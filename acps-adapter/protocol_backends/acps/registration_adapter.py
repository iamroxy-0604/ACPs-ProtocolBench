# -*- coding: utf-8 -*-
"""
ACPs Protocol Registration Adapter
Uses the Safety Tech RG's /register endpoint with ACPs-specific proof format.
In a full deployment this would go through ATR (registry-server → CA → certificate),
but for benchmark testing we register directly with the RG using an ACPs-style proof.
"""

from __future__ import annotations

import time
import uuid
from typing import Dict, Any

import httpx


class ACPsRegistrationAdapter:
    """ACPs registration adapter — registers ACPs agents with the Safety Tech RG."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.rg_endpoint = config.get("rg_endpoint", "http://127.0.0.1:8001")

    async def register_agent(
        self,
        agent_id: str,
        endpoint: str,
        conversation_id: str,
        role: str = "doctor",
    ) -> Dict[str, Any]:
        """Register an ACPs agent with the RG using an ACPs-style proof."""

        base = endpoint.rstrip("/")

        # Probe health (disable cert verification for self-signed test certs)
        import ssl
        verify_ctx = ssl.create_default_context()
        verify_ctx.check_hostname = False
        verify_ctx.verify_mode = ssl.CERT_NONE
        async with httpx.AsyncClient(verify=verify_ctx) as client:
            health_resp = await client.get(f"{base}/health", timeout=10.0)
            if health_resp.status_code != 200:
                raise RuntimeError(f"ACPs /health probe failed: {health_resp.status_code}")

        # Build ACPs-style proof (ATR-compatible, simulation mode)
        proof = {
            "timestamp": time.time(),
            "nonce": str(uuid.uuid4()),
            "aic": f"1.2.156.3088.1.test.{agent_id}",  # Simulated AIC (Agent Identity Code)
            "acs_version": "2.1.0",
            "protocol": "acps-aip",
            "endpoint_health": True,
            # In production: would include CA-signed certificate, DID document, etc.
        }

        registration_request = {
            "protocol": "acps",
            "agent_id": agent_id,
            "endpoint": endpoint,
            "conversation_id": conversation_id,
            "role": role,
            "protocolMeta": {
                "protocol_version": "2.1.0",
                "capabilities": ["aip-rpc", "health", "atr"],
                "aic_format": "oid",
            },
            "proof": proof,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.rg_endpoint}/register",
                json=registration_request,
                timeout=30.0,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"ACPs registration failed: {resp.status_code} - {resp.text}"
                )
            return resp.json()

    async def get_conversation_directory(self, conversation_id: str) -> Dict[str, Any]:
        """Query RG for conversation participants."""
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{self.rg_endpoint}/directory",
                params={"conversation_id": conversation_id},
                timeout=15.0,
            )
            if resp.status_code != 200:
                raise RuntimeError(
                    f"Directory query failed: {resp.status_code} - {resp.text}"
                )
            return resp.json()
