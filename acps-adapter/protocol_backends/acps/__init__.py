# -*- coding: utf-8 -*-
"""
ACPs Protocol Backend for Privacy Protection Testing
Implements AIP RPC communication for the Safety Tech scenario.
"""

from .client import ACPsProtocolBackend

__all__ = ["ACPsProtocolBackend"]

# Auto-register with the backend registry
try:
    from scenarios.safety_tech.protocol_backends.common.interfaces import register_backend
    register_backend("acps", ACPsProtocolBackend())
    print("[ACPs Backend] Registered in protocol registry")
except Exception as e:
    print(f"[ACPs Backend] Warning: Could not auto-register: {e}")
