# ResearchOS

<div align="center">

[English](README.md) | [简体中文](README.zh-CN.md)

### 面向可信 AI 研究的执行操作系统

把 `idea -> hidden agent steps -> draft` 这种黑盒流程，升级成一条有状态机、有实验修复、有指标落地、有人工控制面的研究闭环。

![Python](https://img.shields.io/badge/python-3.11+-0f172a?style=for-the-badge&logo=python&logoColor=white)
![UV](https://img.shields.io/badge/package%20manager-uv-2dd4bf?style=for-the-badge)
![Operator](https://img.shields.io/badge/operator-first-true-c2410c?style=for-the-badge)
![Workflow](https://img.shields.io/badge/proof%20chain-guide%20to%20console-2563eb?style=for-the-badge)

</div>

## 为什么它不一样

大多数 research agent 追求的是“再自动一点”。

ResearchOS 追求的是更难也更值钱的事情：

- 团队能不能看见系统到底做了什么
- 实验失败后能不能从正确 checkpoint 恢复
- 草稿里的每一个数字能不能追溯到 artifact
- operator 能不能在批准之前比较分支和证据

ResearchOS 给出的不是一句口号，而是一套真正可操作的产品面。

## 产品故事

```text
idea -> guide -> typed flow -> experiment repair loop -> verified writing -> operator console
```

它不是自动论文机。

它是一个 **Trustworthy Research Execution System**，帮助研究团队：

- 把模糊目标收敛成可执行研究方向
- 用显式 `gate`、`rollback`、`retry`、`pause`、`resume`、`pivot`、`refine` 管理流程
- 用 diagnosis-driven experiment loop 代替盲目重试
- 在写作前把数字绑定到真实 run、artifact、freeze 和证据
- 通过 operator console 实时查看事件、checkpoint、分支和 provider 健康状态

## 从黑盒 Agent 到研究控制面

```mermaid
flowchart LR
    A["自然语言研究目标"] --> B["Guide"]
    B --> C["Typed Flow State Machine"]
    C --> D["Diagnosis-Driven Experiment Loop"]
    D --> E["Verified Metrics Registry"]
    E --> F["Writer"]
    F --> G["Operator Console"]
    G --> H["批准、恢复、比较或转向"]
```

## 核心产品面

| 产品面 | 做什么 | 为什么重要 |
|---|---|---|
| `Guide` | 拆解问题、抓取 seed papers、在人类该决策时停在 `human_select` | 研究起点不再靠 agent 漂移 |
| `Typed Flow` | 持久化阶段、迁移、checkpoint 和决策历史 | 恢复与审计成为内建能力 |
| `Experiment Loop` | 诊断失败、执行有限修复、记录尝试历史、提升最佳结果 | 实验从脆弱脚本变成可恢复闭环 |
| `Verified Metrics Registry` | 把数字绑定到 run、artifact、freeze 和证据包 | 未落地指标不能进入论文 |
| `Operator Console` | 暴露 flow snapshot、event stream、branch compare、checkpoint resume 和 health | 自动化扩大后仍然可控、可见 |

## ResearchOS 强在哪

ResearchOS 不靠“更像魔法”取胜。

它靠“更可信的自动化”取胜。

| 维度 | 常见 autonomous research agent | ResearchOS |
|---|---|---|
| 核心叙事 | 自动化更多步骤 | 负责任地操作化研究 |
| 流程控制 | 隐式 task chaining | typed state machine |
| 失败处理 | 重试或重生 | 诊断、修复、提升最佳结果 |
| 草稿中的数字 | 直接信任 agent 输出 | 必须经过 grounded metrics |
| 人类角色 | 事后审阅 | 通过显式 checkpoint 介入 |
| 产品形态 | agent workflow | research execution system |

## 不是文案，是证明链

仓库里已经有一条完整的 integration proof chain，覆盖：

`guide -> flow -> experiment -> writer -> operator console`

它会验证：

- guided start 与 direction adoption
- autopilot 在分支和实验阶段的推进
- 草稿输出前的 verified metrics grounding
- operator-facing 的 branch compare、event stream 和 flow inspection

关键入口：

- [tests/integration/test_research_proof_chain.py](tests/integration/test_research_proof_chain.py)
- [tests/integration/test_dispatch_workflow.py](tests/integration/test_dispatch_workflow.py)
- [scripts/run_operator_benchmark.py](scripts/run_operator_benchmark.py)

## 代码地图

| 区域 | 关键文件 |
|---|---|
| Flow 状态机 | [app/workflows/research_flow.py](app/workflows/research_flow.py), [app/services/project_service.py](app/services/project_service.py) |
| 实验修复闭环 | [app/tools/experiment_runner.py](app/tools/experiment_runner.py) |
| 可信写作 | [app/services/verified_metrics_registry.py](app/services/verified_metrics_registry.py), [app/agents/writer.py](app/agents/writer.py) |
| Operator 检视层 | [app/services/operator_inspection_service.py](app/services/operator_inspection_service.py), [app/api/app.py](app/api/app.py), [frontend/src/App.tsx](frontend/src/App.tsx) |

## 快速开始

环境要求：

- Python `3.11+`
- [uv](https://docs.astral.sh/uv/)
- Node.js `18+`

```bash
uv sync --dev
cd frontend
npm install
cd ..
uv run researchos --db-path data/researchos.db init-db
uv run researchos web
```

打开 `http://127.0.0.1:5173`。

本地确定性模式：

```bash
export RESEARCHOS_PROVIDER=local
export RESEARCHOS_PROVIDER_MODEL=deterministic-reader
```

CLI provider 模式：

```bash
export RESEARCHOS_PROVIDER=claude
export RESEARCHOS_PROVIDER_MODEL=sonnet
export RESEARCHOS_WORKSPACE_ROOT=$(pwd)
```

仓库当前支持的 provider family 包括 `claude`、`codex`、`gemini` 和 `local`。

## 仓库结构

```text
app/
  agents/        专职研究 agents
  api/           FastAPI 控制面
  services/      registries、freezes、approvals、operator inspection
  tools/         实验执行、验证、检索辅助
  workflows/     typed research flow state machine
frontend/
  src/           operator console 与 workspace UI
scripts/
  run_operator_benchmark.py
tests/
  integration/   端到端证明链
  unit/          service、API 与 agent 回归测试
docs/
  showcase/      对外展示材料
```

## 仓库里的营销文案资产

如果你想看对外产品叙事，而不是工程说明：

- [docs/github_project_intro.md](docs/github_project_intro.md)
- [docs/website_copy.md](docs/website_copy.md)
- [docs/comparison/AutoResearchClaw.md](docs/comparison/AutoResearchClaw.md)

## 当前状态

ResearchOS 已经具备：

- typed flow control
- checkpoint-aware resume
- diagnosis-driven experiment repair
- verified metrics grounding
- branch comparison 和 operator inspection
- integration proof-chain coverage

下一步真正该放大的，不是更黑盒的自动化。

而是围绕同一个可信执行内核做更强包装：公开 benchmark、showcase project，以及更多外部入口。
