# ResearchOS

<p align="right">
  <a href="README.md"><img src="https://img.shields.io/badge/lang-English-blue?style=flat-square" /></a>
  <a href="README.zh-CN.md"><img src="https://img.shields.io/badge/语言-中文-red?style=flat-square" /></a>
</p>

> 一个多 Agent 研究工作流系统，将研究想法从文献检索推进到可投稿草稿，并在每个关键决策节点保留结构化的人工介入。

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white" />
  <img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" />
  <img src="https://img.shields.io/badge/FastAPI-0.135-009688?style=flat-square&logo=fastapi&logoColor=white" />
  <img src="https://img.shields.io/badge/LLM_支持-Claude_·_Codex_·_Gemini-blueviolet?style=flat-square" />
  <img src="https://img.shields.io/badge/Agent_数量-10_个专用-orange?style=flat-square" />
  <img src="https://img.shields.io/badge/流水线-16_阶段-green?style=flat-square" />
</p>

---

## 这个系统解决什么问题？

现有的自动化研究系统（AI Scientist、AgentLaboratory、GPT-Researcher）存在两类根本性局限：
- **完全自主型**：无结构化人工监督，Agent 的决策研究者无法审计和信任
- **仅检索型**：能找论文，但无法设计、运行或分析实验

ResearchOS 基于一个不同的前提：**研究是人机协作，而不是人被机器替代**。Agent 承担高重复性的机械工作（文献筛选、代码生成、引用验证、结果分析），人类保留对真正重要决策的控制权（研究方向选择、实验设计审批、结论验证）。

最终结果：系统中的每一个产物——论文卡片、研究空白图谱、实验规格、结论、经验记录——都是可追溯、可验证、可复现的。

---

## 系统架构

```
研究目标（自然语言输入）
         │
         ▼
  QueryDecomposer ──► arXiv API + Semantic Scholar
  （子问题分解）              （按引用数加权检索）
         │
         ▼
  ┌─ ReaderAgent ──────────────────────────────────────────────┐
  │  从论文中提取结构化论文卡片，包含证据引用               │
  │  拒绝：表格条目、图表引用、编码异常内容                 │
  └────────────────────────────────────────────┬───────────────┘
                                               │
                                               ▼
  ┌─ MapperAgent + ReviewerAgent（辩论验证）───────────────────┐
  │  从 4 个维度聚类研究空白：                               │
  │  方法空白 / 数据空白 / 评估空白 / 算力空白               │
  │  每个候选方向在呈现给人类前由挑战 Agent 质疑             │
  └────────────────────────────────────────────┬───────────────┘
                                               │
                                    ┌──────────▼──────────┐
                                    │  ★ 人工决策节点     │
                                    │  方向选择工作台     │
                                    │  + LLM 顾问对话     │
                                    └──────────┬──────────┘
                                               │
                                               ▼
  ┌─ HypothetistAgent ─────────────────────────────────────────┐
  │  将选定方向转化为可证伪的研究假设                        │
  │  每个假设必须包含具体的证伪条件                         │
  └────────────────────────────────────────────┬───────────────┘
                                               │
                                               ▼
  ┌─ BuilderAgent ─────────────────────────────────────────────┐
  │  生成自包含的 Python 实验脚本                            │
  │  硬件感知：根据 GPU 内存和 CPU 情况自动调整参数          │
  └────────────────────────────────────────────┬───────────────┘
                                               │
                                               ▼
  ┌─ ExperimentRunner（5 轮自修复）────────────────────────────┐
  │  OOM       → 自动降低 batch_size                         │
  │  NaN loss  → LLM 辅助修复优化器                         │
  │  ImportError → 自动安装缺失依赖                          │
  └────────────────────────────────────────────┬───────────────┘
                                               │
                                               ▼
  ┌─ AnalystAgent ─────────────────────────────────────────────┐
  │  PROCEED（置信度 > 0.7）──► WriterAgent                  │
  │  REFINE + patch          ──► 返回 BuilderAgent            │
  │  PIVOT                   ──► 返回 MapperAgent             │
  └────────────────────────────────────────────┬───────────────┘
                                               │
                      ┌────────────────────────┼──────────────────┐
                      ▼                        ▼                  ▼
               ReviewerAgent            VerifierAgent      ArchivistAgent
            （ML 公平性检查）          （证据链验证）    （经验 + 知识库）
                      │
                      ▼
                WriterAgent
          （LaTeX / Markdown 草稿，
           3 轮引用验证与修复，
           会议投稿专项检查清单）
```

