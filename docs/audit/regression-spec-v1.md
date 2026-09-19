# V1 Desired Behavior Regression Specification

## 1. Why These Tests Exist

上一轮 Audit 识别出四个可能影响用户任务边界、会话状态、Agent 证据链和知识治理的问题。本阶段只把这些风险表达为可重复的离线行为测试，不修改生产实现、不修改既有测试、不调用真实模型或金融服务。

新增测试文件：`tests/test_v2_regression_spec.py`。测试复用当前项目的 `Engine`、`route`、`SessionState`、fake planner、`TestClient`、RAG fixture 和 `monkeypatch` 模式。

## 2. Case 1

测试：`test_public_unfilled_definition_does_not_enter_private_order_flow`

目标行为：

- `未成交是什么意思？` 应作为公共概念解释进入 `rules`/公共知识路径，不要求登录或订单号。
- `我的订单为什么没成交？` 应作为 `order` 私人任务，缺少订单号时澄清。

实际行为：

- 公共句路由为 `order`，响应 `intent=order`、`status=clarify`，要求提供模拟订单号，并写入 `pending_slots`。
- 对照句同样路由为 `order` 并要求订单号。

结果：**FAIL**。问题已动态复现。失败位置：`tests/test_v2_regression_spec.py:42`；对应生产路由逻辑位于 `app/runtime/router.py` 的订单关键词判断，在 `public_definition()` 判断之前。

## 3. Case 2

测试：`test_successful_answer_resets_stale_clarification_context`

目标行为：

1. unknown 问题进入 clarification，计数为 1。
2. 成功回答公共知识问题后，旧 clarification 上下文清除或被正确替换。
3. 新的 unknown 问题重新从计数 1 开始，不应直接 handoff。

实际行为：

- Turn 1：`clarify`，`pending_slots={"clarifications": 1}`。
- Turn 2：`开户需要什么材料` 返回 `answered`，但仍保留 `pending_slots={"clarifications": 1}`。
- Turn 3：新的 unknown 问题直接返回 `handoff`，计数变为 2。

结果：**FAIL**。问题已动态复现。失败位置：`tests/test_v2_regression_spec.py:66`；对应状态处理位于 `app/runtime/engine.py` 的 unknown 分支及知识回答分支。

## 4. Case 3

测试：`test_agent_search_knowledge_observation_reaches_final_evidence`

目标行为：Agent planner 明确调用 `get_order_detail` 和 `search_knowledge` 后，检索结果至少应通过最终 citations、answer 中的必要事实或明确 evidence linkage 进入最终回答链路。

测试使用临时 monkeypatch 的专用知识记录 `K-REGRESSION-ORDER-RULE`，其唯一事实为“撤单后不得再次提交同一委托”。真实模型未调用。

实际行为：

- `response.observations` 包含 `get_order_detail` 和 `search_knowledge`。
- `search_knowledge` observation 内含专用知识记录。
- 最终 `response.citations` 为空，answer 只包含订单工具事实，不包含专用知识事实。

结果：**FAIL**。问题已动态复现。失败位置：`tests/test_v2_regression_spec.py:90`；对应事实渲染位于 `app/runtime/tools.py` 的 `render_facts()`，Agent 执行链位于 `app/runtime/engine.py` 的 `_diagnose()`。

## 5. Case 4

测试：`test_public_knowledge_api_filters_non_public_records`

目标行为：`GET /api/knowledge` 对普通用户只展示当前有效、已发布、public、可直接回答的知识；staff-only、draft、inactive、expired 记录不得直接返回。

测试通过 monkeypatch 注入临时记录，没有修改正式 `app/rag/fixtures/knowledge.json`。

实际行为：接口返回五条注入记录，包括：

- `K-PUBLIC-REGRESSION`
- `K-STAFF-REGRESSION`
- `K-DRAFT-REGRESSION`
- `K-INACTIVE-REGRESSION`
- `K-EXPIRED-REGRESSION`

结果：**FAIL**。问题已动态复现。失败位置：`tests/test_v2_regression_spec.py:116`；`app/api.py` 的 `/api/knowledge` 直接返回 `records()`，未调用 `app/rag/governance.py` 的 `current()` 或 `app/rag/retriever.py` 的治理过滤。

## 6. Test Results

### 新增回归测试

- 总数：4
- PASS：0
- FAIL：4
- SKIP：0
- ERROR：0

### 相关既有测试

运行：`tests/test_runtime.py tests/test_llm_loop.py tests/test_review_fixes.py tests/test_integrations.py tests/test_regressions.py`

- 42 passed
- 0 failed
- 2 个依赖弃用警告

### 完整测试套件

运行：`.venv/bin/python -m pytest -q`

- 总数：59
- passed：55
- failed：4
- skipped：0
- error：0
- 2 个依赖弃用警告

失败的 4 项全部来自新增 `tests/test_v2_regression_spec.py`；原有 55 项仍通过。

## 7. Existing Behavior vs Desired Behavior

| Case | Desired behavior | Current behavior | Result |
|---|---|---|---|
| 1 公共“未成交”解释 | 公共 rules/知识解释 | order + clarify + 要求订单号 | FAIL |
| 2 澄清上下文 | 成功回答后清除旧计数，新任务从 1 开始 | 计数保留，新 unknown 直接 handoff | FAIL |
| 3 Agent 检索证据 | search observation 进入最终 evidence chain | observation 存在但 citations/answer 丢失 | FAIL |
| 4 知识浏览治理 | 只返回 public、有效、已发布记录 | 所有 records 直接返回 | FAIL |

## 8. Confirmed Problems

以下问题均由本轮可重复、离线、无外部依赖的测试动态确认：

1. `未成交是什么意思？` 被订单路由截走并要求订单号。
2. 成功知识问答后旧 clarification counter 未清除，并污染后续任务。
3. Agent 调用 `search_knowledge` 后，检索证据未进入最终 citations 或事实回答。
4. `/api/knowledge` 返回 staff-only、draft、inactive、expired 记录。

本轮没有为使测试通过而修改任何生产代码，也没有降低断言标准。

## 9. Static-Only Findings

本轮四个目标问题均已获得动态测试证据，因此没有新增仅凭静态代码推断、但无法表达为稳定测试的问题。

测试使用固定输入、临时内存/monkeypatch 数据和本地 fake planner，不依赖真实模型、网络、真实金融数据、执行顺序或正式知识库变更。

## 10. Recommended Fix Order

本报告只记录下一阶段修复输入，不在本阶段实施修复。建议后续按以下顺序处理：

1. 先修复公共任务与私人订单任务的路由边界，并保留 Case 1 作为回归门槛。
2. 修复任务上下文/clarification 生命周期，保留 Case 2 的三轮状态断言。
3. 设计 Agent tool observation 到最终 answer/citation 的证据链接，保留 Case 3 的专用事实证明。
4. 让 `/api/knowledge` 复用知识治理过滤，保留 Case 4 的 staff/draft/inactive/expired 组合数据。
5. 修复后重新运行新增测试、相关旧测试和完整测试套件；不要删除失败测试。

本阶段确认：生产源码未修改；现有测试未修改；未安装或升级依赖；未调用真实外部 LLM；未调用真实金融服务；未修改正式知识库。
