# -*- coding: utf-8 -*-
"""
ACPs Streaming Queue Runner
"""

from __future__ import annotations

import os, asyncio, time, sys, json
from pathlib import Path
from typing import Dict, List, Any, Optional

HERE = Path(__file__).resolve()
STREAMING_Q = HERE.parents[1]
sys.path.insert(0, str(STREAMING_Q))
sys.path.insert(0, str(HERE.parent))

from runner_base import RunnerBase, ColoredOutput

if str(STREAMING_Q) not in sys.path:
    sys.path.insert(0, str(STREAMING_Q))

from core.network_base import NetworkBase
from protocol_backend.acps.comm import ACPsCommBackend
from protocol_backend.acps.coordinator import QACoordinatorExecutor
from protocol_backend.acps.worker import QAAgentExecutor
import aiohttp


class ACPsRunner(RunnerBase):
    def __init__(self, config_path: str = "config/acps.yaml"):
        super().__init__(config_path)
        self._handles: List[Any] = []
        self._backend: Optional[ACPsCommBackend] = None

    async def create_network(self) -> NetworkBase:
        self._backend = ACPsCommBackend()
        return NetworkBase(comm_backend=self._backend)

    async def setup_agents(self) -> List[str]:
        out = self.output
        out.info("Initializing ACPs Streaming Queue...")

        qa_cfg = self._convert_config_for_qa_agent(self.config)
        assert self._backend is not None

        coord_port = int(self.config.get("qa", {}).get("coordinator", {}).get("port", 9998))
        coordinator_executor = QACoordinatorExecutor(self.config, out)
        coord_handle = await self._backend.spawn_local_agent(
            agent_id="Coordinator-1", host="localhost", port=coord_port, executor=coordinator_executor
        )
        self._handles.append(coord_handle)
        await self.network.register_agent("Coordinator-1", coord_handle.base_url)
        out.success(f"Coordinator-1 @ {coord_handle.base_url}")

        worker_count = int(self.config.get("qa", {}).get("worker", {}).get("count", 4))
        start_port = int(self.config.get("qa", {}).get("worker", {}).get("start_port", 10001))
        worker_ids: List[str] = []

        for i in range(worker_count):
            wid = f"Worker-{i+1}"
            port = start_port + i
            w_exec = QAAgentExecutor(qa_cfg)
            w_handle = await self._backend.spawn_local_agent(agent_id=wid, host="localhost", port=port, executor=w_exec)
            self._handles.append(w_handle)
            await self.network.register_agent(wid, w_handle.base_url)
            worker_ids.append(wid)
            out.success(f"{wid} @ {w_handle.base_url}")

        if hasattr(coordinator_executor, "set_network"):
            coordinator_executor.set_network(self.network, worker_ids, "acps")
        return worker_ids

    async def send_command_to_coordinator(self, command: str) -> Optional[Dict[str, Any]]:
        coord_port = int(self.config.get("qa", {}).get("coordinator", {}).get("port", 9998))
        url = f"http://localhost:{coord_port}/rpc"
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        payload = {
            "jsonrpc": "2.0", "method": "rpc", "id": f"cmd_{int(time.time()*1000)}",
            "params": {"command": {
                "type": "task-command", "id": f"cmd_{int(time.time()*1000)}",
                "sentAt": now, "senderRole": "leader", "senderId": "Runner",
                "command": "start", "dataItems": [{"type": "text", "text": command}],
            }}
        }
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=60)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        result = data.get("result", {})
                        products = result.get("products", [])
                        if products:
                            items = products[0].get("dataItems", [])
                            for item in items:
                                if item.get("type") == "text":
                                    return {"result": item["text"]}
                        return {"result": json.dumps(result)}
        except Exception as e:
            self.output.error(f"Command failed: {e}")
            return None

    def _convert_config_for_qa_agent(self, config):
        if not config:
            return None
        core = config.get("core", {})
        if core.get("type") == "openai":
            api_key = os.getenv("OPENAI_API_KEY") or core.get("openai_api_key")
            base_url = os.getenv("OPENAI_BASE_URL") or core.get("openai_base_url", "https://api.openai.com/v1")
            return {"model": {
                "type": "openai", "name": core.get("name", "deepseek-v4-pro"),
                "openai_api_key": api_key, "openai_base_url": base_url,
                "temperature": core.get("temperature", 0.0),
            }}
        return {"model": {"type": "local", "name": core.get("name", "deepseek-v4-pro")}}

    async def cleanup(self) -> None:
        try:
            await super().cleanup()
        finally:
            for h in self._handles:
                try:
                    await h.stop()
                except Exception:
                    pass


# Direct execution
async def _main():
    runner = ACPsRunner()
    await runner.run()

if __name__ == "__main__":
    asyncio.run(_main())