---

## 关键设计决策

### 1. 三层技能架构
每个 Agent 由三层叠加的指令控制：
- **角色 prompt**（`prompts/roles/`）— 定义该角色的职责边界和专业规范
- **Agent prompt**（`prompts/`）— 针对具体任务类型的行为规则，包含反例和硬拒绝标准
- **技能文件**（`skills/`）— 具体的输出模板、负面示例和 LLM 在返回结果前必须执行的自检标准

这种分层意味着技能质量可以独立于 Agent 编排逻辑进行迭代，且技能文件可以跨不同底层 LLM（Claude、Codex、Gemini）复用。

### 2. 数据库中介的 Agent 通信
Agent 之间不直接调用彼此。所有跨 Agent 状态通过类型化的注册表流转：

```
TaskRegistry → PaperCardRegistry → GapMapRegistry → FreezeRegistry → ArtifactRegistry
```

这使系统完全可观测（任意时刻所有中间产物都可读）、可恢复（任务可从任意检查点重试）、可审计（从原始输入到最终结论的完整溯源链）。

### 3. 结构化人工检查点
`human_select` 是一个一等公民的任务类型——不是 UI 功能，也不是降级状态。流水线会**暂停**，直到人类做出经过验证的决策后才继续。其他检查点（`FREEZE_SPEC`、`AUDIT_RESULTS`）可按项目配置为 `required`（必须等待人工）或 `optional`（置信度足够时自动推进）。人工审批支持附带条件——在 UI 中输入的约束会直接注入到下游任务的上下文中。

### 4. 自进化知识库
经验不是日志。每个任务完成后，`ArchivistAgent` 会评估执行结果是否包含可复用的洞见——必须是可泛化的、有证据支撑的、能在不同上下文中重用的。经验存储在结构化知识库中（4个类别：发现、决策、文献、开放问题），30天不被命中则自动衰减。每个新任务在执行前会检索最相关的 5 条历史经验，使系统在熟悉领域中随时间持续改进。

### 5. 实验完整性门控
`ReviewerAgent` 在任何结论被允许进入论文草稿之前，执行专门的 ML 公平性检查（阻断级别）：
- 提出方法和所有 baseline 是否使用相同数据集划分？
- 如果使用了数据增强，baseline 是否获得了相同的增强预算？
- 超参数选择过程中是否存在测试集泄漏？
- 报告的精度是否来自 cherry-pick 的 epoch，还是预先声明的选择规则？
- 对于类别不平衡数据集，是否仅报告了普通准确率而未补充类别感知指标？

不满足以上条件的结论会被阻断，并附带具体的整改说明。

---

## Agent 目录

| Agent | 角色 | 核心职责 |
|-------|------|---------|
| **ReaderAgent** | 文献馆员 | 文献筛选 → 带证据引用的结构化论文卡片 |
| **MapperAgent** | 综合分析师 | 论文卡片 → 研究空白聚类 + 带评分的候选方向 |
| **HypothetistAgent** | 假设生成者 | 研究空白 → 可证伪、可操作的研究假设 |
| **BuilderAgent** | 实验执行者 | 实验规格 → 可运行的硬件感知 Python 代码 |
| **AnalystAgent** | 结果分析师 | 运行结果 → PROCEED / REFINE / PIVOT 决策（附数字依据）|
| **ReviewerAgent** | 质量审查员 | 产物 → 阻断/警告级别审查报告（含 ML 公平性清单）|
| **VerifierAgent** | 证据验证员 | 结论 → 证据链验证报告（明确声明验证范围）|
| **WriterAgent** | 论文写作者 | 冻结证据 → 论文章节 / 完整草稿（含引用修复）|
| **ArchivistAgent** | 档案管理员 | 运行结果 → 可复用经验 + 知识库条目 |
| **BranchManagerAgent** | — | 多分支实验协调、评分与剪枝 |

---

## 技术栈

