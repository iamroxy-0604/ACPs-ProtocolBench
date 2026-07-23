# -*- coding: utf-8 -*-
"""
ACPs Protocol Backend Client
Implements ProtocolBench's BaseProtocolBackend interface for ACPs/AIP RPC.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from scenarios.safety_tech.protocol_backends.common.interfaces import BaseProtocolBackend

# --------- ACPs SDK imports ---------
try:
    from acps_sdk.aip.aip_rpc_client import AipRpcClient
    from acps_sdk.aip.aip_base_model import TaskCommand, TaskCommandType, TextDataItem
    ACP_SDK_AVAILABLE = True
except ImportError:
    ACP_SDK_AVAILABLE = False
    print("[ACPs Client] Warning: ACPs SDK not fully available - using raw HTTP fallback")

# --------- path for registration adapter ---------
HERE = Path(__file__).resolve().parent
SAFETY_TECH = HERE.parent.parent
PROJECT_ROOT = HERE.parent.parent.parent.parent
sys.path.insert(0, str(SAFETY_TECH))

try:
    from scenarios.safety_tech.protocol_backends.acps.registration_adapter import ACPsRegistrationAdapter
except Exception:
    ACPsRegistrationAdapter = None


def _extract_text(payload: Dict[str, Any]) -> str:
    if "text" in payload:
        return str(payload["text"])
    if "body" in payload:
        return str(payload["body"])
    if "content" in payload:
        return str(payload["content"])
    return str(payload)


class ACPsProtocolBackend(BaseProtocolBackend):
    """ACPs protocol backend — sends AIP RPC requests and manages ACPs agent lifecycle."""

    async def send(
        self,
        endpoint: str,
        payload: Dict[str, Any],
        correlation_id: Optional[str] = None,
        probe_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a message to an ACPs agent via AIP RPC."""
        endpoint = (endpoint or "").rstrip("/")
        rpc_url = f"{endpoint}/rpc"
        txt = _extract_text(payload)
        corr = correlation_id or payload.get("correlation_id")
        sender_id = payload.get("sender_id", "acps_sender")

        probe_config = probe_config or {}
        sent_at = probe_config.get("sent_at")
        if sent_at is None and "clock_skew_seconds" in probe_config:
            sent_at = datetime.fromtimestamp(
                time.time() + float(probe_config["clock_skew_seconds"]),
                tz=timezone.utc,
            ).isoformat()
        now_utc = sent_at or datetime.now(timezone.utc).isoformat()

        # Use raw HTTP JSON-RPC (compatible with our minimal ACPs server)
        rpc_body = {
            "jsonrpc": "2.0",
            "method": "rpc",
            "id": str(uuid.uuid4()),
            "params": {
                "command": {
                    "type": "task-command",
                    "id": str(uuid.uuid4()),
                    "sentAt": now_utc,
                    "senderRole": "leader",
                    "senderId": sender_id,
                    "command": "start",
                    "taskId": corr or str(uuid.uuid4()),
                    "dataItems": [{"type": "text", "text": txt}],
                }
            },
        }
        # Build client kwargs for mTLS if using HTTPS
        client_kwargs = {"timeout": 60.0}
        if endpoint.startswith("https://"):
            import ssl
            cert_dir = HERE.parent.parent / "certs"
            ssl_ctx = ssl.create_default_context(ssl.Purpose.SERVER_AUTH)
            ssl_ctx.load_verify_locations(cafile=str(cert_dir / "trust-bundle.pem"))
            ssl_ctx.load_cert_chain(
                certfile=str(cert_dir / "client.pem"),
                keyfile=str(cert_dir / "client.key"),
            )
            client_kwargs["verify"] = ssl_ctx

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                resp = await client.post(rpc_url, json=rpc_body)
                if resp.status_code in (200, 202):
                    resp_data = resp.json()
                    if "error" in resp_data:
                        err = resp_data["error"]
                        return {"status": "error", "error": f"RPC {err.get('code', '')}: {err.get('message', '')}"}
                    return {"status": "success", "data": resp_data}
                return {"status": "error", "error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    async def spawn(self, role: str, port: int, **kwargs: Any) -> Dict[str, Any]:
        """Start an ACPs agent server as a subprocess."""
        try:
            env = os.environ.copy()
            env["COORD_ENDPOINT"] = kwargs.get("coord_endpoint") or os.environ.get(
                "COORD_ENDPOINT", "http://127.0.0.1:8888"
            )
            # Inject correct LLM API credentials (override system defaults)
            if "OPENAI_API_KEY" in os.environ:
                env["OPENAI_API_KEY"] = os.environ["OPENAI_API_KEY"]
            if "OPENAI_BASE_URL" in os.environ:
                env["OPENAI_BASE_URL"] = os.environ["OPENAI_BASE_URL"]

            agent_name = "ACPs_Doctor_A" if role.lower() == "doctor_a" else "ACPs_Doctor_B"

            use_tls = kwargs.get("use_tls", False)
            tls_flag = "True" if use_tls else "False"
            code = (
                f"import sys; sys.path.insert(0, r'{PROJECT_ROOT}');"
                "from scenarios.safety_tech.protocol_backends.acps.server import run_server;"
                f"run_server('{agent_name}', {port}, use_tls={tls_flag})"
            )

            proc = subprocess.Popen(
                [sys.executable, "-c", code],
                cwd=str(PROJECT_ROOT),
                env=env,
            )
            return {"status": "success", "data": {"pid": proc.pid, "port": port}}
        except Exception as e:
            return {"status": "error", "error": f"Failed to spawn ACPs server: {e}"}

    async def register(
        self,
        agent_id: str,
        endpoint: str,
        conversation_id: str,
        role: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """Register agent with RG via ATR-like flow."""
        start_time = time.time()
        try:
            if ACPsRegistrationAdapter is None:
                return {"status": "error", "error": "ACPsRegistrationAdapter not available"}

            rg_endpoint = kwargs.get("rg_endpoint") or os.environ.get(
                "RG_ENDPOINT", "http://127.0.0.1:8001"
            )
            adapter = ACPsRegistrationAdapter({"rg_endpoint": rg_endpoint})
            resp = await adapter.register_agent(agent_id, endpoint, conversation_id, role)
            verification_latency_ms = int((time.time() - start_time) * 1000)

            return {
                "status": "success",
                "data": {
                    "agent_id": agent_id,
                    "verification_method": "acps_atr_proof",
                    "verification_latency_ms": verification_latency_ms,
                    "details": resp,
                },
            }
        except Exception as e:
            verification_latency_ms = int((time.time() - start_time) * 1000)
            return {
                "status": "error",
                "data": {
                    "agent_id": agent_id,
                    "verification_method": "acps_atr_proof",
                    "verification_latency_ms": verification_latency_ms,
                    "details": {},
                },
                "error": str(e),
            }

    async def health(self, endpoint: str) -> Dict[str, Any]:
        """Check health of ACPs agent."""
        url = (endpoint or "").rstrip("/")
        start_time = time.time()
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get(f"{url}/health", timeout=5.0)
                response_time_ms = int((time.time() - start_time) * 1000)
                if r.status_code == 200:
                    try:
                        details = r.json()
                    except Exception:
                        details = {"raw_response": r.text}
                    return {
                        "status": "success",
                        "data": {
                            "healthy": True,
                            "response_time_ms": response_time_ms,
                            "details": details,
                        },
                    }
                return {
                    "status": "error",
                    "data": {"healthy": False, "response_time_ms": response_time_ms},
                    "error": f"Health check failed: HTTP {r.status_code}",
                }
        except Exception as e:
            return {
                "status": "error",
                "data": {"healthy": False},
                "error": str(e),
            }
