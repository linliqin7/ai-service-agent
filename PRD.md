# AI Service Agent PRD v1.0 — 证券经纪客户服务场景

更新日期：2026-09-19

## 1. 产品概述

AI Service Agent 是一个面向任务型客户服务场景的 AI Agent 原型系统，证券经纪客户服务是第一验证场景。

产品不把目标限定为“回答问题”。它在受边界约束的知识、工具和证据之上，判断用户正在完成什么任务、已经确认了什么、还缺什么，以及当前依据是否足以完成任务；然后选择回答、追问、拒绝或转人工。

```text
User Goal
  → Task State
  → Knowledge / Controlled Tools
  → Evidence
  → Answerability
  → Answer / Clarify / Reject / Handoff
```

## 2. 产品定位

**产品本体**：AI Service Agent，一个为强知识、强任务状态、强边界服务场景设计的原型。

**第一验证场景**：证券经纪客户服务，覆盖公共规则解释、本人模拟账户信息、订单状态诊断、风险请求与本地人工交接。

**长期方向**：将经过验证的任务状态、证据和充分性机制扩展到其他合规要求高、需要受控知识或业务工具的服务场景。证券经纪不是产品唯一身份，也不意味着项目已经具备跨行业或生产能力。

## 3. 问题与用户价值

任务型客服的难点不只是语言理解。同一个词可能对应公共解释、本人状态查询或异常诊断；后两类问题需要身份边界、具体实体和受控事实。仅检索到相关资料，也不意味着它能支持完成用户任务。

本项目验证以下产品假设：

1. 先识别用户目标和当前任务，比先生成答案更可靠。
2. 本人业务事实应来自受控工具并与当前认证身份、实体和任务绑定。
3. 相关证据必须经过充分性判断，不能被当作完整答案的理由。
4. 无法确认时，系统应明确追问、拒绝或转人工，不能补造业务事实。

当前项目没有真实客服日志、生产用户数据或商业 ROI 数据，不对市场规模、人工节省、一次解决率或客户满意度作出结论。

## 4. 核心任务机制

### Task State

系统维护一个 active task，而不是把每个用户消息都视为独立问答。Task State 记录任务类型、目标、实体、必需与缺失槽位、生命周期状态、澄清次数和结束原因。

```text
User Goal
  → Task State
  → Required Information
  → Current Evidence
  → Answerability
  → Next Action
```

任务可处于 `new`、`clarifying`、`executing`、`completed`、`handoff`、`rejected` 或 `abandoned`。用户补充订单号等信息会继续当前任务；识别到明确新目标时，旧任务会结束并创建新的 active task。

### Evidence

Retrieved Evidence ≠ Sufficient Evidence。检索到相关资料，不等于已经拥有足以完成任务的依据。

- **Knowledge evidence**：来自通过版本、有效期、受众、审核状态与 direct-answer 规则验证的知识记录。
- **Business fact evidence**：来自受控工具并经过参数、认证、资源归属与实体绑定检查的模拟业务事实。

证据必须绑定当前 task。旧任务的订单或账户证据不能被新任务继承；模型产生的文字不是事实来源。

### Answerability

Answerability 是产品的最终决策机制，判断当前 task 的必要支持是否由可用证据覆盖。当前状态为：

| Status | Next action |
|---|---|
| `sufficient` | answer |
| `missing_user_information` | clarify |
| `missing_business_evidence` | retrieve 或 handoff |
| `conflicting_evidence` | handoff |
| `expired_or_unusable_evidence` | retrieve 或 handoff |
| `unauthorized` | handoff |
| `unsafe` | reject |
| `out_of_scope` | clarify 或 handoff |

例如，订单状态为“未成交”但工具没有返回个人原因时，公共“未成交是什么意思”的定义只能作为相关知识，不能被用来推断该用户订单的具体原因。

## 5. 产品边界

1. **Task First**：先判断用户试图完成的任务，再决定处理路径。
2. **Evidence First**：回答必须有可追溯的知识或业务事实依据。
3. **Deterministic First**：身份、权限、归属、事实、有效期和风险边界优先由确定性逻辑控制。
4. **Simple When Possible**：稳定的简单任务采用确定性流程，不为演示而增加复杂 AI 基础设施。
5. **Fail Safely**：证据不足、冲突、过期或越权时，不猜测，选择追问、拒绝或交接。
6. **Evaluate Before Expanding**：先在受控离线场景验证机制，再考虑扩大能力范围。

## 6. 当前版本边界

- Task State 与澄清生命周期。
- 受治理的知识检索与公共知识引用。
- 白名单只读工具、参数校验、模拟身份与订单归属检查。
- task-bound knowledge evidence 与 business fact evidence。
- 确定性的 Answerability Gate。
- 回答、追问、风险拒答和本地演示人工交接。
- trace、citation、处理记录与本地演示界面。
- pytest / TestClient 与受控 fixture 上的离线评测。

## 7. 评估

当前 release validation 使用 synthetic / curated / controlled fixture 上的 deterministic offline evaluation：

| Check | Result |
|---|---|
| Automated tests | 113 passed |
| Main evaluation | 49/49 |
| Holdout evaluation | 18/18 |
| Answerability evaluation | 9/9 |

这些结果不是 产品正确率、真实金融正确率、真实客户满意度、FCR 或生产性能指标。它们仅说明当前代码在明确的离线契约和模拟数据上满足断言。

可选外部模型集成不属于本次的验收基础；发布验证不依赖真实模型调用。

## 8. 安全与合规边界

项目只使用模拟账户、订单、资金、规则和本地演示工单。它不连接真实券商、银行、行情、客户账户或交易执行系统。

真实身份认证、生产授权、监管知识审批、数据保留、隐私治理、生产合规验证和坐席协同均不在当前范围。禁止向本地演示输入真实客户数据、账号、证件、密码、验证码或交易凭据。

## 9. 成功与停止边界

一个任务完成的最低条件是：所需用户信息齐备、所需事实或知识已验证、受众/归属/有效期符合要求，且 Answerability 为 `sufficient`。

系统在以下情形停止自动完成：用户信息缺失、业务证据缺失、证据冲突、证据不可用、权限不足、风险请求或超出范围。对应的可见出口为 clarify、retrieve、reject 或 handoff。

## 10. 未来范围

以下方向仍是 future scope，不是当前 v1.0 能力：

- 真实 broker API、生产身份认证、授权和账户/交易操作。
- 生产合规知识库、模型治理、隐私/保留制度与专业合规验证。
- 向量数据库、reranker、Multi-Agent、LangGraph、MCP、长期记忆与多渠道客服。
- 真实用户研究、生产数据分析、负载测试、FCR/满意度等生产指标。

当前设计优先证明一个可测试、可追溯、在证据不足时能安全停止的服务任务闭环。
