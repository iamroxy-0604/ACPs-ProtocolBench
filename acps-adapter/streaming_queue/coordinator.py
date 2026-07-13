# -*- coding: utf-8 -*-
"""ACPs QA Coordinator — full task dispatch and result aggregation."""
from __future__ import annotations
import json, time, asyncio
from typing import Dict, List, Any, Optional


class ACPsQACoordinator:
    """QA Coordinator for ACPs Streaming Queue."""

    def __init__(self, config=None, output=None):
        self.config = config or {}
        qa_cfg = self.config.get("qa", {}) or {}
        coord_cfg = qa_cfg.get("coordinator", {}) or {}
        self.batch_size = int(coord_cfg.get("batch_size", 50))
        self.first_50 = bool(coord_cfg.get("first_50", True))
        self.data_path = coord_cfg.get("data_file", "data/top1000_simplified.jsonl")
        self.result_file = coord_cfg.get("result_file", "results/acps_qa.json")
        self.worker_ids: List[str] = []
        self.agent_network: Any = None
        self.output = output
        self.results: List[Dict] = []
        self._start_time = None

    def set_network(self, network, worker_ids, protocol_name="acps"):
        self.agent_network = network
        self.worker_ids = list(worker_ids)

    async def process_message(self, payload: dict) -> str:
        """Handle incoming commands to coordinator."""
        text = payload.get("text", str(payload))
        try:
            data = json.loads(text) if isinstance(text, str) else text
        except Exception:
            data = {"command": text}
        command = data.get("command", str(data))

        if "start" in command.lower() or "dispatch" in command.lower():
            await self._dispatch_tasks()
            return json.dumps({"status": "dispatched", "tasks": len(self.results)})
        return json.dumps({"status": "acknowledged"})

    async def _dispatch_tasks(self):
        """Load questions and dispatch to workers round-robin."""
        import os
        # Resolve data path
        from pathlib import Path
        data_path = Path(self.data_path)
        if not data_path.is_absolute():
            base = Path(__file__).resolve().parent.parent.parent
            data_path = base / self.data_path

        questions = []
        if data_path.exists():
            with open(data_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            item = json.loads(line)
                            q = item.get("question", item.get("query", str(item)))
                            questions.append(q)
                        except Exception:
                            questions.append(line.strip())
        if self.first_50:
            questions = questions[:50]

        print(f"[Coordinator] Questions: {len(questions)}, Workers: {len(self.worker_ids)}, Network: {self.agent_network is not None}")
        if not questions or not self.worker_ids:
            print("[Coordinator] ABORT: no questions or workers")
            return

        self._start_time = time.time()
        print(f"[Coordinator] Dispatching {len(questions)} questions to {len(self.worker_ids)} workers...")
        tasks = []
        for i, q in enumerate(questions):
            wid = self.worker_ids[i % len(self.worker_ids)]
            tasks.append(self._send_one(wid, q, i))

        self.results = await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_one(self, worker_id: str, question: str, idx: int) -> Dict:
        t0 = time.time()
        try:
            if not self.agent_network:
                return {"idx": idx, "worker": worker_id, "error": "no network"}
            payload = {"text": json.dumps({"question": question, "task_id": f"task_{idx}"}),
                       "sender_id": "Coordinator-1"}
            result = await self.agent_network.route_message("Coordinator-1", worker_id, payload)
            print(f"[Coordinator] Worker {worker_id} responded: {str(result)[:100]}")

            answer = str(result)
            if isinstance(result, dict):
                r = result.get("result", result)
                if isinstance(r, dict):
                    products = r.get("products", [])
                    if products:
                        items = products[0].get("dataItems", [])
                        for item in items:
                            if item.get("type") == "text":
                                answer = item["text"]
                                break
            return {"idx": idx, "worker": worker_id, "answer": answer[:200],
                    "latency_ms": (time.time() - t0) * 1000}
        except Exception as e:
            return {"idx": idx, "worker": worker_id, "error": str(e),
                    "latency_ms": (time.time() - t0) * 1000}

    def get_results(self) -> Dict:
        elapsed = time.time() - self._start_time if self._start_time else 0
        success = [r for r in self.results if isinstance(r, dict) and "error" not in r]
        latencies = [r["latency_ms"] for r in success if "latency_ms" in r]
        return {
            "total": len(self.results),
            "success": len(success),
            "duration_s": round(elapsed, 2),
            "avg_latency_ms": round(sum(latencies)/len(latencies), 1) if latencies else 0,
        }


class QACoordinatorExecutor:
    """Executor wrapper compatible with spawn_local_agent."""
    def __init__(self, config=None, output=None):
        self.coordinator = ACPsQACoordinator(config=config, output=output)
        self.output = output
        self.config = config

    def set_network(self, network, worker_ids, protocol_name="acps"):
        """Proxy set_network to the underlying coordinator."""
        self.coordinator.set_network(network, worker_ids, protocol_name)

    async def process_message(self, payload: dict) -> str:
        return await self.coordinator.process_message(payload)
