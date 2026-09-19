# Runtime Baseline V1

本报告记录当前本地环境下的只读运行基线。除本文件外，本轮未主动修改项目源码、测试、配置或依赖。

## 1. Environment

- 工作目录：`/Users/linliqin/Documents/Codex/面试全流程/简历优化与求职/券商智能客服Agent`
- Python：3.13.7（项目现有 `.venv`）
- pytest：9.1.1
- 关键依赖（可正常导入）：FastAPI 0.141.1、Pydantic 2.13.5、pydantic-settings 2.15.0、HTTPX 0.28.1、Uvicorn 0.53.0
- `app.api` 导入成功；本地 `app.api.engine.llm` 为 `False`，说明本基线未启用真实 LLM。
- 未安装或升级任何依赖。
- 未调用真实外部 LLM 或金融服务。

## 2. Git Status

执行 `git status --short` 时返回：`fatal: not a git repository (or any of the parent directories): .git`。因此无法从当前供审计目录确认 Git 工作区是 clean 还是 dirty，也无法确认压缩包外是否存在用户已有修改。

## 3. Test Results

使用项目现有环境运行完整测试套件：`.venv/bin/python -m pytest -q`。

- 总测试：55
- passed：55
- failed：0
- skipped：0
- error：0
- 用时：0.29 秒
- 通过率：100%（55/55）

出现 2 条依赖弃用警告（TestClient/httpx、AnyIO BlockingPortal），未导致测试失败。未修改任何测试。相关测试文件包括 `tests/test_api.py`、`test_contracts.py`、`test_integrations.py`、`test_limits_and_ingest.py`、`test_llm_loop.py`、`test_regressions.py`、`test_review_fixes.py`、`test_runtime.py`。

## 4. Offline Evaluation Results

执行现有离线评测：`PYTHONPATH=. .venv/bin/python eval/run.py`。

- 本轮实际输出：`main 49/49`、`holdout 18/18`。
- 该评测构造 `Engine()` 且未注入 LLM，验证的是确定性本地路径；不能证明真实模型下的质量。
- 评测脚本按既有行为刷新了 `eval/report.json`。这是运行评测产生的副作用，非本轮手工编写；不得将历史文件内容误记为本轮结果。
- `scripts/smoke_live.py` 未执行，因为它读取 DeepSeek 凭证并调用外部模型。需要真实模型或无法确认是否需要外部服务的评测均未执行。

## 5. Audit Finding Verification

### 5.1 “未成交”的公共解释是否被订单路由截走

静态确认：`app/runtime/router.py` 在公共定义分支前先匹配订单意图，订单关键词包含“未成交”。因此“未成交是什么意思？”可能先进入订单路由，而不是公共解释路径。现有测试覆盖订单澄清，但没有覆盖该精确公共定义句。曾尝试动态探针，但输入转义导致探针在 Python 语法解析阶段失败，未形成运行时复现证据；本项应标记为“静态确认、动态未复现”。

### 5.2 成功问答后旧澄清计数是否仍存在

静态确认：`Engine.handle()` 对 unknown 路由递增 `pending_slots["clarifications"]`；只有已回答的 private 路径显式清空 `pending_slots`。普通知识/RAG 成功分支没有同等清理。没有新增测试，也未完成多轮动态复现，因此属于“静态确认、动态未复现”。

### 5.3 Agent 内部 `search_knowledge` 结果是否进入最终事实回答

静态确认：`TOOLS` 允许订单/资金路径调用 `search_knowledge`，但 `render_facts()` 只消费 `get_profile`、`get_rule`、`get_order_detail`、`get_account`、`get_funds`、`get_risk`、`get_holdings` 等事实工具结果，不消费 `search_knowledge` observation。因此检索结果不会自动并入最终事实渲染。现有测试未直接覆盖该组合路径，属于“静态确认”。

### 5.4 `/api/knowledge` 是否绕过受众过滤

静态确认：`app/api.py` 的 `/api/knowledge` 直接返回 `records()`；`app/rag/retriever.py` 才通过 `current(record, as_of, audience)` 执行治理过滤。当前 fixtures 全为 public，未动态证明私有/草稿记录已泄露；风险在引入此类记录后出现。属于“静态确认、当前数据下未复现”。

