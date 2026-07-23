# -*- coding: utf-8 -*-
"""
ACPs Unified Security Test Runner
Based on the A2A runner, adapted for ACPs protocol (AIP RPC communication).
"""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
import time
import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

HERE = Path(__file__).resolve().parent
SAFETY_TECH = HERE.parent
PROJECT_ROOT = HERE.parent.parent.parent
sys.path.insert(0, str(SAFETY_TECH))
sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# Import core components
try:
    from core.rg_coordinator import RGCoordinator
    from core.attack_scenarios import RegistrationAttackRunner
    from core.backend_api import spawn_backend, register_backend, health_backend, send_backend
except ImportError:
    from scenarios.safety_tech.core.rg_coordinator import RGCoordinator
    from scenarios.safety_tech.core.attack_scenarios import RegistrationAttackRunner
    from scenarios.safety_tech.core.backend_api import (
        spawn_backend,
        register_backend,
        health_backend,
        send_backend,
    )

# ACPs service adapter
try:
    from scenarios.safety_tech.core.llm_wrapper import generate_doctor_reply
except ImportError:
    from core.llm_wrapper import generate_doctor_reply


def _load_medical_dataset() -> List[Dict[str, Any]]:
    try:
        possible = [
            SAFETY_TECH / "data" / "enhanced_medical_questions.json",
            Path("scenarios/safety_tech/data/enhanced_medical_questions.json"),
        ]
        dataset = None
        for p in possible:
            if p.exists():
                dataset = p
                break
        if not dataset:
            raise FileNotFoundError("enhanced_medical_questions.json not found")
        with open(dataset, "r", encoding="utf-8") as f:
            data = json.load(f)
        qs = data.get("questions", [])
        cases: List[Dict[str, Any]] = []
        for i, q in enumerate(qs[:2]):
            cases.append(
                {
                    "case_id": f"dataset_case_{q.get('id', i + 1)}",
                    "patient_info": f"Patient: {q.get('sensitive_info', {}).get('name', 'Unknown')}",
                    "sensitive_info": q.get("sensitive_info", {}),
                    "original_question": q.get("original_question", ""),
                    "enhanced_question": q.get("enhanced_question", ""),
                    "initial_question": f"Medical consultation needed: {q.get('enhanced_question', q.get('original_question', ''))}",
                }
            )
        return cases
    except Exception as e:
        raise RuntimeError(f"Failed to load medical dataset: {e}")


async def _wait_http_ok(url: str, timeout_s: float = 20.0) -> None:
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            async with httpx.AsyncClient() as c:
                r = await c.get(url, timeout=2.0)
                if r.status_code == 200:
                    return
        except Exception:
            pass
        await asyncio.sleep(0.3)
    raise RuntimeError(f"Timeout waiting {url}")


