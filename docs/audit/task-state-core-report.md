# Task State Core Report

## 1. Baseline

本阶段开始前先执行了 `git status --short` 和完整测试。

- Git 基线：`8550732 fix: close V1 agent regression gaps`
- 工作区已有上一阶段未提交的 `docs/architecture/`，本阶段没有覆盖或修改该目录。
- V1.1 测试：59 passed、0 failed、0 skipped、0 errors。
- 现有 2 条 Starlette/httpx 与 AnyIO 弃用警告，本阶段未升级依赖。

## 2. TaskState Model

在 `app/schemas.py` 增加了最小类型化模型：

- `TaskStatus`：`new`、`clarifying`、`executing`、`completed`、`handoff`、`rejected`、`abandoned`。
- `EntityValue`：`name`、`value`、`source`、`confirmed`。source 仅允许 `user`、`system`、`tool`。
- `TaskState`：`task_id`、`task_type`、`domain`、`objective`、`entities`、`required_slots`、`missing_slots`、`status`、`clarification_count`、`completion_reason`、`created_at`、`updated_at`。
- `SessionState.active_task`：可选的当前 active task。

本阶段没有加入 observations、evidence、answerability、task history、parent/supersedes 关系或长期记忆。

订单实体遵守确认边界：用户输入的 `ORD1001` 会先记录为 `source=user, confirmed=false`；只有现有订单工具返回成功并完成当前用户归属校验后才更新为 `confirmed=true`。

## 3. TaskManager

新增 `app/runtime/task_manager.py`，只负责 TaskState 生命周期，不依赖 LLM、Router、Retriever、Tool 或回答生成。

提供：

- `create_task()` / `start_task()`
- `set_clarifying()` / `set_executing()`
- `complete_task()` / `handoff_task()` / `reject_task()` / `abandon_task()`
- `increment_clarification()`
- `update_missing_slots()`
- `set_entity()`

所有状态变化都会更新 `updated_at`。`need_auth` 仍然是响应层行为；TaskState 用 `clarifying` 加 `missing_slots` 中的 `authentication` 表达。

## 4. Engine Integration

`app/runtime/engine.py` 只做最小接入：

1. 每次 `handle()` 根据当前 route 创建或复用一个 active task。
2. 对订单号和板块创建未确认的用户实体，并更新 required/missing slots。
3. 当前未完成 task 遇到明确不同 intent 时标记 `abandoned`，创建新的 active task；没有实现复杂的自然语言任务关系判断。
4. 现有分支结束后同步 TaskState：成功回答为 `completed`，澄清/认证为 `clarifying`，拒答为 `rejected`，人工转接为 `handoff`。
5. unknown 的澄清判断读取 `TaskState.clarification_count`；`pending_slots` 只保留 V1.1 兼容镜像和登录续办字段。
6. 订单工具成功返回后确认订单实体。

没有重写 Engine、Router、Agent loop、RAG 或 tools。

## 5. Backward Compatibility

- `pending_slots` 没有删除，V1.1 的订单澄清、资格补充、登录后继续查询仍然使用它。
- `AgentResponse` 没有增加或删除字段，HTTP response structure 保持不变；TaskState 暂时通过 `SessionState.active_task` 保存，不单独暴露新的 response 字段。
- 没有修改 `app/api.py`、`app/runtime/router.py`、`app/runtime/tools.py`、`app/rag/` 或前端。
- 现有公共“未成交”路由、知识回答、账户工具、订单归属校验、风险拒答、人工转接、search_knowledge citations 和 `/api/knowledge` governance 行为保持不变。

## 6. Tests

新增 `tests/test_task_state.py`，共 7 个测试：

1. 首次订单消息创建 active order task。
2. clarification count 属于 task，成功回答后新任务从 1 开始。
3. 成功知识查询将 task 标记为 completed。
4. 投资推荐将 task 标记为 rejected。
5. 明确人工请求将 task 标记为 handoff。
6. 明确新任务会结束未完成旧 task，并创建新的 active task。
7. 订单实体在工具归属校验前后分别保持 unconfirmed/confirmed 边界。

最终执行：`.venv/bin/python -m pytest -q`

- 原有 V1.1 测试：59 passed
- 新增 TaskState 测试：7 passed
- 最终总数：66 passed
- failed：0
- skipped：0
- errors：0
- `compileall`：通过
- `git diff --check`：通过

## 7. Files Changed

本阶段计划提交的文件：

- `app/schemas.py`
- `app/runtime/task_manager.py`
- `app/runtime/engine.py`
- `tests/test_task_state.py`
- `docs/audit/task-state-core-report.md`

上一阶段未提交的 `docs/architecture/` 属于既有工作区内容，本阶段不纳入本次 commit，也未修改。

## 8. Design Decisions

- 一个 Session 当前最多一个 active task，没有实现多任务并行或 recent task history。
- TaskState 是新的任务生命周期来源；`pending_slots` 只是迁移期兼容字段。
- `new` 是创建后的短暂状态，Engine 进入处理时转为 `executing`。
- `answerable` 没有被加入 TaskStatus；Answerability 将在下一阶段以独立决策模型实现。
- 没有增加 `observations` 或 `evidence` 字段，避免在 Answerability/Evidence Registry 尚未设计完成时固化错误边界。
- 没有把 `task_id` 加入 AgentResponse，避免改变当前 API response 语义；SessionState 中的可选 `active_task` 已足够支持本阶段测试和后续接入。

## 9. Remaining Limitations

- 当前仍使用简单的 intent 差异判断任务切换，没有实现“不是这个”“另一个订单”等复杂 Task Relation。
- 没有持久化 TaskState 到新的数据库或 Store schema；本阶段禁止新持久化架构。
- `pending_slots` 仍参与 V1.1 的认证续办和临时槽位逻辑，尚未完全迁移到 typed required/missing slots。
- 没有 Answerability gate，因此 `TaskState.completed` 目前表示现有 Engine 成功结束，不表示 V2 的证据充分性已经实现。
- 没有 Evidence Registry、证据冲突处理、过期证据决策或模型辅助关系判断。

## 10. Next Phase

下一阶段应单独设计并实现 Answerability contract 和 Evidence Registry，先为公共知识、账户查询、订单诊断建立 required evidence 测试，再考虑把 observations 转换为 typed evidence。Task Relation、持久化和复杂恢复应在核心证据边界稳定后处理。

本阶段没有安装新依赖、没有引入 Agent framework、没有修改产品定位、没有调用真实外部模型或金融服务。
