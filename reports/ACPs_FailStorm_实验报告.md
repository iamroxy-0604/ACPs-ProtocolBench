# ACPs Fail-Storm Recovery 实验报告

> **实验时间**: 2026-07-11 19:26 (UTC+8)
> **协议**: ACPs v2.1.0 (AIP RPC)
> **LLM**: DeepSeek V4 Pro
> **环境**: Windows 11, Python 3.11 (conda env `map`)

---

## 一、实验配置

| 参数 | 值 |
|---|---|
| Agent 数量 | 8 |
| 拓扑 | 环形 Mesh |
| 总运行时间 | 600s (10 min) |
| 故障注入间隔 | 120s (每 2 分钟) |
| 每次 kill 数 | 3 / 8 (37.5%) |
| QA 数据 | 2WikiMultihopQA (8 个 shard) |
| 最大 QA 组数 | 5 |

## 二、故障注入与恢复

| 周期 | 时间 | 被 Kill 的 Agent | 恢复耗时 |
|---|---|---|---|
| 1 | 2.0 min | agent7, agent0, agent4 | **6.0s** ✅ |
| 2 | 4.0 min | agent7, agent5, agent2 | **6.0s** ✅ |
| 3 | 6.1 min | agent7, agent5, agent2 | **6.0s** ✅ |
| 4 | 8.1 min | agent4, agent1, agent7 | **6.0s** ✅ |

**4 轮故障注入全部在 6.0 秒内恢复。**

## 三、QA 任务表现

| 指标 | 值 |
|---|---|
| 总 QA 任务 | 8 |
| 成功 | 7 (87.5%) |
| 找到答案 | 6 (75.0%) |
| — 本地文档匹配 | 3 |
| — 邻居协助 | 3 |
| 平均任务耗时 | 2.59s |

## 四、已知问题

Agent 间邻居通信存在 HTTP 502 错误（httpx ↔ aiohttp 事件循环冲突），导致分布式搜索部分失败，答案主要来自本地文档匹配。

## 五、与论文对比

| 指标 | 论文 A2A | ACPs (本次) |
|---|---|---|
| 恢复时间 | 8.00s | **6.00s** |
| 故障前答案率 | 14.74% | 75.0%* |

> \* 论文使用严格 QA 评判，本实验使用宽松匹配（找到即为成功），不可直接对比

---

> 原始 JSON: `fail_storm_recovery/results/failstorm_metrics_acps_*.json`