| 层次 | 技术选型 |
|------|---------|
| 后端运行时 | Python 3.11、FastAPI、SQLAlchemy |
| 数据存储 | SQLite（本地开发）/ PostgreSQL（生产环境）|
| 任务队列 | Celery + Redis |
| 前端 | React 18、TypeScript、Vite、Lucide |
| LLM 接入 | Claude CLI、Codex CLI、Gemini CLI（子进程方式，无需直接 API）|
| 论文检索 | arXiv API、Semantic Scholar API |
| 容器化 | Docker Compose |
| CI | GitHub Actions |
| 包管理 | uv |

---

## 快速开始

**前置要求：** Python 3.11+、[uv](https://docs.astral.sh/uv/)、Node.js 18+

```bash
# 安装依赖
uv sync --dev
cd frontend && npm install && cd ..

# 初始化本地数据库
uv run researchos --db-path data/researchos.db init-db

# 启动（API 服务在 :8000，前端在 :5173）
uv run researchos web
```

打开 `http://127.0.0.1:5173`，UI 会引导你从一个自然语言研究目标开始第一个项目。

**使用真实 LLM Provider**（需要对应 CLI 已安装并完成认证）：

```bash
export RESEARCHOS_PROVIDER=claude          # 或 codex / gemini
export RESEARCHOS_PROVIDER_MODEL=sonnet
export RESEARCHOS_WORKSPACE_ROOT=$(pwd)
```

**演示和 CI 模式**（确定性输出，无需任何 API Key）：

```bash
export RESEARCHOS_PROVIDER=local
export RESEARCHOS_PROVIDER_MODEL=deterministic-reader
```

自定义端口：

```bash
uv run researchos web --port 8010 --frontend-port 5180
```

---

## 引导式研究工作流

前端界面围绕研究流水线本身构建，而不是底层数据模型。

```
第 1 步：用自然语言输入研究目标
─────────────────────────────────────────────────────────────────
系统将目标分解为互补的检索子查询，
从 arXiv + Semantic Scholar 按引用数加权抓取论文，
自动生成结构化论文卡片。

第 2 步：带对抗辩论的空白分析
─────────────────────────────────────────────────────────────────
MapperAgent 将证据聚类为研究空白。
挑战 Agent 对每个候选方向进行辩论，弱点
会与候选方向一同展示，使人工决策更有依据。

第 3 步：★ 人工决策：方向选择工作台
─────────────────────────────────────────────────────────────────
- 新颖度 × 可行性散点矩阵
- 每个方向的辩论弱点内联展示
- LLM 顾问对话，深度讨论可行性
- 可选：为审批附加约束条件（约束直接注入下游任务）

第 4 步：自动驾驶推进至下一检查点
─────────────────────────────────────────────────────────────────
假设生成 → 规格冻结 → 实验执行 → 结果分析
每个阶段可配置为 required（必须停等人工）或
optional（置信度足够时自动推进）。

第 5 步：生成论文草稿
─────────────────────────────────────────────────────────────────
LaTeX 或 Markdown 格式，含 3 轮引用验证修复，
会议专项检查清单（NeurIPS/ICLR），以及诚实的
局限性章节。
```

---

## 项目结构

```
ResearchOS/
├── app/
│   ├── agents/          # 10 个专用 Agent（reader、mapper、builder……）
│   ├── api/             # FastAPI 路由和 Schema
│   ├── cli.py           # CLI 入口（uv run researchos）
│   ├── core/            # 枚举、配置、流水线阶段定义
│   ├── db/              # SQLAlchemy 模型、Alembic 迁移
│   ├── providers/       # Claude / Codex / Gemini / Local CLI 封装
│   ├── routing/         # Provider 健康检查、路由策略、降级链
│   ├── roles/           # 角色契约、绑定关系、注册表
│   ├── services/        # 所有领域服务（gap maps、lessons、KB……）
│   ├── skills/          # 技能规格和注册表
│   └── tools/           # arXiv、Semantic Scholar、实验运行器……
├── frontend/
│   └── src/
│       ├── components/  # OverviewTab、OperationsTab、RegistryTab、CreateTab
│       └── App.tsx
├── prompts/             # Agent prompts + 角色 prompts + 顾问 prompts
├── skills/              # 各角色的 SKILL.md（模板、反例、自检清单）
├── registry/            # 持久化 JSONL 状态（论文卡片、空白图谱、经验……）
├── tests/
│   ├── unit/
│   └── integration/
└── docker-compose.yml
```

---

## 数据模型

ResearchOS 将研究产物视为有类型、有版本的一等对象，而不是聊天记录或扁平文件。

| 对象 | 记录内容 |
|------|---------|
| `PaperCard` | 问题定义、方法摘要、最强实验结果、数据集、指标、证据引用 |
| `GapMap` | 聚类研究空白，含新颖度/可行性评分和每个方向的辩论弱点 |
| `TopicFreeze` | 所选研究方向及决策依据的不可变快照 |
| `SpecFreeze` | 不可变实验规格：假设、baseline、数据集、指标、成功/失败标准 |
| `RunManifest` | 完整执行记录：配置、随机种子、数据集快照、产物、指标 |
| `Claim` | 与具体 run 绑定的经验断言，含风险等级和人工审批状态 |
| `Lesson` | 来自过往任务的可复用洞见——有证据支撑、命中计数、30 天衰减 |
| `KnowledgeBase` | 跨项目结构化知识：发现、决策、文献摘要、开放问题 |

---

## API 接口（精选）

```
POST  /guide/start                    从自然语言目标启动新研究项目
POST  /guide/discuss-direction        与 LLM 顾问讨论候选方向的可行性
POST  /guide/adopt-direction          锁定研究方向，创建 topic freeze
POST  /projects/{id}/autopilot        将项目推进至下一个人工检查点

GET   /projects/{id}/dashboard        项目完整状态快照
GET   /projects/{id}/events/stream    实时任务状态更新的 SSE 推送流
GET   /routing/system                 当前 Provider 健康状态和路由策略
GET   /providers/health               各 Provider 状态、冷却时间、失败计数

POST  /tasks/{id}/dispatch            手动调度一个排队中的任务
GET   /artifacts/{id}/inspect         查看产物内容和元数据
GET   /audit/summary                  所有结论和运行的审计发现汇总
GET   /verifications/summary          所有项目的证据验证状态汇总
```

---

## 运行测试

```bash
# 单元测试
uv run pytest tests/unit -v

# 集成测试（使用确定性本地 Provider，无需 API Key）
uv run pytest tests/integration -v

# 编译检查 + 前端构建（与 CI 保持一致）
uv run python -m compileall app
cd frontend && npm run build
```

---

## 生产部署

```bash
# 完整服务栈：FastAPI + PostgreSQL + Redis + Celery Worker
docker compose up -d --build

# 健康检查
curl http://localhost:8000/health
```

生产环境将 SQLite 替换为 PostgreSQL，并增加 Celery Worker 负责异步任务调度。API 接口与本地开发环境完全一致。

---

## 与同类系统对比

| 特性 | ResearchOS | AI Scientist v2 | GPT-Researcher | AgentLaboratory |
|------|:---:|:---:|:---:|:---:|
| 结构化人工检查点 | ✅ | ❌ | ❌ | ⚠️ |
| 实验自修复循环 | ✅ | ⚠️ | ❌ | ✅ |
| 跨项目知识积累 | ✅ | ❌ | ❌ | ❌ |
| 引用验证 + 修复 | ✅ | ⚠️ | ❌ | ❌ |
| ML 公平性审查门控 | ✅ | ❌ | ❌ | ⚠️ |
| Gap 对抗辩论验证 | ✅ | ❌ | ❌ | ❌ |
| 操作者 Web UI | ✅ | ❌ | ❌ | ❌ |
| 多 Provider 路由 + 降级 | ✅ | ✅ | ✅ | ⚠️ |
| 完整产物溯源链 | ✅ | ⚠️ | ❌ | ⚠️ |

---

## 开发路线图

- [ ] HypothetistAgent 接入主调度流（已完成设计，尚未接入）
- [ ] 分支树实验探索（树搜索风格，多分支并行）
- [ ] LaTeX 编译生成 PDF
- [ ] 跨项目知识图谱可视化
- [ ] 实验结果对比看板
- [ ] 所有注册表从 JSONL 迁移至 SQLite 主存储

---

*Python 3.11 · FastAPI · React 18 · SQLAlchemy · 多 Provider LLM 路由*