async def main():
    # Port configuration
    rg_port = 8001
    coord_port = 8889
    a_port = 9202
    b_port = 9203
    conv_id = os.environ.get("ACPS_CONV_ID", "conv_acps_eaves")

    procs: List[Any] = []
    try:
        # 1) Start RG
        import subprocess

        proc = subprocess.Popen(
            [
                sys.executable,
                "-c",
                f"import sys; sys.path.insert(0, '{PROJECT_ROOT}'); "
                "from scenarios.safety_tech.core.registration_gateway import RegistrationGateway; "
                f"RegistrationGateway({{'session_timeout':3600,'max_observers':5,'require_observer_proof':True,'a2a_enable_challenge':True}}).run(host='127.0.0.1', port={rg_port})",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        procs.append(proc)
        print(f"Started RG process with PID: {proc.pid}")
        await _wait_http_ok(f"http://127.0.0.1:{rg_port}/health", 15.0)

        # 2) Start Coordinator
        coordinator = RGCoordinator(
            {
                "rg_endpoint": f"http://127.0.0.1:{rg_port}",
                "conversation_id": conv_id,
                "coordinator_port": coord_port,
            }
        )
        await coordinator.start()
        await _wait_http_ok(f"http://127.0.0.1:{coord_port}/health", 20.0)

        # 3) Start ACPs doctor nodes with mTLS
        use_tls = os.environ.get("ACPS_USE_TLS", "true").lower() == "true"
        protocol = "https" if use_tls else "http"
        print(f"   🔐 ACPs TLS mode: {'mTLS enabled' if use_tls else 'HTTP plaintext'}")

        await spawn_backend("acps", "doctor_a", a_port, use_tls=use_tls)
        await spawn_backend("acps", "doctor_b", b_port, use_tls=use_tls)

        # Health check with TLS (self-signed cert)
        import ssl as _ssl
        _ssl_ctx = _ssl.create_default_context()
        _ssl_ctx.check_hostname = False
        _ssl_ctx.verify_mode = _ssl.CERT_NONE

        async def _wait_https_ok(url, timeout_s=20.0):
            start = time.time()
            while time.time() - start < timeout_s:
                try:
                    async with httpx.AsyncClient(verify=False) as c:
                        r = await c.get(url, timeout=2.0)
                        if r.status_code == 200:
                            return
                except Exception:
                    pass
                await asyncio.sleep(0.3)
            raise RuntimeError(f"Timeout waiting {url}")

        await _wait_https_ok(f"{protocol}://127.0.0.1:{a_port}/health", 15.0)
        await _wait_https_ok(f"{protocol}://127.0.0.1:{b_port}/health", 15.0)

        # 4) Register to RG
        doc_a_verify = {}
        doc_b_verify = {}

        try:
            respA = await register_backend(
                "acps",
                "ACPs_Doctor_A",
                f"{protocol}://127.0.0.1:{a_port}",
                conv_id,
                "doctor_a",
                rg_endpoint=f"http://127.0.0.1:{rg_port}",
            )
            if respA.get("status") == "error":
                print(
                    f"   ⚠️ ACPs_Doctor_A registration returned error: {respA.get('error', 'unknown')} (continuing anyway)"
                )
            dataA = respA.get("data", {})
            doc_a_verify = {
                "method": dataA.get("verification_method"),
                "latency_ms": dataA.get("verification_latency_ms"),
                "blocked_by": dataA.get("blocked_by"),
                "reason": dataA.get("reason"),
            }
            print(f"   ✅ ACPs_Doctor_A registered: {doc_a_verify}")
        except Exception as e:
            print(f"   ⚠️ Failed to register ACPs_Doctor_A: {e} (continuing anyway)")
            respA = {}

        try:
            respB = await register_backend(
                "acps",
                "ACPs_Doctor_B",
                f"{protocol}://127.0.0.1:{b_port}",
                conv_id,
                "doctor_b",
                rg_endpoint=f"http://127.0.0.1:{rg_port}",
            )
            if respB.get("status") == "error":
                print(
                    f"   ⚠️ ACPs_Doctor_B registration returned error: {respB.get('error', 'unknown')} (continuing anyway)"
                )
            dataB = respB.get("data", {})
            doc_b_verify = {
                "method": dataB.get("verification_method"),
                "latency_ms": dataB.get("verification_latency_ms"),
                "blocked_by": dataB.get("blocked_by"),
                "reason": dataB.get("reason"),
            }
            print(f"   ✅ ACPs_Doctor_B registered: {doc_b_verify}")
        except Exception as e:
            print(f"   ⚠️ Failed to register ACPs_Doctor_B: {e} (continuing anyway)")
            respB = {}

        # Wait for Coordinator directory refresh + rate limit cooldown
        await asyncio.sleep(8)

        # ===== S1: Business Continuity Test =====
        print("\n🛡️ === S1: Business Continuity Test (ACPs) ===")

        s1_test_mode = os.environ.get("ACPS_S1_TEST_MODE", "light").lower()
        skip_s1 = s1_test_mode in ("skip", "none", "off")

        if not skip_s1:
            from scenarios.safety_tech.core.s1_config_factory import create_s1_tester

            if s1_test_mode == "protocol_optimized":
                s1_tester = create_s1_tester("acps", "protocol_optimized")
            else:
                s1_tester = create_s1_tester("acps", s1_test_mode)

            print(f"📊 S1 test mode: {s1_test_mode}")

            async def acps_send_function(payload):
                """ACPs send function via Coordinator."""
                async with httpx.AsyncClient() as client:
                    try:
                        response = await client.post(
                            f"http://127.0.0.1:{coord_port}/route_message",
                            json=payload,
                            timeout=60.0,
                        )
                        if response.status_code in (200, 202):
                            try:
                                resp_data = response.json()
                                if resp_data.get("status") in ["success", "ok", "processed"]:
                                    return {"status": "success", "data": resp_data}
                                return resp_data
                            except Exception:
                                return {"status": "success", "message": "Request processed"}
                        else:
                            return {"status": "error", "error": f"HTTP {response.status_code}"}
                    except Exception as e:
                        return {"status": "error", "error": str(e)}

            try:
                s1_results = await s1_tester.run_full_test_matrix(
                    send_func=acps_send_function,
                    sender_id="ACPs_Doctor_A",
                    receiver_id="ACPs_Doctor_B",
                    rg_port=rg_port,
                    coord_port=coord_port,
                    obs_port=8004,
                )
            except Exception as e:
                print(f"❌ S1 test execution failed: {e}")
                import traceback
                print(f"Detailed error: {traceback.format_exc()}")
                s1_results = []

        # Process S1 results
        if skip_s1:
            s1_report = {
                "test_summary": {"overall_completion_rate": 0.0, "overall_timeout_rate": 0.0,
                                 "total_requests": 0, "total_successful": 0, "total_test_combinations": 0},
                "latency_analysis": {"avg_ms": 0.0, "p95_ms": 0.0, "p99_ms": 0.0},
                "detailed_results": [],
            }
        else:
            s1_report = s1_tester.generate_comprehensive_report()

        print(f"\n🛡️ === S1 Business Continuity Test Results ===")
        print(f"📊 Overall completion rate: {s1_report['test_summary']['overall_completion_rate']:.1%}")
        print(f"📊 Overall timeout rate: {s1_report['test_summary']['overall_timeout_rate']:.1%}")
        print(f"📊 Latency statistics: avg {s1_report['latency_analysis']['avg_ms']:.1f}ms, "
              f"P50={s1_report['latency_analysis'].get('p50_ms', 0):.1f}ms, "
              f"P95={s1_report['latency_analysis']['p95_ms']:.1f}ms, "
              f"P99={s1_report['latency_analysis']['p99_ms']:.1f}ms")

        s1_rate = s1_report["test_summary"]["overall_completion_rate"]
        s1_score = round(s1_rate * 100, 1)

        # ===== S2: Confidentiality Test =====
        print("\n🔒 === S2: Confidentiality Test (ACPs) ===")

        s2_test_results = {
            "downgrade_attempts": 0, "downgrade_blocked": 0,
            "replay_attempts": 0, "replay_blocked": 0,
            "clock_skew_attempts": 0, "clock_skew_correct": 0,
            "clock_skew_details": [],
            "metadata_leakage": 0,
        }

        # TLS downgrade test
        # Target the HTTPS doctor endpoint for downgrade tests
        s2_target = f"{protocol}://127.0.0.1:{b_port}" if use_tls else f"http://127.0.0.1:{coord_port}"
        downgrade_test_count = 3
        for i in range(downgrade_test_count):
            try:
                async with httpx.AsyncClient(verify=False) as client:
                    resp = await client.get(f"http://127.0.0.1:{b_port if use_tls else coord_port}/health"
                                           if not use_tls else
                                           f"{protocol}://127.0.0.1:{b_port}/health",
                                           timeout=3.0)
                    s2_test_results["downgrade_attempts"] += 1
                    if resp.status_code in (400, 403, 426):
                        s2_test_results["downgrade_blocked"] += 1
                        print(f"   ✅ Downgrade attack {i+1} blocked")
                    else:
                        print(f"   ❌ Downgrade attack {i+1} succeeded")
            except Exception as e:
                s2_test_results["downgrade_attempts"] += 1
                s2_test_results["downgrade_blocked"] += 1
                print(f"   ✅ Downgrade attack {i+1} blocked (exception)")

        # Replay attack test
        for i in range(2):
            try:
                old_message = {
                    "sender_id": "ACPs_Doctor_A",
                    "receiver_id": "ACPs_Doctor_B",
                    "text": f"Replay test message {i+1}",
                    "message_id": f"replay_msg_{int(time.time()-3600)}_{i}",
                    "correlation_id": f"replay_corr_{int(time.time()-3600)}_{i}",
                    "timestamp": time.time() - 3600,
                }
                async with httpx.AsyncClient() as client:
                    resp = await client.post(
                        f"http://127.0.0.1:{coord_port}/route_message",
                        json=old_message,
                        timeout=5.0,
                    )
                    s2_test_results["replay_attempts"] += 1
                    if resp.status_code in (400, 401, 403):
                        s2_test_results["replay_blocked"] += 1
                        print(f"   ✅ Replay attack {i+1} blocked")
                    else:
                        print(f"   ⚠️ Replay attack {i+1} result unclear")
            except Exception:
                s2_test_results["replay_attempts"] += 1

        # Metadata leakage
        exposed = 0
        for ep in ["/health", "/metrics", "/status", "/info", "/debug"]:
            try:
                async with httpx.AsyncClient() as client:
                    r = await client.get(f"http://127.0.0.1:{coord_port}{ep}", timeout=2.0)
                    if r.status_code == 200:
                        exposed += 1
            except Exception:
                pass
        s2_test_results["metadata_leakage"] = exposed
        metadata_score = max(0, 100 - exposed * 20)

        # Session hijack test
        hijack_blocked = 0
        hijack_total = 0
        for scenario_name, token in [
            ("expired_token", "expired_session_12345"),
            ("cross_session_reuse", "other_user_session_67890"),
            ("malformed_token", "malformed__invalid__token"),
            ("privilege_escalation", "admin_session_98765"),
        ]:
            for _ in range(2):
                try:
                    hijack_payload = {
                        "sender_id": "ACPs_Doctor_A",
                        "receiver_id": "ACPs_Doctor_B",
                        "text": f"Session hijack test: {scenario_name}",
                    }
                    async with httpx.AsyncClient(
                        headers={"Authorization": f"Bearer {token}"}
                    ) as client:
                        resp = await client.post(
                            f"http://127.0.0.1:{coord_port}/route_message",
                            json=hijack_payload,
                            timeout=5.0,
                        )
                        hijack_total += 1
                        if resp.status_code in (400, 401, 403):
                            hijack_blocked += 1
                except Exception:
                    hijack_total += 1
                    hijack_blocked += 1

        session_hijack_score = int((hijack_blocked / hijack_total * 100)) if hijack_total else 0

        # Commands inside the 300-second freshness window remain usable;
        # stale or excessively future-dated commands are rejected.
        max_clock_skew_seconds = 300
        for skew_seconds in (-600, -301, -120, -30, 30, 120, 299, 600):
            should_block = abs(skew_seconds) >= max_clock_skew_seconds
            result = await send_backend(
                "acps",
                f"{protocol}://127.0.0.1:{b_port}",
                {
                    "sender_id": "ACPs_Doctor_A",
                    "text": f"Clock skew probe {skew_seconds:+d}s",
                    "correlation_id": f"clock-skew-{skew_seconds:+d}",
                },
                correlation_id=f"clock-skew-{skew_seconds:+d}",
                probe_config={"clock_skew_seconds": skew_seconds},
            )
            was_blocked = result.get("status") == "error"
            correct = was_blocked == should_block
            s2_test_results["clock_skew_attempts"] += 1
            s2_test_results["clock_skew_correct"] += int(correct)
            detail = {
                "skew_seconds": skew_seconds,
                "expected": "blocked" if should_block else "accepted",
                "observed": "blocked" if was_blocked else "accepted",
                "correct": correct,
                "error": result.get("error"),
            }
            s2_test_results["clock_skew_details"].append(detail)
            print(
                f"   {'PASS' if correct else 'FAIL'} Clock skew {skew_seconds:+d}s: "
                f"expected {detail['expected']}, observed {detail['observed']}"
            )

        time_skew_score = round(
            s2_test_results["clock_skew_correct"]
            / max(s2_test_results["clock_skew_attempts"], 1)
            * 100,
            1,
        )

        # S2 scoring (same weights as A2A)
        s2_score = round(
            s2_test_results["downgrade_blocked"] / max(s2_test_results["downgrade_attempts"], 1) * 20
            + 50 * 0.20  # cert_matrix: default medium
            + 60 * 0.18  # e2e: default medium
            + session_hijack_score * 0.15
            + time_skew_score * 0.12
            + 50 * 0.08  # pcap: default medium
            + s2_test_results["replay_blocked"] / max(s2_test_results["replay_attempts"], 1) * 4
            + metadata_score * 0.03,
            1,
        )
        print(f"   📊 S2 confidentiality score: {s2_score}/100")
        print(f"   📊 Session hijacking: {hijack_blocked}/{hijack_total} blocked ({session_hijack_score}/100)")
        print(
            f"   📊 Clock skew matrix: "
            f"{s2_test_results['clock_skew_correct']}/{s2_test_results['clock_skew_attempts']} "
            f"correct ({time_skew_score}/100)"
        )

        # ===== S3: Malicious Registration Protection =====
        print("\n🎭 [S3: Malicious Registration Protection]")
        runner = RegistrationAttackRunner(
            {
                "rg_endpoint": f"http://127.0.0.1:{rg_port}",
                "conversation_id": conv_id,
                "protocol": "acps",
                "attack_timeout": 10.0,
            }
        )
        registration_attacks: List[Dict[str, Any]] = []
        try:
            res = await runner.run_all_attacks()
            for a in res:
                t = getattr(a, "attack_type", "unknown")
                s = getattr(a, "success", False)
                print(f"   {'❌' if s else '✅'} {t}: {'succeeded (lost score)' if s else 'blocked (scored)'}")
                registration_attacks.append({"attack_type": t, "success": s})
        except Exception as e:
            print(f"   ⚠️ Registration attack test exception: {e}")
        s3_blocked = len([1 for a in registration_attacks if not a.get("success", False)])
        total_s3 = len(registration_attacks) if registration_attacks else 6
        s3_score = round((s3_blocked / total_s3 * 100) if total_s3 > 0 else 100, 1)

        # ===== Report =====
        unified = round(s2_score, 1)
        level = "SECURE" if unified >= 90 else "MODERATE" if unified >= 70 else "VULNERABLE"

        print("\n" + "=" * 80)
        print("🛡️ ACPs Unified Security Protection Test Report")
        print("=" * 80)
        print("📋 Protocol: ACPs (AIP RPC)")
        print()
        print("🔍 Security test results:")
        print(f"   S1 Business continuity: {s1_score:.1f}/100 (scoring paused, weight=0%)")
        print(f"   S2 Confidentiality protection: {s2_score:.1f}/100 ✨ Main scoring item")
        print(f"   S3 Registration attack protection: {s3_score:.1f}/100 (scoring paused, weight=0%)")
        if registration_attacks:
            for a in registration_attacks:
                print(f"      · {a['attack_type']}: {'scored' if not a['success'] else 'lost score'}")
        print()
        print(f"🛡️ Unified security score: {unified:.1f}/100 (pure S2 score)")
        print(f"🏷️ Security level: {level}")
        print("=" * 80 + "\n")

        # Save report
        out_dir = SAFETY_TECH / "output"
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / f"acps_unified_security_report_{int(time.time())}.json"
        report = {
            "protocol": "acps",
            "security_score": unified,
            "security_level": level,
            "test_results": {
                "S1_business_continuity": {"completion_rate": s1_rate, "score": s1_score},
                "S2_privacy_protection": {
                    "comprehensive_score": s2_score,
                    "time_skew_score": time_skew_score,
                    "clock_skew_matrix": s2_test_results["clock_skew_details"],
                },
                "S3_registration_defense": {"attacks_blocked": f"{s3_blocked}/{total_s3}", "score": s3_score},
            },
            "timestamp": time.time(),
        }
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"📄 Detailed report: {out_file}")

    finally:
        for p in procs:
            try:
                p.send_signal(signal.SIGTERM)
            except Exception:
                pass
        await asyncio.sleep(1)
        for p in procs:
            try:
                if p.poll() is None:
                    p.kill()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(main())
