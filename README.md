# ProtocolBench — ACPs vs A2A 协议安全对比实验

> **实验室**: AIP-PUB (北京邮电大学智能体互联协议)
> **被测协议**: ACPs v2.1.0 vs A2A (a2a-sdk 0.3.3)
> **基准框架**: ProtocolBench (ulab-uiuc/AgentProtocols, ICML 2026)
> **LLM**: DeepSeek V4 Pro
> **实验日期**: 2026-07-04 ~ 2026-07-11

---

## 一、项目概述

将北邮 ACPs 协议接入 ProtocolBench 基准测试框架，在 Safety Tech 安全场景下与 A2A 协议进行全面对比。ProtocolBench 是 UIUC 发表在 ICML 2026 的多 Agent 通信协议评测基准，覆盖四个场景（GAIA / Safety Tech / Streaming Queue / Fail-Storm Recovery）。

## 二、实验结果 (ACPs mTLS vs A2A HTTP)

| 指标 | A2A (HTTP) | ACPs (mTLS) | ACPs 优势 |
|---|---|---|---|
| **S1 业务连续性** | 100.0/100 | **100.0/100** | 持平 |
| **S1 平均延迟** | 11,733ms | 18,734ms | A2A 更快 (TLS overhead) |
| **S2 TLS 降级拦截** | 0/3 (0%) | **3/3 (100%)** | **+100%** |
| **S2 会话劫持拦截** | 0/8 (0%) | **8/8 (100%)** | **+100%** |
| **S2 重放攻击拦截** | 0/2 (0%) | **2/2 (100%)** | **+100%** |
| **S2 综合安全分** | 52.2/100 | **62.2/100** | **+19.2%** |
| **S3 注册攻击拦截** | 6/6 (100%) | 6/6 (100%) | 持平 |

**核心结论**: ACPs 在传输安全（TLS 降级 100% 拦截）和身份认证（会话劫持 100% 拦截）维度碾压 A2A。ACPs 当前使用自签名证书，若启用完整 ATR CA 体系，S2 理论可达 90+ 分 (SECURE 级别)。

## 三、目录结构

```
├── README.md                          # 本文件
├── reports/                           # 6 份实验报告
│   ├── Safety_Tech_A2A_实验报告.md              # A2A v1 (S1 未修复)
│   ├── Safety_Tech_A2A_实验报告_v2_S1修复版.md    # A2A v2 (S1 修复完整版)
│   ├── GAIA_A2A_实验报告.md                     # GAIA 多Agent 协作
│   ├── GAIA_Task2_DeepSeek_JSON稳定性测试.md      # DeepSeek JSON 问题验证
│   ├── ACPs_A2A_SafetyTech_对比实验报告.md         # ACPs HTTP vs A2A
│   └── ACPs_mTLS_SafetyTech_实验报告.md           # ACPs mTLS 最终版 ★
├── acps-adapter/                      # ACPs 协议适配器 (新增代码)
│   ├── protocol_backends/acps/
│   │   ├── __init__.py                # 自动注册到 protocol registry
│   │   ├── client.py                  # send / spawn / register / health
│   │   ├── server.py                  # AIP RPC 服务端 (FastAPI + /rpc + /health)
│   │   └── registration_adapter.py    # ATR 风格注册适配器
│   ├── runners/
│   │   └── run_unified_security_test_acps.py  # ACPs Safety Tech Runner
│   └── framework-patches/             # 需要修改的框架文件 (含修改说明)
│       ├── registration_gateway.py    # +_verify_acps 验证器
│       ├── backend_api.py             # +acps 到 import 列表
│       ├── llm_wrapper.py             # +deepseek 模型名检测
│       ├── s1_business_continuity.py  # +wait_for 尾消息余量
│       ├── s1_config_factory.py       # light 模式参数调整
│       ├── rg_coordinator.py          # +超时参数
│       ├── a2a_client.py              # (参考 - A2A 原始版本)
│       ├── run_unified_security_test_a2a.py  # (参考 - A2A Runner)
│       ├── browser_use_tool.py        # headless 模式修复
│       ├── gaia_a2a.yaml              # DeepSeek 配置
│       └── gaia_general.yaml          # DeepSeek 配置
└── certs/                             # mTLS 测试证书
    ├── ca.pem / ca.key                # 自签名 CA
    ├── server-doctor_a.pem / .key     # Doctor A 服务端证书
    ├── server-doctor_b.pem / .key     # Doctor B 服务端证书
    ├── client.pem / .key              # 客户端证书 (双向认证)
    └── trust-bundle.pem               # CA 信任链 (仅公钥)
```

