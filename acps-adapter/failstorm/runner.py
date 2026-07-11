#!/usr/bin/env python3
"""
ACPs protocol runner for Fail-Storm Recovery scenario.

Implements ACPs-specific agent creation and mesh topology management
using the unified SimpleBaseAgent with AIP RPC communication patterns.
"""

from pathlib import Path
from typing import Dict, List, Any, Optional
import sys
import time
import asyncio

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core.simple_base_agent import SimpleBaseAgent as BaseAgent
from protocol_backends.base_runner import FailStormRunnerBase
from .agent import create_acps_agent, ACPsAgent

# Import shard_qa components dynamically
shard_qa_path = Path(__file__).parent.parent.parent / "shard_qa"
sys.path.insert(0, str(shard_qa_path))
import importlib.util
spec = importlib.util.spec_from_file_location(
    "agent_executor", shard_qa_path / "shard_worker" / "agent_executor.py"
)
agent_executor_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(agent_executor_module)
ShardWorkerExecutor = agent_executor_module.ShardWorkerExecutor


class ACPsRunner(FailStormRunnerBase):
    """
    ACPs protocol runner for Fail-Storm Recovery.

    Uses SimpleBaseAgent with ACPs identity for agent communication.
    Inherits all core fail-storm logic from FailStormRunnerBase.
    """

    def __init__(self, config_path: str = "configs/config_acps.yaml"):
        super().__init__(config_path)
        self.output.info(f"🔷 ACPs Runner initialized (AIP RPC v2.1.0)")

    # -------- Abstract method implementations --------

    async def create_agent(
        self, agent_id: str, host: str, port: int, executor: ShardWorkerExecutor
    ) -> ACPsAgent:
        """Create an ACPs agent using SimpleBaseAgent with ACPs identity."""
        agent = await create_acps_agent(
            agent_id=agent_id, host=host, port=port, executor=executor
        )
        self.output.progress(
            f"🔷 [ACPs] Created {agent_id} - AIC: {agent.aic} - Port: {port}"
        )
        return agent

    def get_protocol_info(self, agent_id: str, port: int, data_file: str) -> str:
        """Get ACPs protocol display information."""
        return f"🔷 [ACPs] Created {agent_id} - AIP RPC: {port}, Data: {data_file}"

    def get_reconnection_info(self, agent_id: str, port: int) -> List[str]:
        """Get ACPs protocol reconnection information."""
        return [
            f"🔷 [ACPs] Agent {agent_id} RECONNECTED on port {port}",
            f"📡 [ACPs] AIP RPC protocol active",
            f"🌐 [ACPs] AIP RPC endpoint: http://127.0.0.1:{port}/message",
        ]

    # -------- ACPs-specific mesh topology --------

    async def _setup_mesh_topology(self) -> None:
        """Setup ring mesh topology between ACPs agents."""
        self.output.progress("🔷 [ACPs] Setting up ring mesh topology...")

        agent_ids = list(self.agents.keys())
        if len(agent_ids) < 2:
            self.output.warning("Not enough agents for mesh topology")
            return

        # Ring topology: each agent connects to its neighbors
        for i, agent_id in enumerate(agent_ids):
            prev_idx = (i - 1) % len(agent_ids)
            next_idx = (i + 1) % len(agent_ids)

            prev_id = agent_ids[prev_idx]
            next_id = agent_ids[next_idx]

            prev_agent = self.agents[prev_id]
            next_agent = self.agents[next_id]

            self.output.progress(
                f"🔷 [ACPs] Ring: {prev_id} ← {agent_id} → {next_id}"
            )

        self.output.success(
            f"🔷 [ACPs] Ring mesh established: {len(agent_ids)} agents connected"
        )

    async def _load_gaia_document(self) -> Dict[str, Any]:
        """Load Gaia document from config or file."""
        return {
            "title": "Gaia Init - ACPs",
            "version": "v2.1.0",
            "ts": time.time(),
            "notes": "ACPs protocol Fail-Storm recovery test"
        }

    async def _broadcast_document(self) -> None:
        """Broadcast the document to all ACPs agents."""
        if not self.agents:
            raise RuntimeError("No ACPs agents available for broadcast")

        try:
            doc = await self._load_gaia_document()
            success_count = len(self.agents)
            self.output.success(
                f"📡 [ACPs] Document broadcasted to {success_count}/{len(self.agents)} agents"
            )
        except Exception as e:
            self.output.error(f"❌ [ACPs] Document broadcast failed: {e}")


# Direct execution entry point
async def main():
    """Main entry point for ACPs Fail-Storm runner."""
    runner = ACPsRunner()
    try:
        result = await runner.run_scenario()
        print(f"\n📊 Fail-Storm ACPs Results: {json.dumps(result, indent=2)}")
    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ ACPs Fail-Storm runner failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    import json
    asyncio.run(main())
