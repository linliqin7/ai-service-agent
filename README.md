# AI Service Agent

一个以证券客户服务为验证场景的 AI Service Agent prototype。项目展示 Task State、受证据约束的回答、Answerability、受控 Tool Calling、知识治理、风险拒答和本地人工转接；账户、订单、资金和券商规则均为模拟数据。

## Why this project

金融客服问题通常同时需要识别任务、补齐信息、查询受控工具、引用知识并判断证据是否足够。这个项目把这些步骤放在一个可离线运行、可测试的本地演示中，用来验证工作流边界，而不是提供真实金融服务。

## Architecture

```text
User
  → Task State
  → Router
  → Knowledge / Tools
  → Evidence
  → Answerability
  → Response / Handoff
```

详细设计见 [V2 Task State + Answerability Architecture](docs/architecture/v2-task-state-answerability.md)。实现位于 `app/`，本地页面位于 `web/`，受控知识 fixture 位于 `app/rag/fixtures/`。

## Local setup

需要 Python 3.11+。不配置模型密钥也可以运行本地规则模式、模拟工具和离线评测。

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

`.env` 中的 `DEEPSEEK_API_KEY` 是可选项。不要提交 `.env`，不要把真实客户资料、账号、密码、验证码或交易凭据放入本项目。配置密钥后，服务可能访问外部模型服务；本仓库的测试和离线评测不会调用外部 API。

启动本地服务：

```bash
.venv/bin/python -m uvicorn app.api:app --host 127.0.0.1 --port 8000
```

然后打开 http://127.0.0.1:8000。也可以运行已有的 `scripts/start.py` 或 macOS 启动器；服务只监听本机地址。

## Demo flow

```text
User question
  → task recognition and clarification
  → controlled tool / lexical RAG retrieval
  → task-bound verified evidence
  → deterministic answerability gate
  → answer, clarify, reject, retrieve, or local handoff
```

典型演示包括公共“未成交”定义、本人账户状态、订单状态和归属校验、风险拒答，以及证据不足时不猜测订单原因。

## Tests and evaluation

```bash
.venv/bin/python -m pytest -q
PYTHONPATH=. .venv/bin/python eval/run.py
.venv/bin/python -m compileall -q app tests eval
```

当前本地结果：113 passed；离线评测 main 49/49、holdout 18/18、answerability 9/9。它们是 synthetic / deterministic evaluation on controlled fixtures，不是 production accuracy、真实客户满意度或真实金融正确率。

## Project map

- `app/runtime/engine.py`：任务编排、工具执行、证据 gate 和响应流程。
- `app/runtime/evidence.py`、`app/runtime/answerability.py`：证据晋升和确定性充分性判断。
- `app/runtime/tools.py`：工具白名单、参数校验、模拟业务事实。
- `app/rag/`：治理规则、轻量词项检索和演示知识。
- `tests/`：离线行为、集成和回归测试。
- `eval/`：合成主集、留出集和 Answerability 契约评测。
- `docs/`：架构、审计和交付记录。

## Limitations and disclaimer

- Brokerage data is simulated; there is no real customer account access or real trading execution.
- The knowledge corpus is curated demo data, not a complete or continuously verified regulatory corpus.
- The retriever is lightweight lexical retrieval, not semantic vector search; public knowledge sufficiency is not full semantic understanding.
- Human handoff is a local/demo workflow and does not create a real support ticket or contact a live agent.
- Evaluation is synthetic and deterministic on controlled fixtures.
- This project is not production financial advice, a production brokerage system, or an enterprise financial platform.
- Do not use it with real customer data, credentials, identity documents, passwords, verification codes, or trading decisions.

## License

Released under the [MIT License](LICENSE). The repository contains original project code and curated local fixtures; no third-party source attribution is asserted beyond the dependencies listed in `requirements.txt` and `requirements-lock.txt`.
