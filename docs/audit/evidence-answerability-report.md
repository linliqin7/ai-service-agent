# Evidence + Answerability Gate Report

## 1. Baseline

- 阶段：Phase 2B-2，仅实现 Evidence 与确定性 Answerability Gate。
- 开始时工作区 clean；HEAD 为 `d8d3151`（架构文档提交），业务基线为 `0b3264bf7de0f4170b1d3a96d57deba9ed555be4`。
- 修改前完整测试：66 passed，0 failed / skipped / errors。
- 全程使用已有本地环境、模拟数据与 fake planner；没有联网、真实 LLM 或真实金融服务调用，没有安装或升级依赖。
- 本报告与实现同属本地提交 `feat: add evidence and answerability gate`。为避免在文件中写入不可能自洽的所属提交哈希，完整 hash 以 Git 对本报告的记录为准：`git log -1 --format=%H -- docs/audit/evidence-answerability-report.md`。交付回复另提供实际 hash。

## 2. Evidence Model

`app/schemas.py` 新增类型化 `Evidence`，仅允许 `business_fact`、`knowledge` 两种 kind。

字段为 `evidence_id`、`task_id`、`kind`、`source`、`source_id`、`version`、`valid_from`、`valid_to`、`audience`、`scope`、`content`、`verified`、`supports`、`entity_binding`、`conflict_key`。`verified` 默认 false，未知字段被拒绝。

采用最小 task-local 列表：`TaskState.evidence`。每个证据还显式携带 task_id，gate 再次核对；没有全局 registry 或新数据库。切换任务不继承证据，同一任务的新一轮也重新取得证据，避免重用过时业务事实。

SupportKey 使用有限类型：PUBLIC_DEFINITION、ACCOUNT_STATUS、ACCOUNT_BALANCE、RISK_LEVEL、HOLDING_LIST、ORDER_STATUS、ORDER_REASON、ORDER_RULE、PROFILE、QUALIFICATION_RULE。没有模型生成事实类型。

## 3. Evidence Validation

`app/runtime/evidence.py` 提供两个晋升入口。

- `business_evidence()`：只处理已有受控工具名称，复用工具参数 schema，核对认证与本地账户存在性、错误结果、订单 ID、订单归属、板块参数及有效时间。订单绑定 user_id + order_id；账户事实绑定当前认证用户。缺少原因的订单仍可提供 ORDER_STATUS，但不能提供 ORDER_REASON。
- `knowledge_evidence()`：必须通过现有 `governance.current(..., audience='public')`，具有非空 source_id，满足发布时间、review_status、audience 和 direct_answer。复用现有 lexical search 检查匹配，订单、资金知识限制到对应 domain。

现有知识 schema 用 `review_status='retired'` 表达非活跃；draft、retired、staff、过期、direct_answer=false、无 ID 都不能晋升。没有另建治理规则。多个候选逐条验证，保留能交给 gate 判断的冲突内容。

业务结果经 Engine 的受控 execute 后才调用晋升入口。Planner 只能提出 tool/action/args，不能直接写 Evidence 或 verified。无显式 user_id 的账户工具结果依赖现有 executor 的认证查询边界；这不是签名证明或真实券商数据验证。

知识工具返回的不可用记录会在传给下一次 planner、工具 trace 和响应前过滤。最终业务 render 使用选中的已验证证据，citations 只取当前任务且实际进入回答的知识记录。

## 4. Answerability Model

新增 `AnswerabilityDecision`：task_id、status、required_supports、satisfied_supports、missing_supports、evidence_ids、next_action、reason_code、evaluated_at。

TaskState 保存最终 decision，AgentResponse 增加可选 `answerability`；原响应字段及生命周期 TaskStatus 的含义不变。没有把 sufficient、need_auth 或工具错误变成长生命周期 TaskStatus。

| Status | Action | 本阶段含义 |
| --- | --- | --- |
| sufficient | answer | 所需支持被当前可用证据覆盖 |
| missing_user_information | clarify | 缺订单号、板块或认证信息 |
| missing_business_evidence | retrieve / handoff | 执行前可取证；最终仍缺证据或执行失败则交接 |
| conflicting_evidence | handoff | 不自动选择冲突来源 |
| expired_or_unusable_evidence | retrieve / handoff | 证据过期、不可用或跨任务且支持不足 |
| unauthorized | handoff | 归属/认证拒绝，保留当前产品的本地交接行为 |
| unsafe | reject | 复用安全 policy |
| out_of_scope | clarify / handoff | unknown 首次澄清，重复或不支持任务交接 |

用户明确要求人工时沿用已有早退出，answerability 为 null，不制造 sufficient。输出安全检查触发时保留现有响应 handoff，同时记录 unsafe/reject 决策。

## 5. Deterministic Decision Rules

`app/runtime/answerability.py` 用小型 REQUIRED mapping 与 `evaluate()` 完成规则判断，无模型裁判、无新增模型调用。

