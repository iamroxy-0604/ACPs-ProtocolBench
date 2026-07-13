# -*- coding: utf-8 -*-
"""
ACPs Comm Backend (AIP RPC over HTTP)
Uses aiohttp to avoid httpx↔uvicorn event loop conflicts.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import aiohttp
import sys
from pathlib import Path

current_file = Path(__file__).resolve()
streaming_queue_path = current_file.parent.parent.parent
if str(streaming_queue_path) not in sys.path:
    sys.path.insert(0, str(streaming_queue_path))
comm_path = streaming_queue_path / "comm"
if str(comm_path) not in sys.path:
    sys.path.insert(0, str(comm_path))

from base import BaseCommBackend


# ==========================
# Embedded ACPs Host
# ==========================

@dataclass
class ACPsAgentHandle:
    agent_id: str
    host: str
    port: int
    base_url: str
    _server: Any | None
    _task: asyncio.Task | None

    async def stop(self) -> None:
        if self._server:
            self._server.should_exit = True
        if self._task:
            try:
                await self._task
            except asyncio.CancelledError:
                pass


class ACPsCommBackend(BaseCommBackend):
    """ACPs communication backend using AIP RPC with aiohttp."""

    def __init__(self):
        super().__init__()
        self._endpoints: Dict[str, str] = {}
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    async def register_endpoint(self, agent_id: str, address: str) -> None:
        self._endpoints[agent_id] = address

    async def send(self, src_id: str, dst_id: str, payload: Dict[str, Any]) -> Any:
        dst_url = self._endpoints.get(dst_id)
        if not dst_url:
            raise ValueError(f"No endpoint registered for {dst_id}")

        rpc_url = f"{dst_url.rstrip('/')}/rpc"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

        rpc_body = {
            "jsonrpc": "2.0",
            "method": "rpc",
            "id": f"sq_{int(time.time()*1000)}",
            "params": {
                "command": {
                    "type": "task-command",
                    "id": f"cmd_{int(time.time()*1000)}",
                    "sentAt": now,
                    "senderRole": "leader",
                    "senderId": src_id,
                    "command": "start",
                    "taskId": payload.get("task_id", f"task_{int(time.time())}"),
                    "dataItems": [{"type": "text", "text": payload.get("text", str(payload))}],
                }
            },
        }

        session = await self._get_session()
        async with session.post(rpc_url, json=rpc_body,
                                timeout=aiohttp.ClientTimeout(total=60)) as resp:
            if resp.status == 200:
                return await resp.json()
            raise Exception(f"ACPs send failed: HTTP {resp.status}")

    async def health_check(self, agent_id: str) -> bool:
        url = self._endpoints.get(agent_id)
        if not url:
            return False
        try:
            session = await self._get_session()
            async with session.get(f"{url.rstrip('/')}/health",
                                   timeout=aiohttp.ClientTimeout(total=5)) as resp:
                return resp.status == 200
        except Exception:
            return False

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None

    async def spawn_local_agent(self, agent_id: str, host: str, port: int,
                                executor: Any) -> ACPsAgentHandle:
        """Start an ACPs agent as a local uvicorn server."""
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        import uvicorn
        import uuid

        async def health(request):
            return JSONResponse({"status": "ok", "agent_id": agent_id, "protocol": "acps"})

        async def handle_rpc(request):
            try:
                body = await request.json()
                text = ""
                cmd = body.get("params", {}).get("command", {})
                items = cmd.get("dataItems", [])
                for item in items:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text = item.get("text", "")
                        break
                if not text:
                    text = cmd.get("text", str(cmd))

                result_text = ""
                if executor:
                    try:
                        if hasattr(executor, 'process_message'):
                            result_text = await executor.process_message({"text": text})
                        elif hasattr(executor, 'execute'):
                            result_text = await executor.execute({"text": text})
                        else:
                            result_text = f"ACPs agent {agent_id} received: {text[:50]}"
                    except Exception as e:
                        result_text = f"Error: {e}"
                else:
                    result_text = f"Echo: {text[:100]}"

                now2 = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": body.get("id", str(uuid.uuid4())),
                    "result": {
                        "type": "task-result",
                        "id": str(uuid.uuid4()),
                        "sentAt": now2,
                        "senderRole": "partner",
                        "senderId": agent_id,
                        "taskId": cmd.get("taskId", "unknown"),
                        "status": {
                            "state": "completed",
                            "stateChangedAt": now2,
                            "dataItems": [{"type": "text", "text": result_text}],
                        },
                        "products": [{
                            "id": str(uuid.uuid4()),
                            "name": "reply",
                            "dataItems": [{"type": "text", "text": result_text}],
                        }],
                    }
                })
            except Exception as e:
                return JSONResponse({"jsonrpc": "2.0", "id": None,
                                     "error": {"code": -32000, "message": str(e)}},
                                    status_code=500)

        app = Starlette(routes=[
            Route("/health", health, methods=["GET"]),
            Route("/rpc", handle_rpc, methods=["POST"]),
        ])

        class ServerState:
            should_exit = False

        state = ServerState()

        async def serve():
            config = uvicorn.Config(app, host=host, port=port, log_level="warning")
            server = uvicorn.Server(config)
            server.install_signal_handlers = lambda: None
            # Poll state.should_exit
            async def watch():
                while not state.should_exit:
                    await asyncio.sleep(0.5)
                server.should_exit = True
            task = asyncio.create_task(watch())
            await server.serve()
            task.cancel()

        serve_task = asyncio.create_task(serve())
        await asyncio.sleep(0.5)
        base_url = f"http://{host}:{port}"
        return ACPsAgentHandle(agent_id=agent_id, host=host, port=port,
                               base_url=base_url, _server=state, _task=serve_task)
