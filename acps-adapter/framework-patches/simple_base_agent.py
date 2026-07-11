#!/usr/bin/env python3
"""
Simplified BaseAgent for Fail-Storm Recovery scenarios.

This is a minimal implementation that doesn't depend on src/ components.
Only includes the methods needed for fail-storm testing.
"""

import asyncio
import json
import socket
import time
from typing import Any, Dict, Optional, Set
from pathlib import Path
import httpx
from aiohttp import web, ClientSession
import aiohttp


class SimpleBaseAgent:
    """
    Simplified BaseAgent for fail-storm testing scenarios.
    
    This implementation focuses only on the basic server/client functionality
    needed for fail-storm recovery testing without complex protocol adapters.
    """
    
    def __init__(
        self,
        agent_id: str,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        executor: Optional[Any] = None
    ):
        self.agent_id = agent_id
        self.host = host
        self.port = port or self._find_free_port()
        self.executor = executor
        
        # Server components
        self._app: Optional[web.Application] = None
        self._server_task: Optional[asyncio.Task] = None
        self._site: Optional[web.TCPSite] = None
        self._runner: Optional[web.AppRunner] = None
        self._httpx_client = httpx.AsyncClient(timeout=30.0)
        
        # Status tracking
        self._initialized = False
        self._running = False

        # Protocol identity
        self.protocol = "simple"
        self.aic = f"agent:{agent_id}"
    
    @staticmethod
    def _find_free_port() -> int:
        """Find a free port for server binding."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(('', 0))
            s.listen(1)
            port = s.getsockname()[1]
        return port
    
    @classmethod
    async def create_a2a(
        cls,
        agent_id: str,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        executor: Optional[Any] = None,
        **kwargs
    ) -> "SimpleBaseAgent":
        """Create A2A agent instance."""
        agent = cls(agent_id=agent_id, host=host, port=port, executor=executor)
        await agent._start_server()
        agent._initialized = True
        return agent
    
    @classmethod
    async def create_anp(
        cls,
        agent_id: str,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        executor: Optional[Any] = None,
        **kwargs
    ) -> "SimpleBaseAgent":
        """Create ANP agent instance."""
        agent = cls(agent_id=agent_id, host=host, port=port, executor=executor)
        await agent._start_server()
        agent._initialized = True
        return agent
    
    @classmethod
    async def create_acp(
        cls,
        agent_id: str,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        executor: Optional[Any] = None,
        **kwargs
    ) -> "SimpleBaseAgent":
        """Create ACP agent instance."""
        agent = cls(agent_id=agent_id, host=host, port=port, executor=executor)
        await agent._start_server()
        agent._initialized = True
        return agent
    
    @classmethod
    async def create_agora(
        cls,
        agent_id: str,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        executor: Optional[Any] = None,
        **kwargs
    ) -> "SimpleBaseAgent":
        """Create Agora agent instance."""
        agent = cls(agent_id=agent_id, host=host, port=port, executor=executor)
        await agent._start_server()
        agent._initialized = True
        return agent
    
    @classmethod
    async def create_acps(
        cls,
        agent_id: str,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        executor: Optional[Any] = None,
        **kwargs
    ) -> "SimpleBaseAgent":
        """Create ACPs agent instance using AIP RPC communication."""
        agent = cls(agent_id=agent_id, host=host, port=port, executor=executor)
        agent.protocol = "acps"
        agent.aic = f"1.2.156.3088.1.failstorm.{agent_id}"
        await agent._start_server()
        agent._initialized = True
        return agent

    @classmethod
    async def create_simple_json(
        cls,
        agent_id: str,
        host: str = "127.0.0.1",
        port: Optional[int] = None,
        executor: Optional[Any] = None,
        **kwargs
    ) -> "SimpleBaseAgent":
        """Create Simple JSON agent instance."""
        agent = cls(agent_id=agent_id, host=host, port=port, executor=executor)
        await agent._start_server()
        agent._initialized = True
        return agent
    
    async def _start_server(self) -> None:
        """Start the aiohttp server."""
        self._app = web.Application()
        
        # Add basic endpoints
        async def health(request):
            return web.json_response({"status": "ok", "agent_id": self.agent_id})
        
        async def agent_card(request):
            return web.json_response({
                "name": f"Agent {self.agent_id}",
                "agent_id": self.agent_id,
                "protocol": "simple",
                "url": f"http://{self.host}:{self.port}/",
                "endpoints": {
                    "health": "/health",
                    "message": "/message"
                }
            })
        
        async def receive_message(request):
            try:
                request_data = await request.json()
                # Simple message handling
                if self.executor and hasattr(self.executor, 'process_message'):
                    try:
                        result = await self.executor.process_message(request_data)
                        return web.json_response({"status": "ok", "result": result})
                    except Exception as e:
                        return web.json_response({"status": "error", "message": str(e)})
                else:
                    return web.json_response({"status": "ok", "echo": request_data})
            except Exception as e:
                return web.json_response({"status": "error", "message": f"Invalid JSON: {e}"})
        
        # Add routes
        self._app.router.add_get("/health", health)
        self._app.router.add_get("/.well-known/agent.json", agent_card)
        self._app.router.add_post("/message", receive_message)
        
        # Start server
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        
        # Wait for server to be ready
        await self._wait_for_server_ready()
        self._running = True
    
    async def _wait_for_server_ready(self, timeout: float = 10.0) -> None:
        """Wait for server to be ready (uses aiohttp to avoid httpx event loop conflict)."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                url = f"http://{self.host}:{self.port}/health"
                async with ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status == 200:
                            return
            except Exception:
                pass

            await asyncio.sleep(0.1)

        raise RuntimeError(f"Server failed to start within {timeout}s")
    
    async def stop(self) -> None:
        """Stop the agent server."""
        if self._site:
            await self._site.stop()
            self._site = None
        
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        
        if self._httpx_client:
            await self._httpx_client.aclose()
        
        self._running = False
        self._initialized = False
    
    def is_running(self) -> bool:
        """Check if the agent is running."""
        return self._running and self._site is not None
    
    async def health_check(self) -> bool:
        """Check if the agent is healthy (uses aiohttp to avoid httpx conflict)."""
        if not self.is_running():
            return False

        try:
            url = f"http://{self.host}:{self.port}/health"
            async with ClientSession() as session:
                async with session.get(url) as response:
                    return response.status == 200
        except Exception:
            return False

    async def send_message(self, dst_id: str, payload: Dict[str, Any]) -> Any:
        """Send message to another agent via aiohttp (avoids httpx ↔ aiohttp conflict)."""
        dst_agent = None
        # Try to find destination agent through executor or network reference
        if self.executor and hasattr(self.executor, 'agents'):
            dst_agent = self.executor.agents.get(dst_id)
        if self.executor and hasattr(self.executor, 'network'):
            dst_agent = self.executor.network.agents.get(dst_id)

        # Fallback: look up port from known ring topology
        dst_port = None
        if dst_agent and hasattr(dst_agent, 'port'):
            dst_port = dst_agent.port
        else:
            # Try to infer port from agent ID pattern (agent0→9300, agent1→9301, etc.)
            import re
            match = re.search(r'(\d+)$', dst_id)
            if match:
                base_port = getattr(self, 'port', 9300) - (int(re.search(r'(\d+)$', self.agent_id).group(1)) if re.search(r'(\d+)$', self.agent_id) else 0)
                dst_port = base_port + int(match.group(1))

        if dst_port is None:
            raise ValueError(f"Cannot find port for agent {dst_id}")

        url = f"http://127.0.0.1:{dst_port}/message"
        async with ClientSession() as session:
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    return await response.json()
                raise Exception(f"HTTP {response.status}: {await response.text()}")
    
    def get_card(self) -> Dict[str, Any]:
        """Get agent card."""
        return {
            "agent_id": self.agent_id,
            "host": self.host,
            "port": self.port,
            "url": f"http://{self.host}:{self.port}/",
            "running": self.is_running(),
            "initialized": self._initialized
        }
    
    def __repr__(self) -> str:
        return f"SimpleBaseAgent(id='{self.agent_id}', {self.host}:{self.port}, running={self.is_running()})"
