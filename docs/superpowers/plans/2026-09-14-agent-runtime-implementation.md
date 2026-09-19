# Historical Implementation Plan — 券商经纪业务智能客服 Agent

> 执行结果（2026-09-15）：本文件为历史实施计划，记录当时的范围和差异。它不定义当前公开版本；当前规范以根目录 `PRD.md` 和 `../../architecture/overview-v1.0.md` 为准，旧版 PRD 归档于 `../../product/prd-v0.2.md`。向量检索、生产身份和 Judge 校准未作为已完成能力。

> **给执行者：**按任务逐项实现，每个任务都要完成测试和复盘后再进入下一项。

**目标：**构建一个真实接入 DeepSeek 的券商经纪业务智能客服 Agent，覆盖全生命周期任务路由、治理型 RAG、用户画像工具、受控 Agent Loop、合规控制、审计追踪、评测和 Web 界面。

**架构：**后端 Agent Runtime 负责会话状态和策略。确定性 Router 根据意图、风险、鉴权和数据需求选择 FAQ、RAG、受控工具、Agent Loop、拒答或转人工；DeepSeek 只负责复杂意图识别、受限规划和回复生成。前端通过后端 API 交互，并可展开查看处理追踪。

**技术栈：**Python 3.11+、FastAPI、Pydantic、SQLite、本地检索库（初期 SQLite FTS，预留向量适配器）、DeepSeek OpenAI 兼容 API、原生 HTML/CSS/JavaScript、pytest。

**依据：**`PRD.md`

## 全局约束

- 账户、订单、资产和交易数据只使用 mock；不连接真实账户，不执行真实交易。
- API Key 只放在后端环境变量；不得出现在前端或代码仓库。
- 所有金融规则都必须是带版本的数据；禁止只依赖模型记忆回答规则。
- 高风险请求必须由确定性策略在普通生成前拦截。
- 未知、低置信度、过期、未授权或失败请求必须澄清或转人工，不能编造。
- 每次回复都产生包含路由、依据、工具、策略检查、延迟和成本的 trace。
- 主评测集和留出集分开维护、分开报告。

---

## 任务 1：建立应用骨架和接口契约

**文件：**新建 `app/`、`tests/`、`.env.example`、`pyproject.toml`、`app/config.py`、`app/schemas.py`。

**接口：**

- `SessionState(session_id: str, user_id: str | None, authenticated: bool, messages: list, pending_slots: dict, loop_steps: int)`
- `TraceEvent(type: str, data: dict, timestamp: str)`
- `AgentResponse(answer: str, status: str, trace: list[TraceEvent], citations: list, handoff: dict | None)`

**步骤：**

- [ ] 编写 Pydantic 数据模型和配置加载，支持 `DEEPSEEK_API_KEY`、`DEEPSEEK_BASE_URL`、`DEEPSEEK_MODEL`、`DATABASE_URL`。
- [ ] 为模型校验和缺少 API Key 的情况编写测试。
- [ ] 运行 `pytest -q`，确认契约测试通过。

## 任务 2：建立版本化业务数据和仓储层

**文件：**新建 `app/data/`、`app/repositories/`、`app/domain/`；测试 `tests/test_repositories.py`。

**接口：**

- `RuleRepository.get_current(domain: str, as_of: date) -> RuleRecord | None`
- `KnowledgeRepository.search(query: str, filters: dict, top_k: int) -> list[KnowledgeHit]`
- `AccountRepository.get_profile(user_id: str) -> AccountProfile | None`
- `OrderRepository.get_detail(order_id: str, requesting_user_id: str) -> OrderDetail | ToolError`

**步骤：**

- [ ] 定义 mock 用户的资产层级、生命周期、KYC/风险测评和账户状态。
- [ ] 定义 mock 订单和失败原因码。
- [ ] 定义带 `rule_version`、`effective_at`、`expires_at`、`source_url`、`review_status` 的规则记录。
- [ ] 实现资源归属校验；测试用户不存在、订单越权、规则过期和版本选择。
- [ ] 运行仓储层测试，确认越权请求不会返回订单数据。

## 任务 3：实现知识导入和治理型 RAG

**文件：**新建 `app/rag/ingest.py`、`app/rag/retriever.py`、`app/rag/governance.py`、`app/rag/fixtures/`；测试 `tests/test_rag.py`。

**接口：**

- `ingest_document(path: str, metadata: KnowledgeMetadata) -> list[KnowledgeRecord]`
- `retrieve(query: str, domain: str | None, as_of: date, top_k: int = 5) -> RetrievalResult`
- `validate_evidence(result: RetrievalResult) -> EvidenceDecision`

**步骤：**

- [ ] 把示例规则文档切成带来源、业务域、适用时间、版本和直接回答策略的知识块。
- [ ] 初期实现可解释的关键词检索，并隔离后续向量适配器。
- [ ] 检索前过滤过期、废弃和未审核记录，再进行排序。
- [ ] 没有当前且充分依据时返回 `insufficient_evidence`。
- [ ] 测试当前/废弃版本选择、业务域过滤、空检索和引用传递。

