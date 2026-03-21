import { useEffect, useState } from "react";
import { Blocks, RefreshCw, Sparkles, TerminalSquare } from "lucide-react";
import {
  API_BASE,
  getJson,
  postJson,
  type Approval,
  type Artifact,
  type ArtifactDetail,
  type AuditReport,
  type AuditSummary,
  type Claim,
  type GapMap,
  type GapMapDetail,
  type GuideAdoptDirectionResponse,
  type GuideDiscussionMessage,
  type GuideDiscussDirectionResponse,
  type GuideStartResponse,
  type Lesson,
  type PaperCard,
  type PaperCardDetail,
  type ProjectAutopilotResponse,
  type Project,
  type ProjectDashboard,
  type ProviderHealthSnapshot,
  type ResultsFreeze,
  type RoutingInspection,
  type RunManifest,
  type SpecFreeze,
  type Task,
  type TopicFreeze,
  type Verification,
  type VerificationSummary,
} from "./api";
import { CreateTab } from "./components/CreateTab";
import { OperationsTab } from "./components/OperationsTab";
import { OverviewTab } from "./components/OverviewTab";
import { RegistryTab } from "./components/RegistryTab";
import { Panel, StatCard } from "./components/ui";
import { normalizeError } from "./utils";

type TabKey = "overview" | "operations" | "registry" | "create";

type DashboardData = {
  projects: Project[];
  selectedProject: Project | null;
  projectDashboard: ProjectDashboard | null;
  tasks: Task[];
  claims: Claim[];
  runs: RunManifest[];
  artifacts: Artifact[];
  lessons: Lesson[];
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
};

