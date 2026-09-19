# Git Baseline

## Repository Status

- 已在 `/Users/linliqin/Documents/Codex/面试全流程/简历优化与求职/券商智能客服Agent` 初始化 Git repository。
- 初始化前该目录不是 Git repository，因此无法取得初始化前的 Git dirty state。
- 首个 baseline commit 已创建：`46f23f82b7d8b0eedbecb6efc53b0f52bb5fa5a7`。
- 首个 commit message：`chore: establish V1 baseline`。
- 首个 commit 包含 68 个文件。
- 当前没有配置 GitHub remote，也没有 push。

## Security Check

- 未发现 `.env` 文件。
- 未发现可确认的真实 API key、token、password、cookie、session 或 authorization 凭据。
- 命中的 `deepseek_api_key` 是代码配置字段，默认值为空；测试中的 `sk-...` 是伪造测试值，不是真实凭据。
- `var/agent.sqlite3` 是本地 SQLite 会话/反馈数据库，含演示运行状态；未加入 Git。
- 未发现需要公开的真实用户账户资料。项目中的账户、订单和资产是 README 与代码明确标注的模拟数据。
- `eval/report.json` 标记为 `synthetic: true`，保留为可复现离线评测产物。
- `eval/live-report.json` 含真实模型调用记录与运行元数据，作为本地运行产物排除。

## Ignored Files

`.gitignore` 已覆盖：

- `.env`、`.env.*`，并保留 `!.env.example`
- `.venv/`、`venv/`
- Python 缓存、pytest/mypy/ruff 缓存
- `*.db`、`*.sqlite`、`*.sqlite3`、`var/`
- `logs/`、`tmp/`、`cache/`、日志和临时文件
- `eval/live-report.json`
- `.idea/`、`.vscode/`、`.DS_Store`

初始化后 `git status --ignored` 已确认 `.env` 规则、虚拟环境、本地数据库目录、缓存和 live report 均被忽略。

## Environment Variables

已保留并更新安全模板：`.env.example`。

- 仅包含变量名和安全 placeholder。
- `DEEPSEEK_API_KEY=your_api_key_here` 不是真实密钥。
- 未把任何本机环境变量或钥匙串内容写入仓库。

## Public Artifacts

首个 baseline 保留了适合公开复现的内容：

- 应用源码、前端静态文件和 API
- 单元/集成测试
- `eval/main.json`、`eval/holdout.json` 和明确标记 synthetic 的 `eval/report.json`
- 依赖声明与锁定文件
- README、PRD、SECURITY 和架构/评测文档
- `docs/audit/runtime-baseline-v1.md`

现有 README 已具备公开仓库基础，包括概览、运行方式、验证命令、文件导览和金融场景免责声明；本轮未覆盖或另建 README skeleton。

## Commit

- Commit：`46f23f82b7d8b0eedbecb6efc53b0f52bb5fa5a7`
- Message：`chore: establish V1 baseline`
- Files：68
- 本报告在首个 baseline commit 后作为审计记录单独提交，不改变首个 baseline 的内容。

## Files Included

首个 commit 包含应用源码、前端、测试、合成评测数据与报告、依赖文件、公开文档、`.gitignore`、`.env.example` 和运行基线报告；完整列表以该 commit 的 `git show --stat` 为准。

## Files Excluded

- `.env` 及其他本地环境文件
- `.venv/` 和 Python/pytest 缓存
- `var/agent.sqlite3` 及其他本地数据库
- `.DS_Store`、IDE 文件、日志、临时目录和缓存目录
- `eval/live-report.json`，因为它是本地真实模型运行产物

## Risks

- Git 初始化前无法从当前目录确认是否存在此前未提交的用户修改。
- 首次 commit 使用一次性本地身份 `Codex <codex@local>`，未修改全局 Git 配置；若后续发布到公开仓库，应按维护者身份配置提交签名。
- 评测报告和文档含模拟账户/订单示例，不能被表述为真实金融服务数据。
- `.env.example` 的 placeholder 不能直接用于生产；真实密钥只能通过本地环境或安全凭据管理注入。

## GitHub Publishing Checklist

- [x] Git repository initialized
- [x] First V1 baseline commit created
- [x] Staged secret review completed
- [x] `.env` ignored
- [x] Local databases ignored
- [x] `.venv` and caches ignored
- [x] No real credentials found
- [x] No GitHub remote created
- [x] No push performed

本阶段没有修改业务逻辑、没有开发 AI Agent 功能、没有安装或升级依赖。
