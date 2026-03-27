import { useEffect, useRef, useState } from "react";
import { Database, FlaskConical, PanelRightClose, PanelRightOpen, RefreshCw, Settings2, Wrench } from "lucide-react";
import {
  API_BASE,
  getJson,
  postJson,
  type Approval,
  type Artifact,
  type ArtifactDetail,
  type AuditReport,
  type AuditSummary,
  type DiscussionHistory,
  type DiscussionSession,
  type Claim,
  type GapMap,
  type GapMapDetail,
  type GuideAdoptDirectionResponse,
  type GuideDiscussionMessage,
  type GuideDiscussDirectionResponse,
  type GuideStartResponse,
  type KnowledgeRecord,
  type KnowledgeSummary,
  type Lesson,
  type PaperCard,
  type PaperCardDetail,
  type ProjectAutopilotResponse,
  type Project,
  type ProjectDashboard,
  type ProviderHealthSnapshot,
  type ResultsFreeze,
  type RoutingInspection,
  type RunEvent,
  type RunManifest,
  type SpecFreeze,
  type Task,
  type TopicFreeze,
  type Verification,
  type VerificationSummary,
} from "./api";
import { CreateTab, type TopicFreezePrefill } from "./components/CreateTab";
import { DiscussTab } from "./components/DiscussTab";
import { OperationsTab } from "./components/OperationsTab";
import { OverviewTab } from "./components/OverviewTab";
import { RegistryTab } from "./components/RegistryTab";
import { Panel } from "./components/ui";
import { normalizeError } from "./utils";

type MainTab = "workspace" | "discuss" | "registry";
type SystemSection = "operations" | "advanced";
type AdvancedFocus = "project" | "topic_freeze" | null;

type DashboardData = {
  projects: Project[];
  selectedProject: Project | null;
  projectDashboard: ProjectDashboard | null;
  tasks: Task[];
  claims: Claim[];
  runs: RunManifest[];
  artifacts: Artifact[];
  lessons: Lesson[];
  knowledgeSummary: KnowledgeSummary;
  openQuestions: KnowledgeRecord[];
  verifications: Verification[];
  verificationSummary: VerificationSummary;
  approvals: Approval[];
  providers: ProviderHealthSnapshot[];
  routingSystem: RoutingInspection;
  paperCards: PaperCard[];
  gapMaps: GapMap[];
  topicFreeze: TopicFreeze | null;
  specFreeze: SpecFreeze | null;
  resultsFreeze: ResultsFreeze | null;
  auditSummary: AuditSummary;
  auditClaims: AuditReport;
  discussions: DiscussionSession[];
};

