# -*- coding: utf-8 -*-
"""
ACPs Protocol Server for Safety Tech
Minimal ACPs AIP RPC server — accepts JSON-RPC TaskCommands,
calls LLM to generate reply, returns TaskResult.
"""

from __future__ import annotations

import asyncio
import os
import json
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from fastapi import FastAPI, Request, Response
import uvicorn

try:
    from acps_sdk.aip.aip_base_model import (
        TaskCommand, TaskResult, TaskCommandType, TaskStatus,
        TaskState, TextDataItem, Message, Product,
    )
    from acps_sdk.aip.aip_rpc_model import RpcRequest, RpcResponse, JSONRPCError
    print("[ACPs Server] ACPs SDK available")
except ImportError as e:
    raise ImportError(
        f"ACPs SDK is required but not available: {e}. "
        "Please install with: pip install acps-sdk"
    )

# --------- path setup for LLM wrapper ---------
import sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
SAFETY_TECH = HERE.parent.parent
sys.path.insert(0, str(SAFETY_TECH))

try:
    from scenarios.safety_tech.core.llm_wrapper import generate_doctor_reply
except Exception:
    from core.llm_wrapper import generate_doctor_reply


# -------- ACPs Agent App --------

def build_acps_app(agent_name: str) -> FastAPI:
    """Build a minimal FastAPI app that speaks AIP RPC protocol."""

    app = FastAPI(title=f"ACPs Agent - {agent_name}")

    @app.get("/health")
    async def health():
        return {"status": "healthy", "agent": agent_name, "protocol": "acps-aip"}

    @app.post("/rpc")
    async def handle_rpc(request: Request):
        """
        Handle AIP RPC requests (JSON-RPC 2.0).
        Expects: {"jsonrpc":"2.0","method":"rpc","id":"...","params":{"command":{...}}}
        Returns: {"jsonrpc":"2.0","id":"...","result":{...}}
        """
        body = await request.json()
        now_utc = datetime.now(timezone.utc).isoformat()

        try:
            # Parse request — accept both wrapped RPC and raw TaskCommand
            command_data = None
            request_id = body.get("id", str(uuid.uuid4()))

            if "params" in body and "command" in body.get("params", {}):
                # Standard RpcRequest format
                command_data = body["params"]["command"]
            elif "command" in body:
                # Direct TaskCommand
                command_data = body["command"]
            else:
                # Treat body itself as TaskCommand
                command_data = body

            # Extract text from command
            text_content = ""
            task_id = command_data.get("taskId", str(uuid.uuid4()))
            data_items = command_data.get("dataItems", [])
            for item in data_items:
                if isinstance(item, dict) and item.get("type") == "text":
                    text_content = item.get("text", "")
                    break
            if not text_content:
                text_content = command_data.get("text", str(command_data))

            role = agent_name.split("_")[-1].lower()
            print(f"[ACPs-{agent_name}] Processing request: text='{text_content[:80]}...'")

            # Generate doctor reply via LLM
            reply = generate_doctor_reply(f"doctor_{role}", text_content)
            print(f"[ACPs-{agent_name}] Generated reply: '{reply[:80]}...'")

            # Build TaskResult response
            task_result = {
                "type": "task-result",
                "id": str(uuid.uuid4()),
                "sentAt": now_utc,
                "senderRole": "partner",
                "senderId": agent_name,
                "taskId": task_id,
                "status": {
                    "state": "completed",
                    "stateChangedAt": now_utc,
                    "dataItems": [
                        {"type": "text", "text": reply}
                    ],
                },
                "products": [
                    {
                        "id": str(uuid.uuid4()),
                        "name": "doctor_reply",
                        "dataItems": [
                            {"type": "text", "text": reply}
                        ],
                    }
                ],
            }

            rpc_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": task_result,
            }
            return rpc_response

        except Exception as e:
            print(f"[ACPs-{agent_name}] Error: {e}")
            import traceback
            traceback.print_exc()
            return {
                "jsonrpc": "2.0",
                "id": body.get("id", None),
                "error": {
                    "code": -32000,
                    "message": f"Processing failed: {str(e)}",
                },
            }

    return app


def run_server(agent_name: str, port: int, use_tls: bool = False):
    """Entry point for subprocess spawn. Runs a uvicorn server."""
    app = build_acps_app(agent_name)

    if use_tls:
        import ssl
        from pathlib import Path
        cert_dir = Path(__file__).resolve().parent.parent.parent / "certs"

        # Determine which server cert to use
        if "doctor_a" in agent_name.lower():
            cert_prefix = "server-doctor_a"
        elif "doctor_b" in agent_name.lower():
            cert_prefix = "server-doctor_b"
        else:
            cert_prefix = "server-coordinator"

        ssl_keyfile = str(cert_dir / f"{cert_prefix}.key")
        ssl_certfile = str(cert_dir / f"{cert_prefix}.pem")
        ssl_ca_certs = str(cert_dir / "trust-bundle.pem")

        print(f"[ACPs Server] Starting {agent_name} on port {port} with mTLS (cert: {cert_prefix})")
        uvicorn.run(
            app, host="127.0.0.1", port=port, log_level="warning",
            ssl_keyfile=ssl_keyfile, ssl_certfile=ssl_certfile,
            ssl_ca_certs=ssl_ca_certs, ssl_cert_reqs=ssl.CERT_OPTIONAL
        )
    else:
        print(f"[ACPs Server] Starting {agent_name} on port {port} (HTTP)")
        uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
