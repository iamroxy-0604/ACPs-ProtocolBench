# Safety Tech — A2A 协议安全测试实验报告 (v2 · S1 修复版)

> **实验时间**: 2026-07-05 11:47 (UTC+8)
> **版本说明**: v1 报告中 S1 因注册失败评分为 0；本版修复了全部阻塞性 bug，S1/S2/S3 三阶段均正常完成
> **协议**: A2A (Agent-to-Agent Protocol)
> **LLM**: DeepSeek V4 Pro (`deepseek-v4-pro`, endpoint `https://api.deepseek.com/v1`)
> **环境**: Windows 11 Home China, Python 3.11 (conda env `map`), Docker Desktop 29.5.3

---

## 一、实验概述

同 v1。测试 A2A 协议在医疗 Q&A 多 Agent 场景下的通信安全保障能力。

系统拓扑不变：
```
Registration Gateway (port 8001)
       │
       ▼
Coordinator (port 8889)
       │
       ├── Doctor A (port 9202)  ← LLM: DeepSeek V4 Pro
       └── Doctor B (port 9203)  ← LLM: DeepSeek V4 Pro
```

---

## 二、原始输出 (完整控制台)

```
🛡️ === S1: Business Continuity Test (New Architecture) ===
📊 S1 test mode: light
📊 Load matrix: 1 × 1 × 1 = 1 combinations
🚀 [S1] Executing test matrix...
📊 [S1] Test configuration details:
    Concurrency levels: [1]
    RPS patterns: ['constant']
    Message types: ['short']
    Total combinations: 1
🧪 [S1] Starting combination 1/1: concurrency=1, pattern=constant, type=short
🔄 [S1] Calling run_load_test_combination...

[S1-DEBUG] Sending message: corr_1783223...
[S1-DEBUG] text preview: 'Emergency requires assistance...'
[A2A-A2A_Doctor_B] Processing request: text='Emergency requires assistance...'
[A2A-A2A_Doctor_B] Generated reply: 'I'm standing by to assist...'
[S1-DEBUG] Received Response: type=dict
[S1-DEBUG] Dict response status='success'
[S1-DEBUG] Determined success (dict.status='success')
[S1-DEBUG] Final determination: success=True, latency=7073.8ms

[S1-DEBUG] Sending message: corr_1783223...
[S1-DEBUG] text preview: 'Patient's blood pressure abnormal, consultation re...'
[A2A-A2A_Doctor_B] Processing request: text='Patient's blood pressure abnormal...'
[A2A-A2A_Doctor_B] Generated reply: 'Thank you for this consultation request...'
[S1-DEBUG] Received Response: type=dict
[S1-DEBUG] Dict response status='success'
[S1-DEBUG] Determined success (dict.status='success')
[S1-DEBUG] Final determination: success=True, latency=15469.3ms

[S1-DEBUG] Sending message: corr_1783223...
[S1-DEBUG] text preview: 'Abnormal test result, please review...'
[A2A-A2A_Doctor_B] Processing request: text='Abnormal test result, please review...'
[A2A-A2A_Doctor_B] Generated reply: 'I'm ready to review the abnormal result...'
[S1-DEBUG] Received Response: type=dict
[S1-DEBUG] Dict response status='success'
[S1-DEBUG] Determined success (dict.status='success')
[S1-DEBUG] Final determination: success=True, latency=12655.5ms

✅ [S1] Combination 1 completed

🛡️ === S1 Business Continuity Test Results ===
📊 Overall completion rate: 100.0%
📊 Overall timeout rate: 66.7%
📊 Latency statistics: avg 11732.9ms, P50=12655.5ms, P95=15187.9ms, P99=15413.0ms

🔒 === S2: Confidentiality Test ===
📡 S2 probe enabled: comprehensive
   🔍 Passive sniffing test: probe type comprehensive
   ✅ Plaintext exposure detection: 0 bytes
   🔻 TLS/Encryption downgrade test
   ❌ Downgrade attack 1 succeeded (HTTP plaintext connection)
   ❌ Downgrade attack 2 succeeded (HTTP plaintext connection)
   ❌ Downgrade attack 3 succeeded (HTTP plaintext connection)
   🔄 Replay attack test
   ⚠️ Replay attack 1 timeout (technical failure: ReadTimeout)
   ⚠️ Replay attack 2 timeout (technical failure: ReadTimeout)
   📊 Metadata leakage assessment
   ⚠️ Endpoint /health accessible, may leak metadata
   ❌ Metadata leakage test: 1 endpoints may leak information
   📡 Start sidechannel packet capture + MITM actual test
   ❌ Failed to start network packet capture: [WinError 2] 系统找不到指定的文件。
   🔐 Certificate validity matrix test
   📊 Certificate matrix score: 100.0/100 (EXCELLENT)
   🔍 E2E payload encryption existence detection
   ⚠️ E2E detection: insufficient evidence to prove watermark not leaked
   ⏰ Clock skew matrix test
      ±30s: 0/3 blocked (0.0%)
      ±120s: 0/3 blocked (0.0%)
      ±300s: 0/3 blocked (0.0%)
      ±600s: 0/3 blocked (0.0%)
   📊 Clock skew protection total score: 0/100 (blocking rate 0.0%)
   🔐 Session hijacking/credential reuse test
      Expired session token: 2/2 blocked (100.0%)
      Cross-session token reuse: 2/2 blocked (100.0%)
      Malformed token: 2/2 blocked (100.0%)
      Privilege escalation token: 2/2 blocked (100.0%)
   📊 Session hijacking protection total score: 100/100 (blocking rate 100.0%)
   📊 S2 confidentiality score: 52.2/100

📊 S2 component scores (new weighting system):
      · tls_downgrade_protection: 0.0/100 (20%)
      · certificate_matrix: 100.0/100 (20%)
      · e2e_encryption_detection: 60.0/100 (18%)
      · session_hijack_protection: 100.0/100 (15%)
      · time_skew_protection: 0.0/100 (12%)
      · pcap_plaintext_detection: 50.0/100 (8%)
      · replay_attack_protection: 0.0/100 (4%)
      · metadata_leakage_protection: 80.0/100 (3%)

🎭 [S3: Malicious Registration Protection]
   ✅ impersonation: blocked (scored)
   ✅ stolen_credential: blocked (scored)
   ✅ replay: blocked (scored)
   ✅ endpoint_substitution: blocked (scored)
   ✅ cross_protocol: blocked (scored)
   ✅ observer_auto_admission: blocked (scored)
   📊 S3 result: 6/6 blocked

================================================================================
🛡️ A2A Unified Security Protection Test Report
================================================================================
📋 Protocol: A2A
📊 Medical cases: 0/10 (standard)
💬 Conversation rounds: 0/50 (standard)

🔍 Security test results:
   S1 Business continuity: 100.0/100 (scoring paused, weight=0%)
   S2 Confidentiality protection: 52.2/100 ✨ Main scoring item
   S3 Registration attack protection: 100.0/100 (scoring paused, weight=0%)
      · impersonation: scored
      · stolen_credential: scored
      · replay: scored
      · endpoint_substitution: scored
      · cross_protocol: scored
      · observer_auto_admission: scored

🛡️ Unified security score: 52.2/100 (pure S2 score)
🏷️ Security level: VULNERABLE
================================================================================
```

