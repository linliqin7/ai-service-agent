# Product and Repository v1.0 Alignment Audit

Audit date: 2026-09-19

## Scope

This audit aligns public product documentation for the released AI Service Agent v1.0. It does not change application code, tests, evaluation cases, dependencies, task logic, evidence logic, Answerability logic, RAG, tools, API behavior, or the existing `v1.0.0` tag and release.

## Current Product Fact Baseline

The current public product is **AI Service Agent**, validated first in a securities brokerage customer-service scenario. The implemented product loop is:

```text
User Goal
  → Task State
  → Router / Workflow
  → Knowledge / Controlled Tools
  → Evidence
  → Answerability Gate
  → Answer / Clarify / Reject / Handoff
```

The repository implements Task State, task-local evidence, a deterministic Answerability decision, governed lexical knowledge retrieval, controlled simulated tools, clarification, safety rejection, local handoff, traceability, a local web demo, pytest/TestClient coverage, and offline evaluation.

Business data, knowledge records, evaluation cases, and results are synthetic, curated, or controlled fixtures. The system has no real broker API, customer account, transaction execution, production identity system, real human handoff, production metric, or production compliance validation.

## Documentation Classification

| Document | Classification after audit |
|---|---|
| `README.md` | Current public project landing page |
| `PRD.md` | Current v1.0 product specification |
| `docs/architecture/overview-v1.0.md` | Current technical/product architecture overview |
| `docs/product/prd-v0.2.md` | Historical PRD retained for evolution evidence |
| `docs/architecture/v2-task-state-answerability.md` | Historical pre-implementation design note |
| `docs/项目交付与验收.md` | Historical pre-v1.0 delivery record |
| `docs/架构与取舍.md` | Historical technical trade-off note |
| `docs/面试讲解与追问.md` | Historical interview narrative |
| `docs/audit/*` | Historical and current audit evidence, each bounded by its stated phase/date |

The historical documents were retained. Their titles or opening context now make clear that older test counts, real-model smoke checks, plans, and V1/V2 phase statements do not define the current release.

## Current Documentation Checks

- README and PRD both position the project as an AI Service Agent prototype, with securities brokerage as a validation scenario.
- README and the current architecture overview expose the same product loop.
- PRD makes Task State, Evidence, and Answerability core product mechanisms rather than implementation details.
- PRD lists the implemented Answerability statuses and their visible next actions.
- PRD and README state the release validation figures: 113 automated tests, main 49/49, holdout 18/18, and answerability 9/9.
- PRD and README label those figures synthetic / controlled / deterministic offline evaluation, not production accuracy, FCR, customer satisfaction, or financial correctness.
- PRD explicitly lists real broker APIs, production authorization, vector databases, rerankers, Multi-Agent, LangGraph, MCP, long-term memory, omnichannel service, production governance, and production metrics as future scope.

## Security and Public-Data Check

The tracked file list does not include `.env`, local SQLite databases, logs, cache directories, session exports, or `eval/live-report.json`. `.gitignore` excludes `.env`, `.env.*` except `.env.example`, `.venv/`, database extensions, `var/`, `logs/`, caches, and live evaluation output.

The sensitive-term scan found configuration names and deliberate test-only redaction fixtures, not a verified credential. The local working directory does contain ignored runtime artifacts (`var/agent.sqlite3` and `eval/live-report.json`); they are not tracked or staged and are not part of this publication update.

## Deliberately Unchanged Metadata

`pyproject.toml` still declares the historical package name `brokerage-support-agent` and version `0.2.0`; `app/api.py` also retains historical API title/version metadata. They were not changed because this audit prohibits application/configuration changes. The current GitHub-facing README, current PRD, and current architecture overview use the v1.0 AI Service Agent positioning. A future release-management decision can update package/API metadata together, with compatibility review.

## Verification Results

The final local verification ran without an external model or financial service:

| Check | Result |
|---|---|
| `.venv/bin/python -m pytest -q` | 113 passed; 0 failed, skipped, or errors |
| `PYTHONPATH=. .venv/bin/python eval/run.py` | main 49/49; holdout 18/18; answerability 9/9 |
| `.venv/bin/python -m compileall -q .` | passed |
| Documentation stale-reference search | current README and root PRD have no old-stage result claims |
| Sensitive-file and ignore check | passed; ignored local artifacts remain untracked |
| `git diff --check` | passed before commit |

The pytest run reported two existing Starlette/httpx and AnyIO deprecation warnings. This documentation audit does not change dependencies to suppress them.
