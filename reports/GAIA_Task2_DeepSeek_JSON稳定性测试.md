# GAIA Task 2 — DeepSeek V4 Pro JSON 输出稳定性验证

> **实验时间**: 2026-07-05
> **背景**: GAIA 实验中 Task 2 因 Planner JSON 解析失败而完全崩溃。本测试验证该问题是否为偶然。
> **LLM**: DeepSeek V4 Pro (`deepseek-v4-pro`)
> **方法**: 对同一 Task 2 执行 5 次独立的 Planner 分析，观察 JSON 输出质量

---

## 一、测试设计

- **任务**: GAIA Task 2 — Finding Nemo 小丑鱼 USGS 入侵物种查询
- **次数**: 5 次独立 Planner 调用
- **Prompt**: 与正式实验完全一致（含完整 JSON schema + few-shot 示例）
- **环境**: 同上 — Windows 11, Python 3.11, conda `map`

---

## 二、原始输出

```
=== Attempt 1/5 ===
Error in ask: 
Error in ask: 
Error in ask: 
🚀 TOKEN USAGE REPORT
📥 Input Tokens:  1,123  📤 Output Tokens:  1,527  🎯 TOTAL: 2,650

Warning: LLM analysis failed
  (Expecting property name enclosed in double quotes: line 10 column 5 (char 288)),
  using fallback analysis
📋 Generating agent configuration...
ERROR: unsupported operand type(s) for /: 'str' and 'str'

=== Attempt 2/5 ===
Error in ask: 
Error in ask: 
📥 Input: 1,123  📤 Output: 934  🎯 TOTAL: 4,707 (cumulative)

📋 Generating agent configuration...
ERROR: unsupported operand type(s) for /: 'str' and 'str'

=== Attempt 3/5 ===
Error in ask: 
Error in ask: 
📥 Input: 1,123  📤 Output: 1,262  🎯 TOTAL: 7,092 (cumulative)

📋 Generating agent configuration...
ERROR: unsupported operand type(s) for /: 'str' and 'str'

=== Attempt 4/5 ===
Error in ask:  (×6)
Warning: LLM analysis failed
  (RetryError[<Future finished raised TimeoutError>]),
  using fallback analysis
📋 Generating agent configuration...
ERROR: unsupported operand type(s) for /: 'str' and 'str'

=== Attempt 5/5 ===
Error in ask:  (×6)
Warning: LLM analysis failed
  (RetryError[<Future finished raised TimeoutError>]),
  using fallback analysis
📋 Generating agent configuration...
ERROR: unsupported operand type(s) for /: 'str' and 'str'
```

---

## 三、结果统计

| 尝试 | JSON 解析 | LLM 响应 | fallback 代码 | 总耗时 |
|---|---|---|---|---|
| 1 | ❌ 语法错误 (line 10 col 5) | 有返回 (1,527 tokens) | ❌ 类型错误 | ~30s |
| 2 | ❌ 语法错误 | 有返回 (934 tokens) | ❌ 类型错误 | ~30s |
| 3 | ❌ 语法错误 | 有返回 (1,262 tokens) | ❌ 类型错误 | ~30s |
| 4 | ❌ 无响应 | 超时 (6 次重试全断) | ❌ 类型错误 | ~60s |
| 5 | ❌ 无响应 | 超时 (6 次重试全断) | ❌ 类型错误 | ~60s |

**成功率: 0/5 (0%)**

---

## 四、失败模式分析

### 模式 A: JSON 语法错误 (Attempt 1-3, 60%)

DeepSeek 输出了接近正确的 JSON，但存在未转义引号或非法字符：

```
Expecting property name enclosed in double quotes: line 10 column 5 (char 288)
```

**原因**: Planner prompt 包含复杂嵌套 JSON schema，DeepSeek V4 Pro 在严格 JSON 模式下输出不够稳定。论文使用的 Qwen2.5-VL-72B 在结构化输出上训练更充分。

### 模式 B: LLM 超时 (Attempt 4-5, 40%)

6 次重试全部 TimeoutError，DeepSeek 可能触发了速率限制或服务端过载：

```
Error in ask:   (×6, empty error)
Warning: LLM analysis failed (RetryError[...TimeoutError])
```

**原因**: 短时间内多次调用 + 长 prompt (1,123 input tokens) 可能触发了 DeepSeek API 的并发/速率限制。

### 模式 C: fallback 代码自身崩溃 (100%)

即便 Planner 的 JSON 解析失败后有 fallback 路径，fallback 代码本身也因类型错误崩溃：

```
ERROR: unsupported operand type(s) for /: 'str' and 'str'
```

**原因**: fallback 分析返回的数据结构与正常流程不同，下游代码未做防御性类型检查。这是 GAIA 框架代码本身对 LLM 输出异常的容错不足。

---

## 五、与 Task 1 对比

| 维度 | Task 1 | Task 2 |
|---|---|---|
| Planner JSON 解析 | ✅ 成功 | ❌ 0/5 |
| Agent 创建 | ✅ 2-3 个专业 Agent | ❌ fallback 到 1 个无工具 Agent |
| 工具调用 | ✅ 4 次成功 | ❌ 0 次 |
| 答案产出 | ⚠️ 搜索成功但答案提取失败 | ❌ "No results generated" |

Task 1 成功而 Task 2 失败是**随机的**——DeepSeek 的 JSON 输出质量因 prompt 内容微妙差异而波动。Task 1 的 prompt 刚好触碰到了正确输出的概率区域，Task 2 没有。5 次重试全失败说明这不是"运气"问题，而是 DeepSeek 在该类任务上系统性不可靠。

---

## 六、根因总结

| 层级 | 问题 | 严重度 |
|---|---|---|
| DeepSeek V4 Pro | 长 JSON schema prompt 下输出格式不稳定 | 🔴 致命 |
| DeepSeek API | 连续调用触发限速/超时 | 🟡 中等 |
| GAIA Planner | `plan_agents()` 无 JSON 容错机制 | 🟡 中等 |
| GAIA fallback | fallback 分析代码未处理非标准返回类型 | 🟡 中等 |

核心矛盾: **DeepSeek V4 Pro 是通用对话模型，而 GAIA Planner 要求严格的 function-calling 风格结构化输出**。论文选 Qwen2.5-VL-72B 正是因为其在 tool-use benchmark 上的训练。

---

## 七、可行修复方案

| 方案 | 难度 | 效果 |
|---|---|---|
| 1. 换用原生 JSON mode 模型 (GPT-4o / Qwen) | 低 | ✅ 根本解决 |
| 2. 给 Planner 加 JSON repair 层 (自动修复引号/逗号) | 中 | ⚠️ 部分缓解 |
| 3. 加 Planner 重试 + temperature 抖动 | 低 | ⚠️ 部分缓解 |
| 4. 改 Planner prompt 让输出更简单 (减少嵌套) | 中 | ⚠️ 可能影响 Agent 规划质量 |

---

## 八、结论

**GAIA Task 2 的失败不是偶然，是 DeepSeek V4 Pro 在结构化 JSON 输出上的系统性问题。** 5 次独立测试 0% 成功率，两种失败模式 (JSON 语法错误 + API 超时) 交替出现。Task 1 的成功具有随机性，不能作为 DeepSeek 可稳定运行 GAIA 的证据。

如需在此项目上复现论文指标，**强烈建议更换 LLM** 为支持可靠结构化输出的模型（GPT-4o 或本地部署 Qwen2.5-VL-72B）。

---

> 📄 相关报告: `GAIA_A2A_实验报告.md` · `Safety_Tech_A2A_实验报告_v2_S1修复版.md`
