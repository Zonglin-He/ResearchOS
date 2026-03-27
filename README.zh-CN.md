# ResearchOS

<p align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-English-blue?style=flat-square" alt="English" /></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/lang-中文-red?style=flat-square" alt="中文" /></a>
</p>

> 面向可信 AI 研究的研究执行系统。

ResearchOS 要解决的不是“怎么再多自动化几步”，而是“怎么把研究流程变成可追踪、可恢复、可验证的系统”。  
它不是自动论文机，而是把研究从黑盒 agent workflow，升级成一个 operator 可见、证据可查、状态可控的执行闭环。

## 定位

ResearchOS 的核心定位是：

**Trustworthy Research Execution System**

也就是：

- 从模糊目标出发，逐步引导到可执行研究方向
- 用显式状态机管理研究流，而不是靠隐式 agent 串联
- 用诊断式实验修复替代盲目重试
- 用指标落地和证据绑定约束写作
- 用 operator console 让人类实时接管关键节点

## 为什么要做这个

很多 research agent 追求的是“更自动”。  
但真实研究团队还需要另外四件事：

- 可见性：系统做了什么、什么时候做的、为什么这么做
- 可恢复性：失败后从哪里继续
- 可问责性：论文中的数字和结论到底来自哪里
- 可控性：人类在关键节点如何介入，而不是事后补救

ResearchOS 的答案不是再堆一层 agent，而是把研究流程操作系统化。

一句话概括：

**不要盲目自动化研究，而要负责任地操作化研究。**

## 产品故事

ResearchOS 把这条黑盒链路：

`idea -> hidden agent steps -> draft`

改造成这条可验证链路：

`guide -> flow -> experiment -> writer -> operator console`

这五段不是功能列表，而是产品本体。

### 1. Guide

从自然语言研究目标开始。系统会分解查询、抓取 seed papers、生成 gap candidates，并在 `human_select` 节点停下，让方向选择保持人类可见。

### 2. Flow

研究流程不是一串松散 task string，而是持久化的 typed state machine。  
当前 flow 明确支持：

- `gate`
- `rollback`
- `retry`
- `pause`
- `resume`
- `pivot`
- `refine`

### 3. Experiment

实验执行不是“报错了再跑一次”。ResearchOS 会记录尝试历史，诊断失败原因，执行有限修复，并在多个成功尝试之间提升最佳结果。

### 4. Writer

写作阶段受到证据约束。Writer 会结合：

- citation verification
- verified metrics registry
- metric grounding report
- results freeze

未落地的数字不会直接进入草稿。

### 5. Operator Console

操作台不是辅助页面，而是控制面。它暴露：

- flow snapshot
- run event stream
- branch compare
- checkpoint resume
- approvals
- provider health

## 核心能力

### Typed Flow Control

研究流以显式状态、决策和 checkpoint requirement 形式持久化。

关键代码：

- [app/workflows/research_flow.py](app/workflows/research_flow.py)
- [app/services/project_service.py](app/services/project_service.py)

### Diagnosis-Driven Experiment Repair

实验执行链支持失败诊断、repair action、attempt history 和 best-result promotion。

关键代码：

- [app/tools/experiment_runner.py](app/tools/experiment_runner.py)

### Verified Metrics Registry

论文中的数字必须能回溯到 run manifest、artifact metadata 或 approved results freeze。

关键代码：

- [app/services/verified_metrics_registry.py](app/services/verified_metrics_registry.py)
- [app/agents/writer.py](app/agents/writer.py)

### Operator-First Inspection

ResearchOS 从一开始就是面向 operator 的系统，而不是只面向后台 agent。

关键代码：

- [app/services/operator_inspection_service.py](app/services/operator_inspection_service.py)
- [app/api/app.py](app/api/app.py)
- [frontend/src/App.tsx](frontend/src/App.tsx)

## 它和常见 Autonomous Research Agent 的区别

ResearchOS 不靠“更像黑盒自动论文机”取胜。  
它靠“更可信的自动化”取胜。

| 维度 | 常见 autonomous research agent | ResearchOS |
|---|---|---|
| 叙事中心 | 自动跑更多步骤 | 把每一步做成可检查、可恢复的执行系统 |
| 流程控制 | 隐式 task chaining | typed workflow state machine |
| 失败处理 | 重试或重生成 | 诊断、修复、提升最佳结果 |
| 草稿数字 | 常常直接信任 agent 输出 | 必须经过 verified metrics grounding |
| 人类角色 | 事后批准 | 显式 checkpoint 与 operator console |
| 产品形态 | agent workflow | research execution system |

## 端到端证明链

当前仓库已经包含一条完整 integration proof chain，覆盖：

`guide -> flow -> experiment -> writer -> operator console`

它会验证：

- guide start 与 direction adoption
- autopilot 在 branch planning 和 experiment fanout 中的推进
- result grounding 与 draft generation
- operator-facing 的 branch compare、event stream 和 flow surface

相关测试：

- [tests/integration/test_research_proof_chain.py](tests/integration/test_research_proof_chain.py)
- [tests/integration/test_dispatch_workflow.py](tests/integration/test_dispatch_workflow.py)

基准脚本：

- [scripts/run_operator_benchmark.py](scripts/run_operator_benchmark.py)

## 快速开始

环境要求：

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- Node.js 18+

```bash
uv sync --dev
cd frontend
npm install
cd ..
uv run researchos --db-path data/researchos.db init-db
uv run researchos web
```

打开 `http://127.0.0.1:5173`。

### Provider 配置

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

仓库里还支持 `codex` 与 `gemini` provider family。

## 仓库结构

```text
app/
  agents/        专职研究 agent
  api/           FastAPI 控制面
  services/      registries、freezes、operator inspection
  tools/         实验执行、验证、检索工具
  workflows/     typed research flow state machine
frontend/
  src/           operator console 与 workspace UI
scripts/
  run_operator_benchmark.py
tests/
  integration/   端到端证明链
  unit/          service、API、agent 回归测试
docs/
  showcase/      对外展示材料
```

## 仓库内的营销文案资产

如果你需要的是对外讲产品，而不是对内讲工程，请看：

- [docs/github_project_intro.md](docs/github_project_intro.md)
- [docs/website_copy.md](docs/website_copy.md)
- [docs/comparison/AutoResearchClaw.md](docs/comparison/AutoResearchClaw.md)

## 当前状态

ResearchOS 已经具备：

- typed flow control
- checkpoint-aware resume
- diagnosis-driven experiment repair
- verified metrics grounding
- branch comparison 与 operator inspection
- integration 证明链覆盖

接下来真正需要放大的，不是“更黑盒的自动化”，而是：

- 更强的公开 benchmark
- 更完整的 showcase project
- 更丰富的外部入口

但这些都应该建立在同一个核心上：

**可信的研究执行，而不是不可审计的自动论文生成。**