依次检查安全策略、明确权限错误、任务类型/终止状态、必需用户实体、认证、执行失败、证据 task_id/verified/时间/source/audience/governance、资源绑定、支持覆盖与冲突。

同 kind、同 conflict_key 的已验证可用证据若内容不同，返回 conflicting_evidence。业务事实按规范化 JSON 比较；知识按正文比较，避免仅版本号或评分变化产生内容冲突。不能比较出跨 conflict_key 的语义矛盾。

订单解释要求 ORDER_STATUS + ORDER_REASON；仅查状态要求 ORDER_STATUS。ORDER_REASON 只能来自该订单工具的非空 reason。ORDER_RULE 是补充解释，不能作为个人未成交原因。当前 fixture 没有结构化“规则触发条件与本人订单相符”的字段，因此本阶段不从知识推导原因，不伪造因果绑定。

余额 0 和空持仓是有效事实，不能误当成无数据。执行前 retrieve 只记录为 preflight；不创建无限重试。最终执行失败明确为 handoff，避免先成功取证、随后失败却残留 sufficient。

## 6. Engine Integration

`Engine.handle()` 在原有分类/检索确定最终 intent 后选择当前任务，再清空本轮旧 evidence/decision。这样 unknown 不会因临时 rules 意图在每轮被重建，原 clarification count 得以延续。

公共知识路径：原 retriever → 晋升知识 → gate → FAQ/抽取/已有 grounded generation。证据不充分时不调用 grounded；异常抽取 fallback 也需要已有 sufficient 决策。

`Engine._diagnose()`：记录取证前 preflight → 原工具执行/归属检查 → observation 晋升 → 原有 loop → 最终 gate → `render_facts()`。业务事实不足不能通过 planner 的 answer 动作绕过检查；planner 的自由回答文本不作为事实。

返回前再检查 answered 必须 sufficient；非 answered 清空 citations。trace 保存最终 decision 和 evidence IDs。没有改写 Router、Retriever、Agent Loop 调度协议或 API 实现。

`tools.render_facts()` 仅补充订单缺 reason/next 时的明确未知提示，使合法的状态查询可以回答；原因查询在进入 render 前被 gate 拦截。

持久化继续走已有 Store 的 SessionState JSON 序列化，因此 active_task 内的 evidence/decision 随原会话载荷保存。没有新增表、registry、历史任务或持久化架构；pending_slots 兼容路径继续保留。

## 7. Canonical Tasks

| Task | 必需输入/工具 | 支持与成功条件 | 不足时 |
| --- | --- | --- | --- |
| 公共知识解释（rules） | 原检索，public 当前知识 | PUBLIC_DEFINITION，治理与现有词项匹配通过 | clarify 或 handoff |
| 本人账户（account） | 认证、get_account | ACCOUNT_STATUS，当前用户业务字段完整 | need_auth/clarify 或 handoff |
| 资金/风险/持仓 | 原认证及对应工具 | ACCOUNT_BALANCE / RISK_LEVEL / HOLDING_LIST | handoff，不补造明细 |
| 资格核对 | 板块、认证、get_profile + get_rule | PROFILE + QUALIFICATION_RULE | clarify/need_auth/handoff |
| 订单状态 | order_id、认证、get_order_detail | ORDER_STATUS、归属校验 | clarify/need_auth/handoff |
| 订单原因解释 | 上述输入及对应 reason | ORDER_STATUS + ORDER_REASON；若检索知识，只作为已治理规则补充 | missing_business_evidence → handoff |
| 风险拒答 / 人工请求 | 现有 policy | 确定性拒答 / 明确交接 | 不进入普通问答完成路径 |

简单任务继续保持确定性 workflow；订单等已有路径兼容 fake/已有 planner，没有强制 Agent。

## 8. Bad Cases

- **只有 NOT_FILLED，没有 reason**：先澄清订单号，再取得 status-only 结果；最终 missing_business_evidence / handoff，不输出资金、价格、流动性等猜测。
- **相关但不足**：订单定义只产生 ORDER_RULE；即使 fake planner 提议“因为资金不足”，仍缺 ORDER_REASON，不能 sufficient。
- **跨任务污染**：ORD1001 任务切换基金问题后，新的 task_id、证据与回答不携带 ORD1001；手动把旧 evidence 放进新 task 也被 gate 拒绝。
- **治理绕过**：直接 monkeypatch 原始检索为 staff/draft/expired/direct_answer=false，仍不能回答；staff 工具 observation 不发送给下一次 planner。
- **冲突**：同一事实或同标题知识内容冲突时 handoff；知识冲突不能通过生成失败 fallback 重新回答。
- **执行失败**：工具成功后重复调用、或后续搜索返回错误，都不能保留 sufficient。后一个测试先真实复现为 FAIL，再修正错误分支，保留回归测试。

## 9. Tests