## 任务 4：接入 DeepSeek 并使用结构化输出

**文件：**新建 `app/llm/deepseek.py`、`app/llm/prompts.py`；使用 fake transport 测试 `tests/test_llm_adapter.py`。

**接口：**

- `DeepSeekClient.complete(messages: list[dict], response_model: type[BaseModel], temperature: float = 0) -> BaseModel`
- `IntentDecision(intent_id: str, risk_level: str, needs_auth: bool, slots: dict, confidence: float)`
- `PlanStep(action: Literal['clarify', 'retrieve', 'tool', 'answer', 'reject', 'handoff'], name: str, args: dict)`

**步骤：**

- [ ] 使用 OpenAI 兼容 HTTP 接口，加入超时、有限重试、token/成本统计和脱敏日志。
- [ ] 结构化输出解析失败时，降级为澄清或转人工。
- [ ] 在 Prompt 中禁止无依据事实、投资建议、秘密泄露和未授权工具。
- [ ] 测试超时、非法 JSON、API 错误和正常结构化响应。

## 任务 5：实现 Router 和确定性处理管线

**文件：**新建 `app/runtime/router.py`、`app/runtime/pipelines.py`、`app/runtime/policy.py`；测试 `tests/test_routing.py`。

**接口：**

- `route(request: AgentRequest, session: SessionState) -> RouteDecision`
- `run_pipeline(decision: RouteDecision, request: AgentRequest, session: SessionState) -> AgentResponse`

**步骤：**

- [ ] 实现风险优先路由：注入、越权和高风险请求先于普通意图处理。
- [ ] 实现 FAQ、RAG、鉴权资格/状态、订单诊断、拒答和转人工管线。
- [ ] 严格区分“规则是什么”和“我能不能办理”。
- [ ] 每次工具调用都检查会话身份和资源归属。
- [ ] 测试标准规则、资格判断、订单诊断、歧义、高风险投资请求和越权订单。

## 任务 6：实现受控 Agent Loop

**文件：**新建 `app/runtime/loop.py`、`app/runtime/tools.py`；测试 `tests/test_agent_loop.py`。

**接口：**

- `run_loop(state: LoopState, planner: Planner, tools: ToolRegistry, limits: LoopLimits) -> LoopResult`
- `ToolRegistry.invoke(name: str, args: dict, context: AuthContext) -> ToolResult`

**步骤：**

- [ ] 只允许注册工具和通过 schema 校验的参数。
- [ ] 限制最大步数、总时长、成本、重复动作和策略终止条件。
- [ ] 支持“澄清 → 鉴权 → 工具 → 检索 → 回答”的订单/资格诊断流程。
- [ ] 工具失败、依据过期或槽位缺失时，明确降级或转人工。
- [ ] 测试成功多步诊断、超步数、未知工具、非法参数、超时和策略终止。

## 任务 7：实现评测、回归和可观测性

**文件：**新建 `eval/`、`app/observability/`；测试 `tests/test_eval.py`。

**接口：**

- `evaluate(dataset_path: str, mode: Literal['main', 'holdout']) -> EvalReport`
- `score_case(expected: Case, actual: AgentResponse) -> CaseScore`

**步骤：**

- [ ] 建立覆盖全生命周期的标准、口语、模糊、多轮、对抗和边界 Query。
- [ ] 评估意图、任务完成、依据引用、工具正确性、合规一票否决、延迟和成本。
- [ ] 禁止修复脚本读取留出集。
- [ ] 保存 trace ID 并脱敏敏感字段。
- [ ] 按路由、检索、工具、生成和策略层输出 Bad Case 归因。

## 任务 8：实现 Web 客户端和端到端流程

**文件：**新建 `web/index.html`、`web/app.js`、`web/styles.css`；后端 `app/api.py`；测试 `tests/test_api.py`。

**接口：**

- `POST /api/sessions -> SessionState`
- `POST /api/sessions/{id}/messages -> AgentResponse`
- `POST /api/sessions/{id}/auth -> SessionState`
- `GET /api/sessions/{id}/trace -> list[TraceEvent]`

**步骤：**

- [ ] 实现用户选择、模拟登录、聊天、建议任务、加载状态和转人工操作。
- [ ] 调试面板默认折叠；展开后展示路由、画像、依据、工具、策略和版本。
- [ ] 增加规则查询、资格判断、订单诊断、多轮澄清和拒答的端到端测试。

## 任务 9：安全、质量审查和面试交付

**文件：**新建 `docs/architecture-final.md`、`docs/interview/`、`SECURITY.md`、`Makefile`。

**步骤：**

- [ ] 运行单元、API 和评测测试；确认密钥不出现在日志和前端资源。
- [ ] 确认所有高风险留出集样本都会被拒答或转人工。
- [ ] 记录实际实现、生产设计和 mock 边界。
- [ ] 准备 90 秒自我介绍、5 分钟项目讲解、Agent Loop/Workflow/Router/Multi-Agent 理论解释和一个诚实的 Bad Case 故事。
- [ ] 每次修复后重新评测，并分开报告主集和留出集结果。
