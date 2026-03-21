# ResearchOS

Language: [English](#english) | [中文](#zh-cn)

<a id="english"></a>
<details open>
<summary><strong>English</strong></summary>

## What It Is

ResearchOS is a research workflow runtime for structured, multi-step work. It keeps projects, tasks, paper cards, gap maps, freezes, runs, claims, lessons, and verification records as first-class objects instead of burying them in chat logs.

It has three operator surfaces:

- CLI for direct control
- FastAPI for automation and inspection
- React web UI for the same control-plane workflow in a visual interface

The current web UI supports guided research intake, automated `paper_ingest -> gap_mapping`, human idea selection, and a real LLM-backed discussion sidebar for idea feasibility review.

## Core Capabilities

- Typed task lifecycle and dispatch state
- Specialized agents with role contracts
- Provider routing across `codex`, `claude`, `gemini`, and `local`
- Durable registries for research objects
- Verification, audit, provenance, and approval surfaces
- One-command local web startup

## Quick Start

### Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+ for the frontend
- Optional provider CLIs if you want live external model execution

### Install

```powershell
uv sync --dev
cd frontend
npm install
cd ..
```

### Recommended Local Setup

Use the deterministic local provider if you want a safe first run:

```powershell
$env:RESEARCHOS_PROVIDER = "local"
$env:RESEARCHOS_PROVIDER_MODEL = "deterministic-reader"
$env:RESEARCHOS_WORKSPACE_ROOT = (Resolve-Path ".").Path
```

Initialize the database:

```powershell
uv run researchos --db-path data\researchos.db init-db
```

### Start the Web UI

```powershell
uv run researchos web
```

Default local ports:

- Frontend: `http://127.0.0.1:5173`
- API: `http://127.0.0.1:8000`

Override ports if needed:

```powershell
uv run researchos web --port 8010 --frontend-port 5180
```

### Start Only the API

```powershell
uv run uvicorn app.api.app:create_app --factory --reload
```

Health check:

```powershell
curl http://127.0.0.1:8000/health
```

## Common Workflows

### CLI

Create a project:

```powershell
uv run researchos --db-path data\researchos.db create-project `
  --project-id p1 `
  --name "ResearchOS Demo" `
  --description "Minimal local demo"
```

Create a task:

```powershell
uv run researchos --db-path data\researchos.db create-task `
  --task-id t1 `
  --project-id p1 `
  --kind paper_ingest `
  --goal "Read one paper summary" `
  --owner demo `
  --input-payload "{\"topic\":\"robustness\",\"source_summary\":{\"title\":\"Example Paper\",\"abstract\":\"A compact summary.\",\"setting\":\"classification\"}}"
```

Dispatch and inspect:

```powershell
uv run researchos --db-path data\researchos.db dispatch-task --task-id t1
uv run researchos --db-path data\researchos.db list-tasks --project-id p1
uv run researchos --db-path data\researchos.db project-dashboard --project-id p1
uv run researchos --db-path data\researchos.db inspect-routing-system
uv run researchos --db-path data\researchos.db provider-health
```

Open the terminal control plane:

```powershell
uv run researchos
uv run researchos console
uv run ros
```

### Web UI

The web UI is built around the same workflow as the CLI, but with guided entry points:

- Start a project from a plain-language research goal
- Auto-run `paper_ingest` and `gap_mapping`
- Pause at `human_select`
- Discuss candidate directions with the LLM sidebar
- Adopt one direction and continue into spec/build/review/writing

## Provider Setup

Minimum environment example:

```powershell
$env:RESEARCHOS_PROVIDER = "claude"
$env:RESEARCHOS_PROVIDER_MODEL = "sonnet"
$env:RESEARCHOS_MAX_STEPS = "12"
```

Supported provider families:

- `codex`
- `claude`
- `gemini`
- `local`

Use `local` for demos, CI, and deterministic tests. Use `codex`, `claude`, or `gemini` only if the matching CLI is already installed and authenticated.

## Project Layout

Main directories:

- [`app/`](app/) — runtime, agents, services, API, CLI
- [`frontend/`](frontend/) — React web UI
- [`prompts/`](prompts/) — repo-owned prompts
- [`skills/`](skills/) — repo-owned skills
- [`examples/`](examples/) — copy-pastable demos
- [`docs/`](docs/) — setup and release notes

## Durable State

ResearchOS stores durable workflow state in two places:

- Database: projects and tasks
- Registry files under `registry/`: paper cards, gap maps, runs, claims, lessons, verifications, freezes, artifacts

Important paths:

- `registry/paper_cards.jsonl`
- `registry/gap_maps.jsonl`
- `registry/claims.jsonl`
- `registry/runs.jsonl`
- `registry/lessons.jsonl`
- `registry/verifications.jsonl`
- `registry/artifacts.jsonl`
- `registry/freezes/`
- `artifacts/`
- `state/provider_health.yaml`

## API Surfaces

Useful operator endpoints:

- `GET /projects/{project_id}/dashboard`
- `GET /routing/system`
- `GET /routing/tasks/{task_id}`
- `GET /providers/health`
- `GET /artifacts`
- `GET /artifacts/{artifact_id}`
- `GET /artifacts/{artifact_id}/inspect`
- `GET /verifications/summary`
- `GET /audit/summary`
- `POST /guide/start`
- `POST /guide/discuss-direction`
- `POST /guide/adopt-direction`
- `POST /projects/{project_id}/autopilot`

## Production Stack

The production-oriented stack uses:

- FastAPI
- Postgres
- Redis
- Celery worker

Start it with:

```powershell
docker compose up -d --build
```

## Examples and Notes

- [`examples/README.md`](examples/README.md)
- [`docs/operator_setup.md`](docs/operator_setup.md)
- [`docs/release_checklist.md`](docs/release_checklist.md)
- [`CHANGELOG.md`](CHANGELOG.md)

## CI

GitHub Actions currently runs:

- dependency install with `uv`
- Python import sanity
- unit tests
- API dispatch smoke with the local provider
- a small CLI smoke path

Workflow file:

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

</details>

<a id="zh-cn"></a>
<details>
<summary><strong>中文</strong></summary>

## 这是什么

ResearchOS 是一个面向研究流程的运行时系统。它把项目、任务、论文卡片、gap map、freeze、run、claim、lesson、verification 这些对象都当成正式状态来管理，而不是散落在聊天记录里。

它现在有三个主要入口：

- CLI，适合直接控制
- FastAPI，适合自动化和检查
- React Web UI，适合同样的控制流程但更直观

当前 Web UI 已经支持从研究方向出发，自动推进 `paper_ingest -> gap_mapping`，在 `human_select` 停下，并用真实 LLM 讨论侧栏辅助选题。

## 核心能力

- 强类型任务生命周期和调度状态
- 带角色约束的专用 agent
- `codex`、`claude`、`gemini`、`local` 多 provider 路由
- 持久化研究登记表
- verification、audit、provenance、approval 一整套检查面
- 一条命令同时拉起前后端

## 快速开始

### 环境要求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+（前端需要）
- 如果要调用外部模型，需要对应 provider 的 CLI

### 安装依赖

```powershell
uv sync --dev
cd frontend
npm install
cd ..
```

### 推荐的本地起步方式

第一次跑建议先用确定性的本地 provider：

```powershell
$env:RESEARCHOS_PROVIDER = "local"
$env:RESEARCHOS_PROVIDER_MODEL = "deterministic-reader"
$env:RESEARCHOS_WORKSPACE_ROOT = (Resolve-Path ".").Path
```

初始化数据库：

```powershell
uv run researchos --db-path data\researchos.db init-db
```

### 启动 Web UI

```powershell
uv run researchos web
```

默认本地地址：

- 前端：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:8000`

如果端口冲突，可以改：

```powershell
uv run researchos web --port 8010 --frontend-port 5180
```

### 只启动 API

```powershell
uv run uvicorn app.api.app:create_app --factory --reload
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health
```

## 常见工作流

### CLI

创建项目：

```powershell
uv run researchos --db-path data\researchos.db create-project `
  --project-id p1 `
  --name "ResearchOS Demo" `
  --description "Minimal local demo"
```

创建任务：

```powershell
uv run researchos --db-path data\researchos.db create-task `
  --task-id t1 `
  --project-id p1 `
  --kind paper_ingest `
  --goal "Read one paper summary" `
  --owner demo `
  --input-payload "{\"topic\":\"robustness\",\"source_summary\":{\"title\":\"Example Paper\",\"abstract\":\"A compact summary.\",\"setting\":\"classification\"}}"
```

调度和检查：

```powershell
uv run researchos --db-path data\researchos.db dispatch-task --task-id t1
uv run researchos --db-path data\researchos.db list-tasks --project-id p1
uv run researchos --db-path data\researchos.db project-dashboard --project-id p1
uv run researchos --db-path data\researchos.db inspect-routing-system
uv run researchos --db-path data\researchos.db provider-health
```

打开终端控制台：

```powershell
uv run researchos
uv run researchos console
uv run ros
```

### Web UI

Web UI 和 CLI 是同一套控制流程，只是入口更引导化：

- 用自然语言输入研究方向
- 自动跑 `paper_ingest` 和 `gap_mapping`
- 在 `human_select` 停下
- 用右侧 LLM 对话栏讨论候选方向
- 选定方向后继续推进 spec、build、review、draft

## Provider 配置

最小环境变量示例：

```powershell
$env:RESEARCHOS_PROVIDER = "claude"
$env:RESEARCHOS_PROVIDER_MODEL = "sonnet"
$env:RESEARCHOS_MAX_STEPS = "12"
```

当前支持的 provider family：

- `codex`
- `claude`
- `gemini`
- `local`

`local` 适合演示、CI 和确定性测试。只有在对应 CLI 已安装并且登录可用时，才建议切到 `codex`、`claude` 或 `gemini`。

## 目录结构

主要目录：

- [`app/`](app/)：运行时、agent、service、API、CLI
- [`frontend/`](frontend/)：React 前端
- [`prompts/`](prompts/)：仓库内维护的 prompt
- [`skills/`](skills/)：仓库内维护的 skill
- [`examples/`](examples/)：可直接复制的示例
- [`docs/`](docs/)：配置和发布说明

## 持久化状态放在哪

ResearchOS 把持久化状态分成两层：

- 数据库：项目和任务
- `registry/` 下的文件：paper card、gap map、run、claim、lesson、verification、freeze、artifact

关键路径：

- `registry/paper_cards.jsonl`
- `registry/gap_maps.jsonl`
- `registry/claims.jsonl`
- `registry/runs.jsonl`
- `registry/lessons.jsonl`
- `registry/verifications.jsonl`
- `registry/artifacts.jsonl`
- `registry/freezes/`
- `artifacts/`
- `state/provider_health.yaml`

## 常用 API

常用操作面接口：

- `GET /projects/{project_id}/dashboard`
- `GET /routing/system`
- `GET /routing/tasks/{task_id}`
- `GET /providers/health`
- `GET /artifacts`
- `GET /artifacts/{artifact_id}`
- `GET /artifacts/{artifact_id}/inspect`
- `GET /verifications/summary`
- `GET /audit/summary`
- `POST /guide/start`
- `POST /guide/discuss-direction`
- `POST /guide/adopt-direction`
- `POST /projects/{project_id}/autopilot`

## 生产栈

生产部署目前围绕这些组件：

- FastAPI
- Postgres
- Redis
- Celery worker

启动：

```powershell
docker compose up -d --build
```

## 示例与文档

- [`examples/README.md`](examples/README.md)
- [`docs/operator_setup.md`](docs/operator_setup.md)
- [`docs/release_checklist.md`](docs/release_checklist.md)
- [`CHANGELOG.md`](CHANGELOG.md)

## CI

GitHub Actions 当前会跑：

- `uv` 安装依赖
- Python 导入检查
- 单元测试
- local provider 的 API smoke
- 一条小型 CLI smoke path

工作流文件：

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

</details>
