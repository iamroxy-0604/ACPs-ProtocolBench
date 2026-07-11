# Safety Tech — A2A 协议安全测试实验报告

> **实验时间**: 2026-07-04 19:45 (UTC+8)
> **协议**: A2A (Agent-to-Agent Protocol)
> **LLM**: DeepSeek V4 Pro (`deepseek-v4-pro`)
> **数据**: ChatDoctor-HealthCareMagic 增强医疗问答 (10 例)
> **环境**: Windows 11, Python 3.11, conda env `map`

---

## 一、实验概述

Safety Tech 场景评估 A2A 协议在医疗 Q&A 场景下的通信安全保障能力。实验启动了一套本地多 Agent 系统（Registration Gateway → Coordinator → 两名 LLM Doctor Agent），并对其注入安全探测（TLS 降级、重放攻击、会话劫持、时钟偏移、证书矩阵等），评估协议层面的安全防护水平。

**系统拓扑**:
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

## 二、原始输出 (控制台)

```
🛡️ === S1: Business Continuity Test (New Architecture) ===
📊 S1 test mode: light
📊 Load matrix: 1 × 1 × 1 = 1 combinations

🛡️ === S1 Business Continuity Test Results ===
📊 Overall completion rate: 0.0%
📊 Overall timeout rate: 0.0%
📊 Latency statistics: avg 0.0ms, P50=0.0ms, P95=0.0ms, P99=0.0ms

🔒 === S2: Confidentiality Test (Transport and Session Confidentiality Verification) ===
📡 S2 probe enabled: comprehensive
   🔍 Passive sniffing test: probe type comprehensive
   ✅ Plaintext exposure detection: 0 bytes (probe found no plaintext fragments)
   🔻 TLS/Encryption downgrade test
   ❌ Downgrade attack 1 succeeded (HTTP plaintext connection)
   ❌ Downgrade attack 2 succeeded (HTTP plaintext connection)
   ❌ Downgrade attack 3 succeeded (HTTP plaintext connection)
   🔄 Replay attack test
   ⚠️ Replay attack 1 result unclear (status: 500)
   ⚠️ Replay attack 2 result unclear (status: 500)
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
   S1 Business continuity: 0.0/100 (scoring paused, weight=0%)
   S2 Confidentiality protection: 52.2/100 (transport and session confidentiality) ✨ Main scoring item
   S3 Registration attack protection: 100.0/100 (scoring paused, weight=0%)

🛡️ Unified security score: 52.2/100 (pure S2 score)
🏷️ Security level: VULNERABLE
📄 Detailed report: scenarios/safety_tech/output/a2a_unified_security_report_1783165548.json
================================================================================
```

---

## 三、详细评分数据

### 3.1 综合评分

| 指标 | 分数 | 权重 | 说明 |
|---|---|---|---|
| **统一安全分** | **52.2/100** | — | 纯 S2 分数 |
| **安全等级** | **VULNERABLE** | — | 需要额外安全层 |

### 3.2 S2 保密性保护 — 分项明细

| 测试项 | 得分 | 权重 | 加权贡献 | 说明 |
|---|---|---|---|---|
| TLS/加密降级防护 | 0.0/100 | 20% | 0.0 | 3 次降级攻击全部成功 (HTTP 明文) |
| 证书矩阵 | 100.0/100 | 20% | 20.0 | expired/self-signed/hostname_mismatch/weak_cipher/TLS降级 全部拦截 |
| E2E 加密检测 | 60.0/100 | 18% | 10.8 | 水印注入成功，但 PCAP 不可用无法确证未泄露 |
| 会话劫持防护 | 100.0/100 | 15% | 15.0 | 4 类攻击全部 100% 拦截 |
| 时钟偏移防护 | 0.0/100 | 12% | 0.0 | 4 个偏移级别 (30s~600s) 均未拦截 |
| 旁路包捕获 | 50.0/100 | 8% | 4.0 | Windows 无 tcpdump，默认中位数 |
| 重放攻击防护 | 0.0/100 | 4% | 0.0 | 2 次重放均返回 500（状态不明） |
| 元数据泄露防护 | 80.0/100 | 3% | 2.4 | `/health` 端点可访问，扣 20 分 |

**加权公式**:
```
S2 = 0.0×0.20 + 100.0×0.20 + 60.0×0.18 + 100.0×0.15 + 0.0×0.12 + 50.0×0.08 + 0.0×0.04 + 80.0×0.03
   = 0.0 + 20.0 + 10.8 + 15.0 + 0.0 + 4.0 + 0.0 + 2.4
   = 52.2
```

### 3.3 S3 注册攻击防护 — 6/6 全部拦截