const tabs: Array<{ id: MainTab; label: string; icon: typeof FlaskConical }> = [
  { id: "workspace", label: "研究台", icon: FlaskConical },
  { id: "discuss", label: "Discuss", icon: Wrench },
  { id: "registry", label: "数据库", icon: Database },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<MainTab>("workspace");
  const [systemOpen, setSystemOpen] = useState(false);
  const [systemSection, setSystemSection] = useState<SystemSection>("operations");
  const [advancedFocus, setAdvancedFocus] = useState<AdvancedFocus>(null);
  const [topicFreezePrefill, setTopicFreezePrefill] = useState<TopicFreezePrefill | null>(null);
  const [selectedProjectId, setSelectedProjectId] = useState("");
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [artifactDetail, setArtifactDetail] = useState<ArtifactDetail | null>(null);
  const [paperCardDetail, setPaperCardDetail] = useState<PaperCardDetail | null>(null);
  const [gapMapDetail, setGapMapDetail] = useState<GapMapDetail | null>(null);
  const [routingPreview, setRoutingPreview] = useState<RoutingInspection | null>(null);
  const [selectedRunAudit, setSelectedRunAudit] = useState<AuditReport | null>(null);
  const [busyKeys, setBusyKeys] = useState<string[]>([]);
  const [activityLog, setActivityLog] = useState<string[]>([]);
  const refreshTimerRef = useRef<number | null>(null);

  useEffect(() => {
    void loadData();
  }, []);

  useEffect(() => {
    if (!selectedProjectId) {
      setActivityLog([]);
      return;
    }
    const stream = new EventSource(`${API_BASE}/projects/${encodeURIComponent(selectedProjectId)}/events/stream`);
    const scheduleRefresh = () => {
      if (refreshTimerRef.current !== null) {
        return;
      }
      refreshTimerRef.current = window.setTimeout(() => {
        refreshTimerRef.current = null;
        void loadData(false, selectedProjectId);
      }, 350);
    };
    stream.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data) as RunEvent;
        if (typeof payload.message === "string" && payload.message.trim()) {
          setActivityLog((current) => [...current.slice(-4), payload.message.trim()]);
        }
      } catch {
        if (typeof event.data === "string" && event.data.trim()) {
          setActivityLog((current) => [...current.slice(-4), event.data.trim()]);
        }
      }
      scheduleRefresh();
    };
    stream.onerror = scheduleRefresh;
    return () => {
      stream.close();
      if (refreshTimerRef.current !== null) {
        window.clearTimeout(refreshTimerRef.current);
        refreshTimerRef.current = null;
      }
    };
  }, [selectedProjectId]);

  async function loadData(showLoading = true, projectOverride?: string) {
    try {
      if (showLoading) {
        setLoading(true);
      }
      setError("");
      const projects = await getJson<Project[]>("/projects");
      const requestedProjectId = projectOverride ?? selectedProjectId;
      const nextProjectId =
        requestedProjectId && projects.some((project) => project.project_id === requestedProjectId)
          ? requestedProjectId
          : projects[0]?.project_id ?? "";

      if (nextProjectId !== selectedProjectId) {
        setSelectedProjectId(nextProjectId);
      }

      const [
        tasks,
        claims,
        runs,
        artifacts,
        lessons,
        knowledgeSummary,
        openQuestions,
        verifications,
        verificationSummary,
        approvals,
        providers,
        routingSystem,
        paperCards,
        gapMaps,
        topicFreeze,
        specFreeze,
        resultsFreeze,
        auditSummary,
        auditClaims,
        discussions,
        projectDashboard,
      ] = await Promise.all([
        getJson<Task[]>("/tasks"),
        getJson<Claim[]>("/claims"),
        getJson<RunManifest[]>("/runs"),
        getJson<Artifact[]>("/artifacts"),
        getJson<Lesson[]>("/lessons"),
        getJson<KnowledgeSummary>("/kb/summary"),
        getJson<KnowledgeRecord[]>("/kb/open_questions"),
        getJson<Verification[]>("/verifications"),
        getJson<VerificationSummary>("/verifications/summary"),
        getJson<Approval[]>("/approvals/pending"),
        getJson<ProviderHealthSnapshot[]>("/providers/health"),
        getJson<RoutingInspection>("/routing/system"),
        getJson<PaperCard[]>("/paper-cards"),
        getJson<GapMap[]>("/gap-maps"),
        getJson<TopicFreeze | null>("/freezes/topic"),
        getJson<SpecFreeze | null>("/freezes/spec"),
        getJson<ResultsFreeze | null>("/freezes/results"),
        getJson<AuditSummary>("/audit/summary"),
        getJson<AuditReport>("/audit/claims"),
        getJson<DiscussionSession[]>(nextProjectId ? `/discussions?project_id=${encodeURIComponent(nextProjectId)}` : "/discussions"),
        nextProjectId ? getJson<ProjectDashboard>(`/projects/${nextProjectId}/dashboard`) : Promise.resolve(null),
      ]);

      setData({
        projects,
        selectedProject: projects.find((project) => project.project_id === nextProjectId) ?? null,
        projectDashboard,
        tasks,
        claims,
        runs,
        artifacts,
        lessons,
        knowledgeSummary,
        openQuestions,
        verifications,
        verificationSummary,
        approvals,
        providers,
        routingSystem,
        paperCards,
        gapMaps,
        topicFreeze,
        specFreeze,
        resultsFreeze,
        auditSummary,
        auditClaims,
        discussions,
      });
    } catch (loadError) {
      setError(normalizeError(loadError));
    } finally {
      setLoading(false);
    }
  }

  async function runAction(key: string, callback: () => Promise<unknown>, refresh = true) {
    try {
      setBusyKeys((current) => [...current, key]);
      setError("");
      await callback();
      if (refresh) {
        await loadData(false);
      }
    } catch (actionError) {
      setError(normalizeError(actionError));
    } finally {
      setBusyKeys((current) => current.filter((item) => item !== key));
    }
  }

  function openSystem(section: SystemSection, focus: AdvancedFocus = null) {
    setSystemSection(section);
    setSystemOpen(true);
    setAdvancedFocus(focus);
  }

  function openHumanSelect(task: Task) {
    const topic =
      typeof task.input_payload.topic === "string" && task.input_payload.topic.trim()
        ? task.input_payload.topic.trim()
        : task.task_id;
    const rankedCandidates = Array.isArray(task.input_payload.ranked_candidates)
      ? task.input_payload.ranked_candidates
      : [];
    const selectedGapIds = rankedCandidates
      .map((item) => {
        if (!item || typeof item !== "object") {
          return "";
        }
        const gapId = (item as Record<string, unknown>).gap_id;
        return typeof gapId === "string" ? gapId : "";
      })
      .filter(Boolean);
    setTopicFreezePrefill({
      projectId: task.project_id,
      sourceTaskId: task.task_id,
      topicId: `${topic}-freeze`.toLowerCase().replace(/\s+/g, "-"),
      researchQuestion: `围绕 ${topic} 确认下一步研究问题。`,
      selectedGapIds,
      noveltyType: ["extension"],
    });
    setNotice(`已将人工决策任务 ${task.task_id} 载入高级表单。`);
    openSystem("advanced", "topic_freeze");
  }

  function openTopicFreeze() {
    openSystem("advanced", "topic_freeze");
  }

  function openProject(projectId: string, tab: MainTab = "workspace") {
    setSelectedProjectId(projectId);
    setActiveTab(tab);
    setArtifactDetail(null);
    setPaperCardDetail(null);
    setGapMapDetail(null);
    setRoutingPreview(null);
    void loadData(false, projectId);
  }

  async function startResearchFlow(payload: { researchGoal: string; projectName: string }) {
    await runAction(
      "guide-start",
      async () => {
        const response = await postJson<GuideStartResponse>("/guide/start", {
          research_goal: payload.researchGoal,
          project_name: payload.projectName,
        });
        setSelectedProjectId(response.project_id);
        setActiveTab("workspace");
        setArtifactDetail(null);
        setPaperCardDetail(null);
        setGapMapDetail(null);
        setNotice(response.next_step);
        await loadData(false, response.project_id);
      },
      false,
    );
  }

  async function continueProjectAutopilot() {
    if (!selectedProjectId) {
      setError("请先选择一个项目。");
      return;
    }
    await runAction(
      "guide-autopilot",
      async () => {
        const response = await postJson<ProjectAutopilotResponse>(`/projects/${selectedProjectId}/autopilot`);
        setNotice(autopilotNotice(response.autopilot.stop_reason));
        await loadData(false, selectedProjectId);
      },
      false,
    );
  }

  async function adoptGuidedDirection(payload: {
    humanSelectTaskId: string;
    gapId: string;
    researchQuestion: string;
    operatorNote: string;
  }) {
    if (!selectedProjectId) {
      setError("请先选择一个项目。");
      return;
    }
    await runAction(
      `adopt-${payload.gapId}`,
      async () => {
        const response = await postJson<GuideAdoptDirectionResponse>("/guide/adopt-direction", {
          project_id: selectedProjectId,
          human_select_task_id: payload.humanSelectTaskId,
          gap_id: payload.gapId,
          research_question: payload.researchQuestion,
          operator_note: payload.operatorNote,
        });
        setNotice(response.next_step);
        await loadData(false, selectedProjectId);
      },
      false,
    );
  }

  const projectTasks = data?.tasks.filter((task) => !selectedProjectId || task.project_id === selectedProjectId) ?? [];
  const projectRuns =
    data?.runs.filter((run) => projectTasks.some((task) => `run-${task.task_id}` === run.run_id || task.task_id === run.run_id)) ?? [];
  const projectArtifacts =
    data?.artifacts.filter((artifact) => projectRuns.some((run) => run.run_id === artifact.run_id)) ?? [];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-card">
          <div className="brand-icon">
            <FlaskConical size={20} />
          </div>
          <div>
            <span>ResearchOS</span>
            <strong>Studio Workspace</strong>
          </div>
        </div>

        <div className="sidebar-section">
          <label htmlFor="project-picker">当前项目</label>
          <select
            id="project-picker"
            value={selectedProjectId}
            onChange={(event) => {
              setSelectedProjectId(event.target.value);
              setArtifactDetail(null);
              setPaperCardDetail(null);
              setGapMapDetail(null);
              setRoutingPreview(null);
              void loadData(false, event.target.value);
            }}
          >
            {data?.projects.length ? (
              data.projects.map((project) => (
                <option key={project.project_id} value={project.project_id}>
                  {project.name} · {project.project_id}
                </option>
              ))
            ) : (
              <option value="">暂无项目</option>
            )}
          </select>
        </div>

        <nav className="nav-stack">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button key={tab.id} className={activeTab === tab.id ? "nav-button active" : "nav-button"} onClick={() => setActiveTab(tab.id)}>
                <Icon size={16} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

        <div className="sidebar-actions">
          <button className="button secondary" type="button" onClick={() => openSystem("advanced", "project")}>
            <Wrench size={14} />
            新建 / 高级操作
          </button>
          <button className="button secondary" type="button" onClick={() => openSystem("operations")}>
            <Settings2 size={14} />
            系统面板
          </button>
        </div>

        <Panel title="API" subtitle="前端代理目标">
          <div className="mono-block">{API_BASE}</div>
          <button className="button secondary" onClick={() => void loadData()}>
            <RefreshCw size={14} />
            全部刷新
          </button>
        </Panel>
      </aside>

      <main className="main-column">
        <header className="topbar">
          <div>
            <p className="eyebrow">Research Workspace</p>
            <h1>{data?.selectedProject?.name ?? "尚未选择项目"}</h1>
            <div className="topbar-meta">
              {data?.selectedProject ? <span className="next-tag">当前阶段：{stageLabel(data.selectedProject.stage)}</span> : null}
              {data?.projectDashboard?.recommended_next_task_kind ? (
                <span className="next-tag">下一步：{data.projectDashboard.recommended_next_task_kind}</span>
              ) : null}
            </div>
          </div>
          <div className="topbar-actions">
            <button className="button secondary" onClick={() => setSystemOpen((current) => !current)}>
              {systemOpen ? <PanelRightClose size={14} /> : <PanelRightOpen size={14} />}
              {systemOpen ? "收起系统" : "打开系统"}
            </button>
            <button className="button secondary" onClick={() => void loadData()} disabled={loading}>
              <RefreshCw size={14} className={loading ? "spin" : ""} />
              刷新
            </button>
          </div>
        </header>

        {notice ? <div className="notice-banner">{notice}</div> : null}
        {error ? <div className="error-banner">{error}</div> : null}
        {loading && !data ? <div className="loading-panel">正在加载 ResearchOS…</div> : null}
        {busyKeys.length > 0 ? <div className="pixel-loading-bar">操作处理中，请稍候...</div> : null}

        {data ? (
          <div className={systemOpen ? "workspace-layout system-open" : "workspace-layout"}>
            <div className="workspace-main">
              {activeTab === "workspace" ? (
                <OverviewTab
                  projects={data.projects}
                  selectedProject={data.selectedProject}
                  allTasks={data.tasks}
                  projectTasks={projectTasks}
                  projectDashboard={data.projectDashboard}
                  providers={data.providers}
                  routingSystem={data.routingSystem}
                  approvals={data.approvals}
                  paperCards={data.paperCards}
                  gapMaps={data.gapMaps}
                  openQuestions={data.openQuestions}
                  topicFreeze={data.topicFreeze}
                  specFreeze={data.specFreeze}
                  activityLog={activityLog}
                  startResearch={startResearchFlow}
                  continueAutopilot={continueProjectAutopilot}
                  adoptDirection={adoptGuidedDirection}
                  loadGapMap={(topic) => getJson(`/gap-maps/${encodeURIComponent(topic)}`)}
                  discussDirection={(payload) =>
                    postJson<GuideDiscussDirectionResponse>("/guide/discuss-direction", {
                      project_id: selectedProjectId,
                      human_select_task_id: payload.humanSelectTaskId,
                      gap_id: payload.gapId,
                      user_message: payload.userMessage,
                      history: payload.history as GuideDiscussionMessage[],
                    })
                  }
                  loadDiscussionHistory={(humanSelectTaskId, gapId) =>
                    getJson<DiscussionHistory>(
                      `/projects/${encodeURIComponent(selectedProjectId)}/guide/discussions/${encodeURIComponent(humanSelectTaskId)}/${encodeURIComponent(gapId)}`,
                    )
                  }
                  openProject={openProject}
                  openSystem={openSystem}
                  isBusy={(key) => busyKeys.includes(key)}
                />
              ) : null}

              {activeTab === "discuss" ? (
                <DiscussTab
                  selectedProject={data.selectedProject}
                  projectTasks={projectTasks}
                  projectRuns={projectRuns}
                  claims={data.claims}
                  paperCards={data.paperCards}
                  topicFreeze={data.topicFreeze}
                  specFreeze={data.specFreeze}
                  resultsFreeze={data.resultsFreeze}
                  discussions={data.discussions}
                  runAction={runAction}
                  isBusy={(key) => busyKeys.includes(key)}
                  createDiscussion={(payload) => postJson<DiscussionSession>("/discussions", payload)}
                  importDiscussion={(sessionId, payload) => postJson<DiscussionSession>(`/discussions/${sessionId}/import`, payload)}
                  adoptDiscussion={(sessionId, payload) => postJson<DiscussionSession>(`/discussions/${sessionId}/adopt`, payload)}
                  promoteDiscussionKb={(sessionId) => postJson(`/discussions/${sessionId}/promote/kb`)}
                  promoteDiscussionApproval={(sessionId, payload) => postJson(`/discussions/${sessionId}/promote/approval`, payload)}
                  promoteDiscussionTask={(sessionId, payload) => postJson(`/discussions/${sessionId}/promote/task`, payload)}
                />
              ) : null}

              {activeTab === "registry" ? (
                <RegistryTab
                  projectTasks={projectTasks}
                  projectArtifacts={projectArtifacts}
                  artifactDetail={artifactDetail}
                  paperCardDetail={paperCardDetail}
                  gapMapDetail={gapMapDetail}
                  verificationSummary={data.verificationSummary}
                  auditSummary={data.auditSummary}
                  paperCards={data.paperCards}
                  gapMaps={data.gapMaps}
                  lessons={data.lessons}
                  knowledgeSummary={data.knowledgeSummary}
                  topicFreeze={data.topicFreeze}
                  specFreeze={data.specFreeze}
                  resultsFreeze={data.resultsFreeze}
                  runAction={runAction}
                  loadArtifact={(artifactId) => getJson(`/artifacts/${artifactId}`)}
                  loadPaperCard={(paperId) => getJson(`/paper-cards/${encodeURIComponent(paperId)}`)}
                  loadGapMap={(topic) => getJson(`/gap-maps/${encodeURIComponent(topic)}`)}
                  setArtifactDetail={setArtifactDetail}
                  setPaperCardDetail={setPaperCardDetail}
                  setGapMapDetail={setGapMapDetail}
                  openHumanSelect={openHumanSelect}
                  openTopicFreeze={openTopicFreeze}
                />
              ) : null}
            </div>

            {systemOpen ? (
              <aside className="system-drawer">
                <div className="system-drawer-head">
                  <div>
                    <span className="eyebrow">System</span>
                    <h2>系统面板</h2>
                  </div>
                  <button className="button secondary" type="button" onClick={() => setSystemOpen(false)}>
                    <PanelRightClose size={14} />
                    收起
                  </button>
                </div>

                <div className="system-switcher">
                  <button
                    className={systemSection === "operations" ? "system-switch active" : "system-switch"}
                    type="button"
                    onClick={() => setSystemSection("operations")}
                  >
                    调度与 Provider
                  </button>
                  <button
                    className={systemSection === "advanced" ? "system-switch active" : "system-switch"}
                    type="button"
                    onClick={() => setSystemSection("advanced")}
                  >
                    高级表单
                  </button>
                </div>

                <div className="system-drawer-body">
                  {systemSection === "operations" ? (
                    <OperationsTab
                      projectTasks={projectTasks}
                      projectRuns={projectRuns}
                      claims={data.claims}
                      approvals={data.approvals}
                      providers={data.providers}
                      routingPreview={routingPreview}
                      selectedRunAudit={selectedRunAudit}
                      runAction={runAction}
                      isBusy={(key) => busyKeys.includes(key)}
                      setRoutingPreview={setRoutingPreview}
                      setSelectedRunAudit={setSelectedRunAudit}
                      loadTaskRouting={(taskId) => getJson(`/routing/tasks/${taskId}`)}
                      loadRunAudit={(runId) => getJson(`/audit/runs/${runId}`)}
                      dispatchTask={(taskId) => postJson(`/tasks/${taskId}/dispatch`)}
                      retryTask={(taskId) => postJson(`/tasks/${taskId}/retry`)}
                      cancelTask={(taskId) => postJson(`/tasks/${taskId}/cancel`)}
                      disableProvider={(provider) => postJson(`/providers/${provider}/disable`)}
                      enableProvider={(provider) => postJson(`/providers/${provider}/enable`)}
                      clearCooldown={(provider) => postJson(`/providers/${provider}/clear-cooldown`)}
                      probeProvider={(provider) => postJson(`/providers/${provider}/probe`)}
                      verifyClaim={(claimId) => postJson(`/verifications/claims/${claimId}`)}
                      verifyRun={(runId) => postJson(`/verifications/runs/${runId}`)}
                      createApproval={(payload) => postJson("/approvals", payload)}
                      openHumanSelect={openHumanSelect}
                    />
                  ) : (
                    <CreateTab
                      selectedProjectId={selectedProjectId}
                      selectedProjectName={data.selectedProject?.name ?? ""}
                      focusSection={advancedFocus}
                      topicFreezePrefill={topicFreezePrefill}
                      runAction={runAction}
                      createProject={(payload) => postJson("/projects", payload)}
                      createTask={(payload) => postJson("/tasks", payload)}
                      createClaim={(payload) => postJson("/claims", payload)}
                      createRun={(payload) => postJson("/runs", payload)}
                      createPaperCard={(payload) => postJson("/paper-cards", payload)}
                      createGapMap={(payload) => postJson("/gap-maps", payload)}
                      createLesson={(payload) => postJson("/lessons", payload)}
                      createApproval={(payload) => postJson("/approvals", payload)}
                      saveTopicFreeze={(payload) => postJson("/freezes/topic", payload)}
                      saveSpecFreeze={(payload) => postJson("/freezes/spec", payload)}
                      saveResultsFreeze={(payload) => postJson("/freezes/results", payload)}
                      setNotice={setNotice}
                    />
                  )}
                </div>
              </aside>
            ) : null}
          </div>
        ) : null}
      </main>
    </div>
  );
}

