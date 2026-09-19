# Open Source Release Audit

## 1. Security

The tracked repository was scanned for API keys, tokens, passwords, authorization headers, cookies, private URLs, local credentials, databases, logs, and session artifacts.

- No real secrets were found.
- `.env` and `.env.*` are ignored; only `.env.example` is tracked and contains placeholders.
- `eval/live-report.json`, local databases, logs, caches, virtual environments, and runtime directories are ignored.
- Test fixtures contain deliberately constructed `sk-...` strings used to verify redaction. They are not credentials and do not grant access.
- `SECURITY.md` documents the local-only security boundary; it does not contain a secret value.

No suspicious credential is reported because the scan found no real credential to report.

## 2. License

No license file existed before this audit. A standard MIT `LICENSE` dated 2026 was added with the neutral holder text “The repository owner”; no personal name was guessed.

The repository does not vendor third-party source code or assets, and no copied-code or embedded attribution notice was found in the tracked files. Runtime dependencies remain declared in `requirements.txt`, `requirements-lock.txt`, and `pyproject.toml`; their own licenses should be reviewed by a publisher as part of normal dependency compliance.

## 3. Public Data

The public repository content is suitable for release as a local prototype:

- `app/`, `web/`, `tests/`, `eval/`, `docs/`, `scripts/`, `pyproject.toml`, `requirements*.txt`, `.env.example`, and `.gitignore` contain source, tests, documentation, or synthetic fixtures.
- `app/data/repository.py` and `app/rag/fixtures/knowledge.json` contain simulated accounts, orders, and curated demo knowledge, not real customer records.
- `eval/main.json`, `eval/holdout.json`, `eval/answerability.json`, and `eval/report.json` contain synthetic queries, fixture outputs, and deterministic evaluation metadata.
- No tracked SQLite database, local log, cookie, session export, or live model report was found.

## 4. README

README was updated to provide the project positioning, motivation, architecture flow, local setup, optional model-key configuration, startup command, tests, offline evaluation, project map, demo flow, limitations, and license.

It explicitly identifies the project as an AI Service Agent prototype for a securities customer-service scenario. It does not claim production brokerage capabilities, enterprise readiness, real trading, real account access, or production accuracy.

## 5. Evaluation

Fresh offline checks produced:

- main: 49/49
- holdout: 18/18
- answerability: 9/9

These are synthetic / deterministic evaluations on controlled fixtures. They are not production accuracy, real customer satisfaction, or a real financial correctness rate. The additional Answerability result remains a separate top-level report field so the existing web evaluation view continues to interpret its original two splits correctly.

## 6. Local Setup

The README documents:

1. creating `.venv`;
2. installing `requirements.txt`;
3. copying `.env.example` to `.env`;
4. optionally configuring `DEEPSEEK_API_KEY`;
5. starting `uvicorn` on `127.0.0.1:8000`;
6. running pytest, offline evaluation, and compileall.

No new startup system, dependency, API, or runtime behavior was introduced.

## 7. Limitations

The release documentation states that brokerage data is simulated, there is no real trading execution or customer-account access, the knowledge corpus is curated demo data, retrieval is lightweight lexical matching, public knowledge sufficiency is not full semantic understanding, human handoff is local/demo only, and the project is not production financial advice.

The optional live-model script remains in the repository for local experimentation but is not part of the offline release verification and is not run by this audit.

## 8. Tests

Fresh command results:

- `.venv/bin/python -m pytest -q`: **113 passed**, 0 failed, 0 skipped, 0 errors.
- `PYTHONPATH=. .venv/bin/python eval/run.py`: **main 49/49, holdout 18/18, answerability 9/9**.
- `.venv/bin/python -m compileall -q app tests eval`: passed.
- `git diff --check`: passed.

The test run emitted two existing dependency deprecation warnings from Starlette/httpx and AnyIO. No dependency was upgraded to remove them.

## 9. Files Changed

This release-audit change is limited to:

- `README.md` — minimal public-project, setup, evaluation, architecture, and limitation documentation.
- `LICENSE` — MIT license, 2026.
- `docs/audit/open-source-release-audit.md` — this audit report.
- `eval/report.json` — refreshed by the required offline evaluation command; it remains synthetic fixture output.

No application, test, router, RAG, tool, API, or frontend behavior was changed.

## 10. Remaining Risks

- Dependency license obligations are not vendored into this repository; a final publisher should retain the dependency manifests and review their licenses before redistribution.
- The optional DeepSeek integration can contact an external model provider if a user supplies a key. The default local mode and all required audit commands do not do so.
- The repository is a local demo and should not be deployed publicly with real customer data or credentials.
- The generated evaluation report includes runtime latency samples; these are local execution observations, not performance guarantees.

## 11. GitHub Publishing Checklist

- [x] No real secrets found.
- [x] No real user data found.
- [x] MIT license added.
- [x] README suitable as an open-source prototype landing page.
- [x] Synthetic data and evaluation scope labeled.
- [x] `.env` and local runtime artifacts ignored.
- [x] Tests, evaluation, compileall, and diff check passed.
- [x] No GitHub remote created.
- [x] No push or release performed.

The working tree is expected to be clean after committing the three release-audit files and the refreshed synthetic evaluation report.
