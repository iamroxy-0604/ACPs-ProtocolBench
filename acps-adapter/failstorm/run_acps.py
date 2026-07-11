#!/usr/bin/env python3
"""
ACPs Protocol Fail-Storm Recovery Test Runner

Usage:
    python run_acps.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from protocol_backends.acps.runner import ACPsRunner


async def main():
    """Main entry point for ACPs fail-storm testing."""
    try:
        print("🚀 Starting ACPs Protocol Fail-Storm Recovery Test")
        print("=" * 60)

        runner = ACPsRunner(config_path="configs/config_acps.yaml")

        print(f"📋 Configuration: configs/config_acps.yaml")
        print(f"🔷 Protocol: ACPs (AIP RPC v2.1.0)")
        print(f"👥 Agents: {runner.config['scenario']['agent_count']}")
        print(f"⏱️  Runtime: {runner.config['scenario']['total_runtime']}s")
        print(f"💥 Fault time: {runner.config['scenario']['fault_injection_time']}s")
        print("=" * 60)

        result = await runner.run_scenario()

        print("\n" + "=" * 60)
        print("📊 ACPs Fail-Storm Recovery Test Complete")
        print("=" * 60)
        if result:
            for k, v in result.items():
                print(f"  {k}: {v}")

    except KeyboardInterrupt:
        print("\n🛑 Test interrupted by user")
    except Exception as e:
        print(f"❌ ACPs Fail-Storm runner failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