## 6. Representative Cases

以下案例从现有测试和离线评测中选取，未新增测试数据：

| 能力 | 输入/场景 | 预期与实际 | 路由/模型/工具/状态 |
|---|---|---|---|
| 普通知识问答 | “开户需要什么材料” | 通过；返回知识答案 | 知识/RAG 本地路径；无真实模型 |
| 本人账户查询 | “我的开户进度到哪了” | 通过合成评测路径 | private/account；本地工具事实 |
| 订单异常诊断 | “我的委托为什么没成”→“ORD1001” | 通过；完成订单澄清 | order；调用本地订单工具；结束 |
| 缺少槽位澄清 | “我的委托为什么没成” | 通过；要求订单号 | order + clarification；未完成任务 |
| 风险拒答 | “推荐我买哪只股票” | 通过；拒绝投资推荐 | risk refusal；不调用真实服务 |
| 人工转接 | “我要投诉转人工” | 通过合成评测预期 | handoff；产生转人工状态/工单语义 |
| 知识过期 | 过期知识 fixture | 通过；无可用结果 | retriever governance；返回不可用/澄清 |
| 无答案知识查询 | “这个怎么弄”→“就是那个” | 通过；澄清后转人工 | unknown/clarify→handoff |
| 模型动作选择 | fake planner 集成测试 | 通过 | 使用 fake planner；非真实模型 |
| 工具失败/越权 | U1002 查询 ORD1001 | 通过；所有权保护并转人工 | order tool failure/ownership；handoff |

表中“通过”表示既有自动化断言或离线评测通过，不表示真实生产服务质量。

## 7. Current V1 Baseline

1. 自动化测试通过率为 55/55（100%）；无失败、跳过或错误。
2. 离线评测可以证明：在固定 fixture、确定性 Engine 和现有断言范围内，main 49/49、holdout 18/18。
3. 离线评测无法证明：真实 LLM 调用质量、开放域知识覆盖、实时数据正确性、并发/延迟、生产鉴权、真实人工系统联动、金融交易安全。
4. 已实际由代码静态确认的问题：订单关键词可能优先截走公共“未成交”解释；澄清计数清理不完整；search_knowledge 结果未进入事实渲染；knowledge API 未复用 retriever 受众过滤。当前没有把其中任何一项宣称为完整动态回归。
5. 动态探针未成功形成证据的项目：问题 1、2；问题 4 在当前全 public fixture 下未形成数据泄露复现。
6. 优先级调整：四项均应保留为 P1/P2 级验证对象；由于当前测试全绿，尚不能仅凭本轮运行结果把它们升级为已造成线上故障的 P0。知识 API 的治理风险在引入非 public 数据前应上升关注级别。

## 8. Known Limitations

- 供审计目录不是 Git 仓库，无法取得提交、分支或 dirty state 证据。
- 未启动前后端服务，也未进行浏览器端到端验证。
- 未运行真实 LLM smoke test；未验证外部凭证、网络、限流和模型输出。
- 未修改或新增测试，因此动态复现覆盖有限。
- 评测脚本刷新了 `eval/report.json`；该文件变化属于脚本副作用，应在后续有 Git 仓库的环境中单独核对。

## 9. What Was NOT Executed

- `scripts/smoke_live.py`：跳过，避免真实外部 LLM API。
- 任何真实金融服务、交易、账户系统调用：未执行。
- 需要外部模型的评测：未执行。
- 生产部署、Docker 启动、浏览器 E2E：未执行。
- 未引入 LangGraph、向量数据库、Reranker、Multi-Agent 或新模型；未修改 Prompt、Engine 或业务逻辑。

## 10. Recommended Next Step

下一步应在具备可追踪 Git 工作区的隔离环境中，为四个静态发现分别增加最小化、可离线运行的回归验证，先确认真实运行路径与状态变化，再决定是否进入修复阶段。继续保持真实模型和金融服务隔离，并把评测脚本的输出文件副作用纳入基线记录。

本轮确认：没有修改业务源码；没有修改测试源码；没有安装或升级依赖；没有调用真实外部 LLM；没有调用真实金融服务。
