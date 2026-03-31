# 何宗霖

求职意向：Agent Engineering / AI Agent Engineer  
电话：13325744856

## 个人简介

温州肯恩大学计算机科学与技术本科在读，目标岗位为 Agent Engineering。以 `ResearchOS` 为核心项目，具备从 0 到 1 设计并实现 AI Agent 执行系统的经验，重点关注工作流编排、状态机控制、实验自动修复、结果可验证性与人机协同控制台。熟悉 Python 后端、LLM/Agent 系统设计、React 前端与自动化测试，能够把黑盒式 Agent 流程拆解为可追溯、可恢复、可干预的工程系统。

## 教育背景

**温州肯恩大学**  
计算机科学与技术 本科 | 2024 - 2028

## 科研经历

### 高志强教授课题组 | Research Assistant

时间：2025.09 - 至今

- 主导时间序列鲁棒测试时适应（Test-Time Adaptation）方向科研工作，围绕 source-free online TTA、结构性扰动与鲁棒适配方法完成问题定义、方案推进、实验验证与论文撰写。
- 独立完成论文《NuSTAR: Robust Test-Time Adaptation via Stochastic Smooth Adversarial Warping》主体写作，并负责从实验设计、baseline 复现、结果分析到投稿稿整理的完整研究流程。
- 复现并比较多个基线方法，围绕时间序列分布偏移、自然结构性损坏（Natural Structural Corruption）和在线自适应场景开展实验分析，形成可支撑论文结论的结果整理与技术论证。
- 在科研过程中系统提升了文献阅读、实验复现、研究叙事、学术写作与结果归纳能力，能够独立推进机器学习研究项目的主要技术环节。

## 论文与学术输出

- `NuSTAR: Robust Test-Time Adaptation via Stochastic Smooth Adversarial Warping`，在投论文，负责主体写作、baseline 复现与实验推进。

## 核心技能

- 编程语言：Python 3.11、TypeScript
- Agent Engineering：Agent 工作流编排、Typed State Machine、Checkpoint/Resume、Failure Diagnosis、Best-Result Promotion、Human-in-the-Loop
- 后端与基础设施：FastAPI、SQLAlchemy、Celery、Redis、SQLite/PostgreSQL、Docker、uv
- 前端：React 18、TypeScript、Vite、EventSource/SSE
- 工程化：Pytest、集成测试、CLI 工具、接口设计、审计与验证链路建设

## 项目经历

### ResearchOS | Trustworthy AI Research Execution System

角色：独立开发 / 核心工程负责人  
技术栈：Python、FastAPI、React、TypeScript、SQLAlchemy、Celery、Redis、Pytest、Docker

- 从 0 到 1 设计并实现面向可信 AI Research 的 Agent 执行系统，将研究流程抽象为 `guide -> typed flow -> experiment -> verified metrics -> writer -> operator console` 的闭环，解决传统 Agent 系统黑盒、脆弱、难以追责的问题。
- 设计 Typed Research Flow State Machine，显式建模 `gate / rollback / retry / pause / resume / pivot / refine` 等流程控制动作，使 Agent 任务具备状态推进、失败回退、人工介入和检查点恢复能力。
- 基于 FastAPI 构建控制平面，沉淀 `70+` 个 API 路由，覆盖项目管理、任务调度、讨论会话、审批、审计、验证、分支比较和事件流等核心模块。
- 实现 Diagnosis-Driven Experiment Runner，对实验脚本失败进行分类诊断与自动修复，支持 OOM、超时、缺失依赖、数值发散等场景，并保留 attempt history 与 best-result promotion 机制。
- 构建 Verified Metrics Registry，将运行结果、实验产物元数据和外部结果统一注册到可验证指标表中，在写作阶段自动校验文本中的数值是否具备证据绑定，降低 unsupported claims 进入草稿的风险。
- 开发 React Operator Console，支持项目总览、任务流转、Provider 健康检查、Branch Comparison、Artifact / Gap Map / Paper Card 查看以及实时事件刷新，提升 Agent 系统的人机协同与运行可见性。
- 建立以 proof-chain 为核心的测试体系，项目包含 `110+` 个测试文件，并覆盖 `guide -> flow -> experiment -> writer -> operator console` 的关键集成链路，提高复杂 Agent Workflow 的回归可靠性。
- 围绕 “trustworthy AI research” 完成产品定位、架构设计与工程落地，将系统从普通自动化脚本提升为具备控制平面、验证链路和操作台的 research execution system。

## 项目亮点

- 具备完整 Agent Runtime 视角：不仅实现任务执行，还覆盖状态管理、失败恢复、审计、验证和人工控制。
- 具备系统工程能力：同时完成后端控制平面、前端操作台、实验执行模块与测试体系。
- 具备产品抽象能力：能从具体功能实现上升到 Agent 系统的可靠性、可见性和可验证性设计。

## 荣誉与成绩

- 院长二等奖学金
- 雅思 6.5
- GRE 322

## 适合 Agent Engineering 岗位的简历项目描述精简版

- 独立开发 `ResearchOS`，构建面向 AI Research 的 Agent 执行系统，将研究流程建模为可审计、可恢复的 Typed Workflow，支持 gate、rollback、retry、pause、resume 等流程控制。
- 基于 FastAPI 搭建 `70+` 控制平面接口，覆盖任务调度、审批、审计、验证、分支比较与事件流，形成完整 Agent Runtime 管理能力。
- 实现实验失败诊断与自动修复模块，支持 OOM、超时、依赖缺失、数值异常等场景，并保留 best-result promotion 机制。
- 构建 Verified Metrics Registry 与 React Operator Console，提升 Agent 输出的可验证性与运行过程的可见性。

## 可补充信息

- 邮箱
- GitHub / 项目主页
- 竞赛、论文、开源贡献或课程项目
