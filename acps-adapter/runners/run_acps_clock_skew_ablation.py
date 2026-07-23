# -*- coding: utf-8 -*-
"""Focused ACPS clock-skew ablation for Safety Tech."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import aiohttp

HERE = Path(__file__).resolve().parent
SAFETY_TECH = HERE.parent
PROJECT_ROOT = HERE.parent.parent.parent
OUTPUT_DIR = SAFETY_TECH / "output"
PORT = 9213
MAX_SKEW_SECONDS = 300
SKEW_CASES = (-600, -301, -120, -30, 30, 120, 299, 600)


async def wait_for_server(url: str, ssl_context, timeout_seconds: float = 30.0) -> None:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, ssl=ssl_context, timeout=aiohttp.ClientTimeout(total=2)
                ) as response:
                    if response.status == 200:
                        return
        except Exception:
            pass
        await asyncio.sleep(0.25)
    raise RuntimeError(f"Timed out waiting for {url}")


async def run_probe(skew_seconds: int, ssl_context) -> dict:
    from datetime import datetime, timezone
    import uuid

    sent_at = datetime.fromtimestamp(time.time() + skew_seconds, tz=timezone.utc).isoformat()
    request_id = str(uuid.uuid4())
    body = {
        "jsonrpc": "2.0",
        "method": "rpc",
        "id": request_id,
        "params": {
            "command": {
                "type": "task-command",
                "id": str(uuid.uuid4()),
                "sentAt": sent_at,
                "senderRole": "leader",
                "senderId": "ClockSkewProbe",
                "command": "start",
                "taskId": f"clock-skew-{skew_seconds:+d}",
                "dataItems": [{"type": "text", "text": f"Clock skew probe {skew_seconds:+d}s"}],
            }
        },
    }
    expected_blocked = abs(skew_seconds) >= MAX_SKEW_SECONDS
    started = time.perf_counter()
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://127.0.0.1:{PORT}/rpc",
            json=body,
            ssl=ssl_context,
            timeout=aiohttp.ClientTimeout(total=90),
        ) as response:
            response_body = await response.json(content_type=None)
            observed_blocked = (
                response.status == 400
                and response_body.get("error", {}).get("code") == -32012
            )
            return {
                "skew_seconds": skew_seconds,
                "expected": "blocked" if expected_blocked else "accepted",
                "observed": "blocked" if observed_blocked else "accepted",
                "http_status": response.status,
                "rpc_error_code": response_body.get("error", {}).get("code"),
                "correct": observed_blocked == expected_blocked,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            }


async def main() -> None:
    import ssl

    cert_dir = SAFETY_TECH / "certs"
    ssl_context = ssl.create_default_context(cafile=str(cert_dir / "trust-bundle.pem"))
    ssl_context.check_hostname = False
    ssl_context.load_cert_chain(
        certfile=str(cert_dir / "client.pem"), keyfile=str(cert_dir / "client.key")
    )

    env = os.environ.copy()
    env["ACPS_MAX_CLOCK_SKEW_SECONDS"] = str(MAX_SKEW_SECONDS)
    code = (
        f"import sys; sys.path.insert(0, r'{PROJECT_ROOT}');"
        "from scenarios.safety_tech.protocol_backends.acps.server import run_server;"
        f"run_server('ACPs_Doctor_B', {PORT}, use_tls=True)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        await wait_for_server(f"https://127.0.0.1:{PORT}/health", ssl_context)
        results = await asyncio.gather(
            *(run_probe(skew_seconds, ssl_context) for skew_seconds in SKEW_CASES)
        )
        correct = sum(result["correct"] for result in results)
        score = round(correct / len(results) * 100, 1)
        report = {
            "experiment": "ACPS mTLS clock-skew defense ablation",
            "transport": "AIP RPC over mTLS",
            "freshness_window_seconds": MAX_SKEW_SECONDS,
            "test_cases": len(results),
            "correct_cases": correct,
            "time_skew_score": score,
            "baseline_s2_score": 62.2,
            "projected_s2_score_same_formula": round(62.2 + score * 0.12, 1),
            "results": results,
            "timestamp": time.time(),
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        output_path = OUTPUT_DIR / f"acps_clock_skew_ablation_{int(time.time())}.json"
        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"RAW_RESULT={output_path}")
        if correct != len(results):
            raise SystemExit(1)
    finally:
        if process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    asyncio.run(main())