## 四、复现步骤

### 4.1 环境

```bash
# ProtocolBench
cd AgentProtocols-main
conda create -n map python==3.11 -y && conda activate map
pip install -r requirements.txt

# ACPs SDK
cd ACPs-community-main/acps-sdk
pip install -e .

# 生成测试证书
cd scenarios/safety_tech/certs
python generate_certs.py  # 或使用 archive/certs/ 中预生成的证书
```

### 4.2 配置 LLM

```bash
# macOS/Linux
export OPENAI_API_KEY="sk-your-key"
export OPENAI_BASE_URL="https://api.deepseek.com/v1"

# 或编辑各 config/*.yaml 中的 api_key
```

### 4.3 运行

```bash
# ACPs mTLS 模式 (HTTPS)
PYTHONIOENCODING=utf-8 \
D:/conda_envs/map/python.exe \
  -m scenarios.safety_tech.runners.run_unified_security_test_acps

# ACPs HTTP 模式
ACPS_USE_TLS=false \
PYTHONIOENCODING=utf-8 \
D:/conda_envs/map/python.exe \
  -m scenarios.safety_tech.runners.run_unified_security_test_acps

# A2A 对比基线
PYTHONIOENCODING=utf-8 \
D:/conda_envs/map/python.exe \
  -m scenarios.safety_tech.runners.run_unified_security_test_a2a
```

### 4.4 安装 ACPs 适配器

将 `acps-adapter/` 下的文件复制到 ProtocolBench 对应位置：

```bash
cp -r acps-adapter/protocol_backends/acps \
      AgentProtocols-main/scenarios/safety_tech/protocol_backends/
cp acps-adapter/runners/run_unified_security_test_acps.py \
   AgentProtocols-main/scenarios/safety_tech/runners/
cp acps-adapter/framework-patches/*.py \
   AgentProtocols-main/scenarios/safety_tech/core/  # 覆盖原有文件
cp certs/* \
   AgentProtocols-main/scenarios/safety_tech/certs/
```

## 五、框架修改清单

为使 ACPs 和 DeepSeek 在 ProtocolBench 上正常运行，修改了以下框架文件：

| 文件 | 修改内容 | 原因 |
|---|---|---|
| `registration_gateway.py` | +`_verify_acps` 验证器, +`timezone` import, +ACPs 验证器注册 | ACPs 协议验证 |
| `backend_api.py` | +`acps` 到 protocols_to_import | ACPs 后端发现 |
| `llm_wrapper.py` | +`deepseek` 模型名检测 | DeepSeek 替换 gpt-4o |
| `s1_business_continuity.py` | wait_for timeout +20s 余量 | LLM 尾消息不被截断 |
| `s1_config_factory.py` | light 模式参数 (25s, 1 RPS) | 适配 LLM 延迟 |
| `rg_coordinator.py` | 超时 35→65s | LLM 调用链路 |
| `a2a_client.py` | 超时 30→60s | LLM 调用链路 |
| `run_unified_security_test_a2a.py` | registration status 检查, key 路径修复 | S1 注册失败检测 |
| `browser_use_tool.py` | Windows 强制 headless | browser-use + pydantic 兼容 |
| `gaia_a2a.yaml` | model → deepseek-v4-pro | DeepSeek 配置 |
| `gaia_general.yaml` | model/llm → deepseek-v4-pro | DeepSeek 配置 |

## 六、未完成的工作

| 项目 | 状态 | 阻塞原因 |
|---|---|---|
| S2 mTLS 满分 (90+) | ⚠️ 62.2/100 | 需 ACPs ATR CA 完整部署 |
| S1 standard 模式 | ❌ 未跑 | DeepSeek 并发限速 |
| Fail-Storm 场景 | ❌ 未开始 | 需写 ~1000 行新 adapter |
| Streaming Queue 场景 | ❌ 未开始 | 需写 ~200 行新 adapter |
| GAIA with ACPs | ❌ 未开始 | 需换支持 JSON mode 的 LLM |
| ACP / ANP / Agora 对比 | ❌ 未开始 | 需分别为每个协议写 adapter |

## 七、引用

- ProtocolBench: [ulab-uiuc/AgentProtocols](https://github.com/ulab-uiuc/AgentProtocols)
- ACPs: [AIP-PUB/ACPs-community](https://github.com/AIP-PUB/ACPs-community)
- 论文: *ProtocolBench: Which LLM MultiAgent Protocol to Choose?* (ICML 2026)

---

> 实验人: AIP-PUB 实验室
> 实验日期: 2026-07-04 ~ 2026-07-11