最终运行：`.venv/bin/python -m pytest -q`

| 测试组 | 结果 |
| --- | --- |
| 原有测试（未修改） | 66 passed |
| tests/test_evidence.py | 16 passed |
| tests/test_answerability.py | 31 passed |
| 合计 | **113 passed** |

0 failed、0 skipped、0 errors；本次耗时 0.28s。保留两个已有 Starlette/httpx 与 AnyIO 弃用 warning，没有为消除 warning 升级依赖。

覆盖全部八类 decision、五种 next_action、六类 canonical 输入、治理、权限、冲突、任务隔离、缺失原因、相关但不足、fake planner、生成前 gate、工具失败与原有 clarification 行为。新增测试不使用真实网络/模型/金融服务，临时数据使用 monkeypatch，不修改正式知识 JSON 或原始数据库。

## 10. Evaluation

运行：`PYTHONPATH=. .venv/bin/python eval/run.py`

| 数据集 | 结果 |
| --- | --- |
| main | 49/49 |
| holdout | 18/18 |
| answerability | 9/9 |

新增 `eval/answerability.json` 为合成契约案例，包含 label、required_supports、expected_next_action、稳定 evidence source IDs 及污染禁止项。运行结果另记录实际 evidence UUIDs。缺原因情形仅在该 case 的工具 wrapper 中暂时裁剪结果，不修改正式 fixture。

`eval/report.json` 为重新生成的本地合成运行产物，无真实用户数据。保留原有 `splits` 两项结构，新增顶层 `answerability`，避免现有前端将 V2 数据误当成 holdout。任意评测失败时脚本退出非零。

这些指标验证 deterministic fixture workflow 与支持契约，不是模型准确率，不证明真实交易诊断能力或任意自然语言的语义完备性。

额外检查：`.venv/bin/python -m compileall -q app tests eval`、`git diff --check` 均通过。

## 11. Files Changed

| 文件 | 变更 |
| --- | --- |
| app/schemas.py | Evidence、AnswerabilityDecision 与可选集成字段 |
| app/runtime/evidence.py | 新增证据晋升与受限渲染输入 |
| app/runtime/answerability.py | 新增确定性 required supports / gate |
| app/runtime/engine.py | 任务选择位置、证据收集、最终 gate、trace、失败保护 |
| app/runtime/tools.py | 订单缺失原因/下一步的明确提示 |
| tests/test_evidence.py | 新增 16 项用例 |
| tests/test_answerability.py | 新增 31 项用例 |
| eval/answerability.json | 新增 9 项合成契约 |
| eval/run.py | 新增 V2 评测，保持原报告结构兼容 |
| eval/report.json | 刷新合成离线结果 |
| docs/audit/evidence-answerability-report.md | 本报告 |

未修改任何已有测试、正式知识库、Router、policy、RAG、API 或 web；无新依赖、远程仓库或发布动作。

## 12. Remaining Limitations

- 当前验证是受控进程内 provenance，不防范任意服务端代码直接伪造 Evidence；外部模型没有此写入接口。
- 公共知识的充分性仍基于已有 lexical relevance + 治理 + PUBLIC_DEFINITION，不能判定任意复杂问题的全部子目标。已明确阻止的是“公共定义冒充个人订单原因”。
- 原因非空仅证明来源返回了 reason。ORD1001 的现有取消说明含有未知边界；sufficient 允许如实转述已知信息，不表示已经证明最初未成交的市场原因。
- 不从自然语言规则生成个人因果结论；以后若支持规则推因，必须新增可验证的适用条件与订单绑定，而不能仅放宽 supports。
- 冲突比较是结构/正文差异，不做跨主题语义矛盾分析；可能对同义改写采取保守交接。
- 原 Retriever 自身可能先抑制冲突或无效记录并返回空集；此时现有路由可表现为 unknown/澄清，而非细分 conflict/expired。它仍不会形成有效 Evidence 或 answered。
- 保留现有任务关系、登录续办及 pending_slots；不实现复杂实体纠正关系、历史任务或并行任务。每轮重新取证，不跨轮缓存。
- Adapter/gate 单元测试使用固定 as_of；端到端和已有评测仍依赖正式演示 fixture 的有效期（部分到 2027 年），将来过期会按治理失败，不能把本次通过率当成永久保证。
- API 新增可选 decision，无 UI 改造；preflight 的 retrieve 是受限执行前建议，不是新增自主搜索循环。

## 13. V2 Next Step

后续可单独评审更细的公共知识 support coverage、结构化规则适用条件、任务关系边界与固定时钟测试。这些仅为候选，本阶段未实现。

本阶段止于可测试的 task-bound Evidence 与 deterministic Answerability Gate；不引入 LangGraph、Multi-Agent、Vector DB、Reranker、MCP、Long-term Memory、新数据库、新模型或真实金融连接。不创建 GitHub remote、不 push。