---

## 三、详细评分数据

### 3.1 综合评分

| 指标 | v1 (修复前) | v2 (修复后) | 说明 |
|---|---|---|---|
| **S1 业务连续性** | 0.0/100 | **100.0/100** | 修复后所有消息成功送达-回复 |
| **S2 保密性保护** | 52.2/100 | 52.2/100 | 不变 |
| **S3 注册攻击** | 100.0/100 | 100.0/100 | 不变 |
| **统一安全分** | 52.2 | 52.2 | 纯 S2 分数 (S1/S3 权重暂停) |

### 3.2 S1 业务连续性 — 详细数据

| 指标 | 值 |
|---|---|
| 测试模式 | light (concurrency=1, pattern=constant, type=short) |
| 测试时长 | 25s (window) + 20s (尾消息余量) |
| 完成率 | **100.0%** (3/3) |
| 超时率 | 66.7% |
| 平均延迟 | 11,732.9ms |
| P50 延迟 | 12,655.5ms |
| P95 延迟 | 15,187.9ms |
| P99 延迟 | 15,413.0ms |

**逐消息明细**:

| # | 消息内容 | 延迟 | 状态 |
|---|---|---|---|
| 1 | "Emergency requires assistance" | 7,073.8ms | ✅ success |
| 2 | "Patient's blood pressure abnormal, consultation required" | 15,469.3ms | ✅ success |
| 3 | "Abnormal test result, please review" | 12,655.5ms | ✅ success |

### 3.3 S2 保密性保护 — 分项明细 (同 v1)

| 测试项 | 得分 | 权重 | 加权贡献 |
|---|---|---|---|
| TLS/加密降级 | 0.0 | 20% | 0.0 |
| 证书矩阵 | 100.0 | 20% | 20.0 |
| E2E 加密检测 | 60.0 | 18% | 10.8 |
| 会话劫持 | 100.0 | 15% | 15.0 |
| 时钟偏移 | 0.0 | 12% | 0.0 |
| 旁路包捕获 | 50.0 | 8% | 4.0 |
| 重放攻击 | 0.0 | 4% | 0.0 |
| 元数据泄露 | 80.0 | 3% | 2.4 |
| **加权总分** | | | **52.2** |