function stageLabel(stage: string) {
  const labels: Record<string, string> = {
    NEW_TOPIC: "新主题",
    INGEST_PAPERS: "论文摄入",
    BUILD_PAPER_CARDS: "构建卡片",
    MAP_GAPS: "Gap 分析",
    HUMAN_SELECT: "人工选题",
    FREEZE_TOPIC: "冻结方向",
    FREEZE_SPEC: "冻结规格",
    REPRO_BASELINES: "复现实验",
    IMPLEMENT_IDEA: "实现方案",
    RUN_EXPERIMENTS: "运行实验",
    AUDIT_RESULTS: "审计结果",
    FREEZE_RESULTS: "冻结结果",
    WRITE_DRAFT: "撰写草稿",
    REVIEW_DRAFT: "审阅草稿",
    STYLE_PASS: "样式整理",
    SUBMISSION_READY: "准备提交",
  };
  return labels[stage] ?? stage;
}

function autopilotNotice(stopReason: string) {
  switch (stopReason) {
    case "human_select_ready":
      return "AI 已经整理出候选方向，请在研究台选一个方向继续。";
    case "blocked":
      return "自动流程被阻塞了，请打开系统面板处理失败或阻塞任务。";
    case "waiting_approval":
      return "自动流程进入待审批状态，需要人工确认。";
    case "failed":
      return "自动流程失败了，请到系统面板查看失败任务。";
    case "running":
      return "当前还有任务在运行，稍后刷新即可。";
    case "idle":
      return "当前没有可继续自动推进的任务。";
    case "dispatch_limit_reached":
      return "本轮已自动推进一批任务，可以继续点击一次。";
    default:
      return "自动流程已经完成这一轮推进。";
  }
}