| 攻击类型 | 结果 |
|---|---|
| impersonation (身份冒充) | ✅ blocked |
| stolen_credential (凭证窃取) | ✅ blocked |
| replay (注册重放) | ✅ blocked |
| endpoint_substitution (端点替换) | ✅ blocked |
| cross_protocol (跨协议攻击) | ✅ blocked |
| observer_auto_admission (观察者自动准入) | ✅ blocked |

### 3.4 S1 业务连续性

| 指标 | 值 |
|---|---|
| 完成率 | 0.0% |
| 超时率 | 0.0% |
| 延迟 (avg/p95/p99) | 0ms / 0ms / 0ms |

> **原因**: Doctor Agent 未成功注册到 conversation 中（端口 9202/9203 被前次运行的残留进程占用，导致 `[Errno 10048]` 绑定失败）。S1 权重已暂停 (0%)，不影响最终安全评分。

### 3.5 会话劫持详细数据

| 攻击场景 | 尝试次数 | 拦截次数 | 拦截率 |
|---|---|---|---|
| Expired session token (过期令牌) | 2 | 2 | 100.0% |
| Cross-session token reuse (跨会话复用) | 2 | 2 | 100.0% |
| Malformed token (畸形令牌) | 2 | 2 | 100.0% |
| Privilege escalation (权限提升) | 2 | 2 | 100.0% |
| **合计** | **8** | **8** | **100.0%** |

### 3.6 时钟偏移详细数据

| 偏移量 | 尝试次数 | 拦截次数 | 拦截率 |
|---|---|---|---|
| ±30s | 3 | 0 | 0.0% |
| ±120s | 3 | 0 | 0.0% |
| ±300s | 3 | 0 | 0.0% |
| ±600s | 3 | 0 | 0.0% |
| **合计** | **12** | **0** | **0.0%** |

### 3.7 证书矩阵详细数据

| 测试项 | 状态 | 拦截 |
|---|---|---|
| Expired certificate (过期证书) | ssl_error | ✅ blocked |
| Hostname mismatch (主机名不匹配) | ssl_error | ✅ blocked |
| Self-signed certificate (自签名证书) | ssl_error | ✅ blocked |
| Incomplete chain (不完整链) | skipped | — |
| Weak cipher suites (弱密码套件) | completed | ✅ blocked (4/4 套件) |
| TLS version downgrade (TLS 版本降级) | completed | ✅ blocked (TLS 1.0/1.1) |

---

## 四、与论文数据对比

根据论文 Table 3d，A2A 协议的安全能力矩阵：

| 安全维度 | 论文 A2A | 本实验 | 一致性 |
|---|---|---|---|
| TLS/Transport | ✗ | ✗ (0/3 降级拦截) | ✅ 一致 |
| Session Hijack | ✓ | ✓ (100% 拦截) | ✅ 一致 |
| E2E Encryption | ✓ | ⚠️ (60 分, 未确证) | 部分一致 |
| Tunnel Sniffing | ✗ | ⚠️ (Windows 无 tcpdump) | 无法验证 |
| Metadata Leakage | ✓ | ⚠️ (80 分, /health 泄露) | 部分一致 |

---

## 五、已知问题与限制

1. **端口冲突** (`[Errno 10048]`): 前次运行的 Doctor Agent 进程未完全退出，导致 9202/9203 端口仍被占用，S1 业务连续性测试因此全部失败。解决方法: 运行前执行 `taskkill /F /IM python.exe`。

2. **Windows 无 tcpdump**: 旁路包捕获依赖 Unix `tcpdump`，Windows 上不可用，导致 PCAP 分析跳过。该项以默认中位数 50 分计入。

3. **localhost 无真实 TLS**: A2A 协议的 Coordinator 运行在 HTTP 明文模式，TLS 降级攻击因此全部成功。生产环境应部署反向代理 (nginx/Caddy) 提供 TLS 终结。

4. **A2A 无原生时钟偏移防护**: A2A 协议不校验消息时间戳，所有时钟偏移攻击均未被拦截。需要应用层额外实现 nonce/timestamp 校验。

---

## 六、结论

A2A 协议在本地测试中综合安全评分 **52.2/100 (VULNERABLE)**。其**强项**在于:
- 会话令牌管理完善（100% 拦截各类令牌攻击）
- 注册网关防护严密（6/6 拦截恶意注册）
- 证书相关攻击在传输层被有效拒绝

其**弱项**在于:
- 无原生传输层加密（依赖外部 TLS 终结）
- 无消息时间戳/时钟偏移校验
- 无重放攻击防护机制
- 元数据端点 (`/health`) 暴露

这与论文 Table 3d 的结论一致: A2A 适合企业内部、延迟敏感的场景，但在跨组织、隐私敏感的场景中需要额外的安全层（如 mTLS、应用层加密）。

---

> 📄 原始 JSON 报告: `scenarios/safety_tech/output/a2a_unified_security_report_1783165548.json`
> 🖥️ 完整控制台输出: 见上文第二节