const tabs: Array<{ id: TabKey; label: string; icon: typeof Sparkles }> = [
  { id: "overview", label: "总览", icon: Sparkles },
  { id: "operations", label: "控制", icon: TerminalSquare },
  { id: "registry", label: "登记", icon: Blocks },
  { id: "create", label: "创建", icon: Blocks },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [createFocus, setCreateFocus] = useState<"topic_freeze" | null>(null);
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

  const [projectForm, setProjectForm] = useState({
    project_id: "",
    name: "",
    description: "",
    status: "active",
    dispatch_profile_json: "",
  });
  const [taskForm, setTaskForm] = useState({
    task_id: "",
    project_id: "",
    kind: "paper_ingest",
    goal: "",
    owner: "operator",
    assigned_agent: "",
    parent_task_id: "",
    input_payload_json: '{\n  "topic": ""\n}',
    dispatch_profile_json: "",
  });
  const [claimForm, setClaimForm] = useState({
    claim_id: "",
    text: "",
    claim_type: "result",
    risk_level: "medium",
    approved_by_human: false,
  });
  const [runForm, setRunForm] = useState({
    run_id: "",
    spec_id: "",
    git_commit: "HEAD",
    config_hash: "",
    dataset_snapshot: "",
    seed: "42",
    gpu: "cpu",
  });
  const [paperCardForm, setPaperCardForm] = useState({
    paper_id: "",
    title: "",
    problem: "",
    setting: "",
    task_type: "",
    strongest_result: "",
    method_summary: "",
    evidence_refs: "manual:1",
  });
  const [gapMapForm, setGapMapForm] = useState({
    topic: "",
    cluster_name: "",
    gap_id: "",
    description: "",
    supporting_papers: "",
    attack_surface: "",
    difficulty: "",
    novelty_type: "",
  });
  const [lessonForm, setLessonForm] = useState({
    lesson_id: "",
    lesson_kind: "lesson",
    title: "",
    summary: "",
    rationale: "",
    recommended_action: "",
    task_kind: "",
    agent_name: "",
    provider_name: "",
    model_name: "",
    context_tags: "",
    evidence_refs: "",
    artifact_ids: "",
    source_task_id: "",
    source_run_id: "",
    source_claim_id: "",
  });
  const [approvalForm, setApprovalForm] = useState({
    approval_id: "",
    project_id: "",
    target_type: "results_freeze",
    target_id: "",
    approved_by: "operator",
    decision: "approved",
    comment: "",
  });
  const [topicFreezeForm, setTopicFreezeForm] = useState({
    topic_id: "",
    research_question: "",
    selected_gap_ids: "",
    novelty_type: "",
    owner: "operator",
    status: "approved",
  });
  const [specFreezeForm, setSpecFreezeForm] = useState({
    spec_id: "",
    topic_id: "",
    hypothesis: "",
    must_beat_baselines: "",
    datasets: "",
    metrics: "",
    fairness_constraints: "",
    ablations: "",
    success_criteria: "",
    failure_criteria: "",
    approved_by: "operator",
    status: "approved",
  });
  const [resultsFreezeForm, setResultsFreezeForm] = useState({
    results_id: "",
    spec_id: "",
    main_claims: "",
    tables: "",
    figures: "",
    approved_by: "operator",
    status: "approved",
  });

  useEffect(() => {
    void loadData();
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void loadData(false);
    }, 15000);
    return () => window.clearInterval(timer);
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
        projectDashboard,
      ] = await Promise.all([
        getJson<Task[]>("/tasks"),
        getJson<Claim[]>("/claims"),
        getJson<RunManifest[]>("/runs"),
        getJson<Artifact[]>("/artifacts"),
        getJson<Lesson[]>("/lessons"),
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
      .filter(Boolean)
      .slice(0, 1)
      .join("\n");

    setTopicFreezeForm((current) => ({
      ...current,
      topic_id: current.topic_id || `${topic}-freeze`.toLowerCase().replace(/\s+/g, "-"),
      research_question: current.research_question || `围绕 ${topic} 确认下一步研究问题。`,
      selected_gap_ids: current.selected_gap_ids || selectedGapIds,
      novelty_type: current.novelty_type || "extension",
      owner: current.owner || "operator",
      status: current.status || "approved",
    }));
    setNotice(`已载入人工决策任务 ${task.task_id}，请在“创建”页完成主题冻结。`);
    setCreateFocus("topic_freeze");
    setActiveTab("create");
  }

  function openTopicFreeze() {
    setCreateFocus("topic_freeze");
    setActiveTab("create");
  }

  async function startResearchFlow(payload: { researchGoal: string; projectName: string }) {
    await runAction("guide-start", async () => {
      const response = await postJson<GuideStartResponse>("/guide/start", {
        research_goal: payload.researchGoal,
        project_name: payload.projectName,
      });
      setSelectedProjectId(response.project_id);
      setArtifactDetail(null);
      setPaperCardDetail(null);
      setGapMapDetail(null);
      setActiveTab("overview");
      setNotice(response.next_step);
      await loadData(false, response.project_id);
    }, false);
  }

  async function continueProjectAutopilot() {
    if (!selectedProjectId) {
      setError("请先选择一个项目。");
      return;
    }
    await runAction("guide-autopilot", async () => {
      const response = await postJson<ProjectAutopilotResponse>(`/projects/${selectedProjectId}/autopilot`);
      setNotice(autopilotNotice(response.autopilot.stop_reason));
      await loadData(false, selectedProjectId);
    }, false);
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
    await runAction(`adopt-${payload.gapId}`, async () => {
      const response = await postJson<GuideAdoptDirectionResponse>("/guide/adopt-direction", {
        project_id: selectedProjectId,
        human_select_task_id: payload.humanSelectTaskId,
        gap_id: payload.gapId,
        research_question: payload.researchQuestion,
        operator_note: payload.operatorNote,
      });
      setNotice(response.next_step);
      await loadData(false, selectedProjectId);
    }, false);
  }

  const projectTasks = data?.tasks.filter((task) => !selectedProjectId || task.project_id === selectedProjectId) ?? [];
  const projectRuns = data?.runs.filter((run) => projectTasks.some((task) => `run-${task.task_id}` === run.run_id)) ?? [];
  const projectArtifacts = data?.artifacts.filter((artifact) => projectRuns.some((run) => run.run_id === artifact.run_id)) ?? [];

  const stats = data
    ? [
        { label: "项目", value: data.projects.length, meta: `当前视图有 ${projectTasks.length} 个任务` },
        { label: "产物", value: data.artifacts.length, meta: `当前项目关联 ${projectArtifacts.length} 个产物记录` },
        { label: "验证", value: data.verificationSummary.total_checks, meta: `已载入 ${data.verifications.length} 条记录` },
        { label: "审批", value: data.approvals.length, meta: "等待人工处理" },
      ]
    : [];

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-card">
          <div className="brand-icon">
            <TerminalSquare size={20} />
          </div>
          <div>
            <span>ResearchOS</span>
            <strong>研究控制台</strong>
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
                  {project.project_id} - {project.name}
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
              <button
                key={tab.id}
                className={activeTab === tab.id ? "nav-button active" : "nav-button"}
                onClick={() => {
                  if (tab.id !== "create") {
                    setCreateFocus(null);
                  }
                  setActiveTab(tab.id);
                }}
              >
                <Icon size={16} />
                <span>{tab.label}</span>
              </button>
            );
          })}
        </nav>

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
            <p className="eyebrow">研究运行台</p>
            <h1>{data?.selectedProject?.name ?? "尚未选择项目"}</h1>
            <div className="topbar-meta">
              {data?.projectDashboard?.recommended_next_task_kind ? (
                <span className="next-tag">下一步: {data.projectDashboard.recommended_next_task_kind}</span>
              ) : null}
            </div>
          </div>
          <div className="topbar-actions">
            <button className="button secondary" onClick={() => void loadData()} disabled={loading}>
              <RefreshCw size={14} className={loading ? "spin" : ""} />
              刷新
            </button>
          </div>
        </header>

        {notice ? <div className="notice-banner">{notice}</div> : null}
        {error ? <div className="error-banner">{error}</div> : null}
        {loading && !data ? <div className="loading-panel">正在加载 ResearchOS 控制台...</div> : null}

        {data ? (
          <>
            <section className="stats-grid">
              {stats.map((item) => (
                <StatCard key={item.label} label={item.label} value={item.value} meta={item.meta} />
              ))}
            </section>

            {activeTab === "overview" ? (
              <OverviewTab
                selectedProject={data.selectedProject}
                projectTasks={projectTasks}
                projectDashboard={data.projectDashboard}
                providers={data.providers}
                routingSystem={data.routingSystem}
                approvals={data.approvals}
                paperCards={data.paperCards}
                gapMaps={data.gapMaps}
                topicFreeze={data.topicFreeze}
                specFreeze={data.specFreeze}
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
                isBusy={(key) => busyKeys.includes(key)}
              />
            ) : null}

            {activeTab === "operations" ? (
              <OperationsTab
                projectTasks={projectTasks}
                projectRuns={projectRuns}
                claims={data.claims}
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
                openHumanSelect={openHumanSelect}
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

            {activeTab === "create" ? (
              <CreateTab
                projectForm={projectForm}
                setProjectForm={setProjectForm}
                taskForm={taskForm}
                setTaskForm={setTaskForm}
                claimForm={claimForm}
                setClaimForm={setClaimForm}
                runForm={runForm}
                setRunForm={setRunForm}
                paperCardForm={paperCardForm}
                setPaperCardForm={setPaperCardForm}
                gapMapForm={gapMapForm}
                setGapMapForm={setGapMapForm}
                lessonForm={lessonForm}
                setLessonForm={setLessonForm}
                approvalForm={approvalForm}
                setApprovalForm={setApprovalForm}
                topicFreezeForm={topicFreezeForm}
                setTopicFreezeForm={setTopicFreezeForm}
                specFreezeForm={specFreezeForm}
                setSpecFreezeForm={setSpecFreezeForm}
                resultsFreezeForm={resultsFreezeForm}
                setResultsFreezeForm={setResultsFreezeForm}
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
                focusSection={createFocus}
              />
            ) : null}
          </>
        ) : null}
      </main>
    </div>
  );
}

function autopilotNotice(stopReason: string) {
  switch (stopReason) {
    case "human_select_ready":
      return "AI 已整理出候选 idea，请在总览页选择一个方向继续。";
    case "blocked":
      return "自动流程被阻塞了，请去控制页检查失败原因。";
    case "waiting_approval":
      return "自动流程进入待审批状态，需要人工确认。";
    case "failed":
      return "自动流程失败了，请去控制页查看失败任务。";
    case "running":
      return "当前还有任务在运行，稍后刷新即可。";
    case "idle":
      return "当前没有可继续自动推进的任务。";
    case "dispatch_limit_reached":
      return "本轮已自动推进一批任务，可以再次点击继续。";
    default:
      return "自动流程已完成这一轮推进。";
  }
}
