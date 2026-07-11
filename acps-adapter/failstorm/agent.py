#!/usr/bin/env python3
"""
ACPs Agent for Fail-Storm Recovery scenario.

Uses the unified SimpleBaseAgent with AIP RPC communication.
Agents communicate via JSON-over-HTTP with ACPs AIC identity headers.
"""

from pathlib import Path
import sys
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.simple_base_agent import SimpleBaseAgent as BaseAgent


class ACPsAgent(BaseAgent):
    """ACPs protocol agent — wraps SimpleBaseAgent with ACPs-specific identity."""

    def __init__(self, agent_id: str, host: str = "127.0.0.1",
                 port: Optional[int] = None, executor=None, **kwargs):
        super().__init__(agent_id=agent_id, host=host, port=port, executor=executor)
        self.protocol = "acps"
        self.aic = f"1.2.156.3088.1.failstorm.{agent_id}"


async def create_acps_agent(
    agent_id: str,
    host: str = "127.0.0.1",
    port: Optional[int] = None,
    executor=None,
    **kwargs
) -> ACPsAgent:
    """Factory function to create an ACPs agent for Fail-Storm."""
    return await BaseAgent.create_acps(
        agent_id=agent_id, host=host, port=port, executor=executor, **kwargs
    )