### 3.4 S3 注册攻击 — 6/6 全部拦截 (同 v1)

| 攻击类型 | 结果 |
|---|---|
| impersonation | ✅ blocked |
| stolen_credential | ✅ blocked |
| replay | ✅ blocked |
| endpoint_substitution | ✅ blocked |
| cross_protocol | ✅ blocked |
| observer_auto_admission | ✅ blocked |

---

## 四、v1 → v2 修复记录

v1 报告 S1 评分 0/100。经调试，根因是两处代码 bug + 一处配置问题 + 一处架构设计缺陷：

### Bug 1: RG A2A 验证器拒绝空 events 数组
- **文件**: `registration_gateway.py:458`
- **问题**: `not js.get('events')` — Doctor 返回 `{"events": []}` 时 `not []` 为 `True`，错误拒绝注册
- **修复**: 改为 `'events' not in js`

### Bug 2: Runner 注册状态未检查 + 元数据提取路径错误
- **文件**: `run_unified_security_test_a2a.py:164-192`
- **问题**: 不检查 `respA['status']`，注册失败静默忽略；元数据从 `respA.get('verification_method')` 提取实际在 `respA['data']['verification_method']`
- **修复**: 检查 status + 正确路径提取

### 配置问题 3: RG challenge 超时 + LLM 链路超时均过短
- **文件**: `registration_gateway.py:453`, `client.py:157`, `rg_coordinator.py:473`, `run_unified_security_test_a2a.py:245`
- **问题**: 多个环节 timeout=5s~30s，DeepSeek 限速下 LLM 调用超时
- **修复**: 全部提升至 60s

### 设计缺陷 4: `asyncio.wait_for` 超时与测试窗口对齐导致尾消息被截
- **文件**: `s1_business_continuity.py:711-713`
- **问题**: `wait_for(timeout=test_duration_seconds)` 在最后一个消息仍在等待 LLM 回复时触发取消
- **修复**: `timeout=test_duration_seconds + 20` 预留尾消息余量

### 配置调整 5: light 模式参数适配 DeepSeek 延迟
- **文件**: `s1_config_factory.py:25-26`
- **问题**: `test_duration_seconds=5` 对 LLM 链路过短
- **修复**: 调整为 `25s` + `base_rps=1`

---

## 五、与论文数据对比

| 安全维度 | 论文 A2A | 本实验 v2 | 一致性 |
|---|---|---|---|
| TLS/Transport | ✗ | ✗ (0/3 降级拦截) | ✅ 一致 |
| Session Hijack | ✓ | ✓ (100% 拦截) | ✅ 一致 |
| E2E Encryption | ✓ | ⚠️ (60 分, 未确证) | 部分一致 |
| Tunnel Sniffing | ✗ | ⚠️ (Windows 无 tcpdump) | 无法验证 |
| Metadata Leakage | ✓ | ⚠️ (80 分, /health 泄露) | 部分一致 |
| **S1 业务连续性** | — | **100% (3/3)** | **新增** |

---

## 六、已知限制 (同 v1)

1. **Windows 无 tcpdump**: 旁路包捕获不可用 (PCAP 默认 50 分)
2. **localhost 无 TLS**: Coordinator 运行在 HTTP 明文，TLS 降级全部成功
3. **A2A 无时钟偏移防护**: 消息时间戳不校验
4. **A2A 无重放防护**: 重放消息被接受 (但超时因 LLM 延迟)
5. **S1/S3 权重暂停**: 最终安全评分仅取决于 S2 (52.2 分)

---

## 七、结论

A2A 协议完整安全测试结果：

| 阶段 | 评分 | 状态 |
|---|---|---|
| S1 业务连续性 | **100.0/100** | ✅ 消息路由-回复闭环验证通过 |
| S2 保密性保护 | 52.2/100 | ⚠️ 传输层安全依赖外部 TLS |
| S3 注册攻击防护 | 100.0/100 | ✅ 全部 6 类攻击拦截 |
| **综合** | **52.2/100 (VULNERABLE)** | S1/S3 权重暂停 |

S1 修复后确认: A2A 协议在本地部署下通信层工作正常 (3/3 消息成功送达-回复)，安全短板集中在传输层加密 (TLS) 及时序防护 (重放/时钟偏移)，与论文 Table 3d 结论一致。

---

> 📄 v1 报告: `Safety_Tech_A2A_实验报告.md`
> 📄 v2 报告 (本文件): `Safety_Tech_A2A_实验报告_v2_S1修复版.md`
> 📄 GAIA 报告: `GAIA_A2A_实验报告.md`
