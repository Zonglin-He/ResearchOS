import { useEffect, useMemo, useRef, useState } from "react";
import type {
  DiscussionHistory,
  GapMap,
  GapMapDetail,
  GuideDiscussDirectionResponse,
  GuideDiscussionMessage,
  PaperCard,
  Project,
  ProjectDashboard,
  ProviderHealthSnapshot,
  RoutingInspection,
  SpecFreeze,
  Task,
  TopicFreeze,
} from "../api";
import { PixelStudio } from "./PixelStudio";
import { EmptyState, KeyValue, Panel, StatCard, StatusPill } from "./ui";

type WorkbenchTab = "overview" | "operations" | "registry" | "create";

type Props = {
  projects: Project[];
  selectedProject: Project | null;
  allTasks: Task[];
  projectTasks: Task[];
  projectDashboard: ProjectDashboard | null;
  providers: ProviderHealthSnapshot[];
  routingSystem: RoutingInspection;
  approvals: Array<{
    approval_id: string;
    target_type: string;
    target_id: string;
    decision: string;
    approved_by: string;
  }>;
  paperCards: PaperCard[];
  gapMaps: GapMap[];
  topicFreeze: TopicFreeze | null;
  specFreeze: SpecFreeze | null;
  startResearch: (payload: { researchGoal: string; projectName: string }) => Promise<void>;
  continueAutopilot: () => Promise<void>;
  adoptDirection: (payload: {
    humanSelectTaskId: string;
    gapId: string;
    researchQuestion: string;
    operatorNote: string;
  }) => Promise<void>;
  loadGapMap: (topic: string) => Promise<GapMapDetail>;
  discussDirection: (payload: {
    humanSelectTaskId: string;
    gapId: string;
    userMessage: string;
    history: GuideDiscussionMessage[];
  }) => Promise<GuideDiscussDirectionResponse>;
  loadDiscussionHistory: (humanSelectTaskId: string, gapId: string) => Promise<DiscussionHistory>;
  openProject: (projectId: string, tab?: WorkbenchTab) => void;
  isBusy: (key: string) => boolean;
};

type RankedCandidate = {
  gap_id: string;
  score: number | null;
  rationale: string;
  feasibility: string;
  novelty_score: number;
  evidence_summary: string;
};

type GapSummary = {
  description: string;
  evidenceSummary: string;
  difficulty: string;
  noveltyType: string;
  feasibility: string;
  noveltyScore: number;
  attackSurface: string;
  supportingPapers: string[];
};

type SessionSummary = {
  projectId: string;
  name: string;
  ingestCount: number;
  gapCount: number;
  currentLabel: string;
  helperText: string;
  actionLabel: string;
  actionTab: WorkbenchTab;
  waitingHuman: boolean;
};

export function OverviewTab(props: Props) {
  const [researchGoal, setResearchGoal] = useState("");
  const [projectName, setProjectName] = useState("");
  const [selectedGapId, setSelectedGapId] = useState("");
  const [chatDraft, setChatDraft] = useState("");
  const [gapMapDetail, setGapMapDetail] = useState<GapMapDetail | null>(null);
  const [discussionByGap, setDiscussionByGap] = useState<Record<string, GuideDiscussDirectionResponse>>({});
  const [threadsByGap, setThreadsByGap] = useState<Record<string, GuideDiscussionMessage[]>>({});
  const [researchQuestionByGap, setResearchQuestionByGap] = useState<Record<string, string>>({});
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  const humanSelectTask = useMemo(
    () =>
      props.projectTasks.find(
        (task) => task.kind === "human_select" && task.status !== "cancelled" && task.status !== "succeeded",
      ) ?? null,
    [props.projectTasks],
  );

  const rankedCandidates = useMemo(() => {
    if (!humanSelectTask) return [] as RankedCandidate[];
    const raw = humanSelectTask.input_payload.ranked_candidates;
    if (!Array.isArray(raw)) return [] as RankedCandidate[];
    return raw
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
      .map((item) => ({
        gap_id: typeof item.gap_id === "string" ? item.gap_id : "",
        score: typeof item.score === "number" ? item.score : null,
        rationale: typeof item.rationale === "string" ? item.rationale : "",
        feasibility: typeof item.feasibility === "string" ? item.feasibility : "",
        novelty_score: typeof item.novelty_score === "number" ? item.novelty_score : 0,
        evidence_summary: typeof item.evidence_summary === "string" ? item.evidence_summary : "",
      }))
      .filter((item) => item.gap_id);
  }, [humanSelectTask]);

  const topic = typeof humanSelectTask?.input_payload.topic === "string" ? humanSelectTask.input_payload.topic : "";

  useEffect(() => {
    if (!props.selectedProject || researchGoal) return;
    setResearchGoal(props.selectedProject.description || props.selectedProject.name);
    setProjectName(props.selectedProject.name);
  }, [props.selectedProject, researchGoal]);

  useEffect(() => {
    if (!topic) {
      setGapMapDetail(null);
      return;
    }
    void props.loadGapMap(topic).then(setGapMapDetail).catch(() => setGapMapDetail(null));
  }, [props, topic]);

  useEffect(() => {
    if (!rankedCandidates.length) {
      setSelectedGapId("");
      setChatDraft("");
      return;
    }
    setSelectedGapId((current) =>
      rankedCandidates.some((candidate) => candidate.gap_id === current) ? current : rankedCandidates[0].gap_id,
    );
  }, [rankedCandidates]);

  const gapLookup = useMemo(() => {
    const map = new Map<string, GapSummary>();
    if (!gapMapDetail) return map;
    gapMapDetail.clusters.forEach((cluster) => {
      cluster.gaps.forEach((gap) => {
        map.set(gap.gap_id, {
          description: gap.description,
          evidenceSummary: gap.evidence_summary,
          difficulty: gap.difficulty,
          noveltyType: gap.novelty_type,
          feasibility: gap.feasibility,
          noveltyScore: gap.novelty_score,
          attackSurface: gap.attack_surface,
          supportingPapers: gap.supporting_papers,
        });
      });
    });
    return map;
  }, [gapMapDetail]);

  const paperTitleById = useMemo(
    () => new Map(props.paperCards.map((paper) => [paper.paper_id, paper.title])),
    [props.paperCards],
  );

  const selectedGap = selectedGapId ? gapLookup.get(selectedGapId) ?? null : null;
  const currentDiscussion = selectedGapId ? discussionByGap[selectedGapId] ?? null : null;
  const currentThread = selectedGapId ? threadsByGap[selectedGapId] ?? [] : [];
  const suggestedResearchQuestion = currentDiscussion?.research_question_suggestion ?? "";
  const researchQuestion = selectedGapId ? researchQuestionByGap[selectedGapId] ?? suggestedResearchQuestion : "";

  const sessionSummaries = useMemo(() => {
    return props.projects.map((project) => {
      const tasks = props.allTasks.filter((task) => task.project_id === project.project_id);
      const ingestCount = tasks.filter((task) => task.kind === "paper_ingest" && task.status === "succeeded").length;
      const gapCount = tasks.filter((task) => task.kind === "gap_mapping" && task.status === "succeeded").length;
      const pendingHuman = tasks.find(
        (task) => task.kind === "human_select" && task.status !== "cancelled" && task.status !== "succeeded",
      );
      const running = tasks.find((task) => task.status === "running");
      const blocked = tasks.find((task) => ["blocked", "failed", "waiting_approval"].includes(task.status));
      const queued = tasks.find((task) => task.status === "queued");
      if (pendingHuman) {
        return buildSession(project, ingestCount, gapCount, "等待你选方向", "文献和 gap 已经聚合完成，进入候选方向判断。", "继续", "overview", true);
      }
      if (running) {
        return buildSession(project, ingestCount, gapCount, `${running.kind} 运行中`, running.goal, "查看运行", "operations", false);
      }
      if (blocked) {
        return buildSession(project, ingestCount, gapCount, `${blocked.kind} 需要处理`, blocked.last_error || blocked.goal, "处理", blocked.kind === "human_select" ? "overview" : "operations", blocked.kind === "human_select");
      }
      if (queued) {
        return buildSession(project, ingestCount, gapCount, `${queued.kind} 待调度`, queued.goal, "去控制台", "operations", false);
      }
      return buildSession(project, ingestCount, gapCount, "查看工作台", project.description || "继续查看当前项目的研究状态。", "打开", "overview", false);
    });
  }, [props.allTasks, props.projects]);

  useEffect(() => {
    if (!selectedGapId || !humanSelectTask || threadsByGap[selectedGapId]?.length) return;
    let cancelled = false;
    const humanSelectTaskId = humanSelectTask.task_id;
    async function hydrate() {
      try {
        const history = await props.loadDiscussionHistory(humanSelectTaskId, selectedGapId);
        if (cancelled) return;
        if (history.messages.length) {
          setThreadsByGap((current) => ({ ...current, [selectedGapId]: history.messages }));
          const restored = discussionFromHistory(history, selectedGapId);
          if (restored) {
            setDiscussionByGap((current) => ({ ...current, [selectedGapId]: restored }));
            setResearchQuestionByGap((current) => ({
              ...current,
              [selectedGapId]: current[selectedGapId] || restored.research_question_suggestion,
            }));
          }
          return;
        }
        const response = await props.discussDirection({
          humanSelectTaskId,
          gapId: selectedGapId,
          userMessage: "",
          history: [],
        });
        if (cancelled) return;
        setDiscussionByGap((current) => ({ ...current, [selectedGapId]: response }));
        setThreadsByGap((current) => ({
          ...current,
          [selectedGapId]: [{ role: "assistant", content: response.assistant_message, metadata: discussionMetadata(response) }],
        }));
        setResearchQuestionByGap((current) => ({
          ...current,
          [selectedGapId]: current[selectedGapId] || response.research_question_suggestion,
        }));
      } catch {
        if (cancelled) return;
        setThreadsByGap((current) => ({
          ...current,
          [selectedGapId]: [{ role: "assistant", content: "当前无法连接选题顾问，请稍后再试。" }],
        }));
      }
    }
    void hydrate();
    return () => {
      cancelled = true;
    };
  }, [humanSelectTask, props, selectedGapId, threadsByGap]);

  async function continueDiscussion(message: string) {
    if (!humanSelectTask || !selectedGapId) return;
    const trimmed = message.trim();
    const history = currentThread.slice();
    const response = await props.discussDirection({
      humanSelectTaskId: humanSelectTask.task_id,
      gapId: selectedGapId,
      userMessage: trimmed,
      history,
    });
    setDiscussionByGap((current) => ({ ...current, [selectedGapId]: response }));
    setThreadsByGap((current) => ({
      ...current,
      [selectedGapId]: [
        ...history,
        ...(trimmed ? [{ role: "user", content: trimmed } satisfies GuideDiscussionMessage] : []),
        { role: "assistant", content: response.assistant_message, metadata: discussionMetadata(response) },
      ],
    }));
    setResearchQuestionByGap((current) => ({
      ...current,
      [selectedGapId]: current[selectedGapId] || response.research_question_suggestion,
    }));
    setChatDraft("");
  }

  const latestPapers = props.paperCards.slice(-4).reverse();
  const latestGapMaps = props.gapMaps.slice(-3).reverse();
  const operatorNotes = currentThread.filter((message) => message.role === "user").map((message) => message.content).join("\n\n");

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [currentThread]);

  return (
    <div className="content-grid overview-grid">
      <Panel title="今天从哪里继续" subtitle="每个项目都显示当前阻塞点，直接点继续即可回到对应工作台。" className="overview-wide-panel">
        {sessionSummaries.length ? <div className="session-grid">
          {sessionSummaries.map((session) => (
            <article key={session.projectId} className={props.selectedProject?.project_id === session.projectId ? "session-card session-card-active" : "session-card"}>
              <div className="session-card-head">
                <div>
                  <strong>{session.name}</strong>
                  <small>{session.projectId}</small>
                </div>
                <StatusPill value={session.waitingHuman ? "waiting_approval" : "running"} />
              </div>
              <div className="session-card-stats">
                <span>已 ingest {session.ingestCount} 篇论文</span>
                <span>已生成 {session.gapCount} 个 gap map</span>
              </div>
              <div className="session-card-focus">
                <strong>{session.currentLabel}</strong>
                <p>{session.helperText}</p>
              </div>
              <button className="button" type="button" onClick={() => props.openProject(session.projectId, session.actionTab)}>{session.actionLabel}</button>
            </article>
          ))}
        </div> : <EmptyState title="还没有研究会话" body="输入一个研究方向，系统就会自动创建项目并开始拉论文。" />}
      </Panel>

      <Panel title="自动研究向导" subtitle="只填研究方向。系统会自动检索 arXiv、生成 paper card、汇总 gap，并在需要你拍板时停下来。" className="overview-guide-panel">
        <div className="pilot-grid">
          <form className="pilot-form" onSubmit={(event) => {
            event.preventDefault();
            void props.startResearch({ researchGoal, projectName });
          }}>
            <label>
              <span>研究方向</span>
              <textarea value={researchGoal} onChange={(event) => setResearchGoal(event.target.value)} placeholder="例如：研究 CIFAR-10 对抗鲁棒性的低算力可复现改进方向。" required />
            </label>
            <label>
              <span>项目名（可选）</span>
              <input value={projectName} onChange={(event) => setProjectName(event.target.value)} placeholder="不填就自动生成" />
            </label>
            <div className="pilot-actions">
              <button className="button" type="submit" disabled={props.isBusy("guide-start")}>开始自动调研</button>
              {props.selectedProject ? <button className="button secondary" type="button" onClick={() => void props.continueAutopilot()} disabled={props.isBusy("guide-autopilot")}>继续自动推进</button> : null}
            </div>
          </form>
          <div className="pilot-side">
            <div className="pilot-step-card">
              <strong>这条链会自动完成什么</strong>
              <ol className="pilot-steps">
                <li>按研究方向检索 arXiv，并批量构造论文候选。</li>
                <li>自动跑文献整理和 gap 聚合，形成候选方向。</li>
                <li>在需要人工判断时切到对话式选题工作台。</li>
                <li>选定方向后继续推进 topic freeze、spec、实验和审阅链路。</li>
              </ol>
            </div>
            {props.projectDashboard ? <div className="pilot-step-card"><strong>当前项目状态</strong><div className="stack-md"><KeyValue label="推荐下一步" value={props.projectDashboard.recommended_next_task_kind || "-"} /><KeyValue label="说明" value={props.projectDashboard.recommendation_reason || "-"} /><KeyValue label="预期产出" value={props.projectDashboard.expected_artifact || "-"} /></div></div> : null}
          </div>
        </div>
      </Panel>

      <Panel className="overview-studio-panel overview-wide-panel" title="像素研究楼层" subtitle="楼层保持完整画幅。角色有各自的工作动作，点击工位看当前状态。">
        <PixelStudio projectTasks={props.projectTasks} projectDashboard={props.projectDashboard} />
      </Panel>

      <Panel title="项目脉搏" subtitle="当前项目的整体运行状态。">
        {props.projectDashboard ? (
          <div className="stack-md">
            <div className="pulse-grid">
              <StatCard label="运行中" value={props.projectDashboard.running_tasks} />
              <StatCard label="待审批" value={props.projectDashboard.waiting_approval_tasks} />
              <StatCard label="已完成" value={props.projectDashboard.succeeded_tasks} />
              <StatCard label="失败" value={props.projectDashboard.failed_tasks} />
            </div>
            <KeyValue label="Topic freeze" value={props.topicFreeze?.topic_id || "尚未确定"} />
            <KeyValue label="Spec freeze" value={props.specFreeze?.spec_id || "尚未生成"} />
          </div>
        ) : (
          <EmptyState title="还没有选中项目" body="先启动一个研究方向，项目脉搏会在这里出现。" />
        )}
      </Panel>

      <Panel title="最新证据" subtitle="最近生成的 paper card 和 gap map。">
        <div className="pilot-evidence-grid">
          <div className="record-card">
            <div className="record-card-head">
              <strong>最近 Paper card</strong>
              <span>{props.paperCards.length}</span>
            </div>
            {latestPapers.length ? (
              <ul className="plain-list">
                {latestPapers.map((paper) => (
                  <li key={paper.paper_id}>
                    {paper.title}
                    <small>{paper.paper_id}</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">还没有论文卡片。</p>
            )}
          </div>
          <div className="record-card">
            <div className="record-card-head">
              <strong>最近 Gap map</strong>
              <span>{props.gapMaps.length}</span>
            </div>
            {latestGapMaps.length ? (
              <ul className="plain-list">
                {latestGapMaps.map((gap) => (
                  <li key={gap.topic}>
                    {gap.topic}
                    <small>{gap.clusters} 个 cluster</small>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted">还没有 gap map。</p>
            )}
          </div>
        </div>
      </Panel>

      {humanSelectTask && rankedCandidates.length ? (
        <Panel className="overview-wide-panel" title="方向工作台" subtitle="左边看候选方向矩阵与证据，右边和选题顾问持续对话。">
          <div className="idea-workbench">
            <div className="candidate-stack">
              <div className="candidate-matrix-card">
                <div className="candidate-matrix-head">
                  <div>
                    <strong>Novelty × Feasibility</strong>
                    <small>横轴越右越新，纵轴越上越容易快速验证。</small>
                  </div>
                  <span>{topic || "当前主题"}</span>
                </div>
                <div className="candidate-matrix">
                  <div className="candidate-matrix-axis candidate-matrix-axis-x"><span>保守</span><span>更有新意</span></div>
                  <div className="candidate-matrix-axis candidate-matrix-axis-y"><span>高可行</span><span>低可行</span></div>
                  {rankedCandidates.map((candidate) => {
                    const gap = gapLookup.get(candidate.gap_id);
                    return (
                      <button
                        key={candidate.gap_id}
                        type="button"
                        className={selectedGapId === candidate.gap_id ? "matrix-point matrix-point-active" : "matrix-point"}
                        style={{ left: `${10 + normalizeNovelty(candidate, gap) * 18}%`, top: `${74 - normalizeFeasibility(candidate, gap) * 20}%` }}
                        onClick={() => setSelectedGapId(candidate.gap_id)}
                      >
                        <span>{candidate.gap_id}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className="candidate-grid">
                {rankedCandidates.map((candidate) => {
                  const gap = gapLookup.get(candidate.gap_id);
                  const paperLabels = (gap?.supportingPapers ?? []).map((paperId) => paperTitleById.get(paperId) || paperId);
                  return (
                    <button
                      key={candidate.gap_id}
                      type="button"
                      className={selectedGapId === candidate.gap_id ? "candidate-card candidate-card-active" : "candidate-card"}
                      onClick={() => {
                        setSelectedGapId(candidate.gap_id);
                        setChatDraft("");
                      }}
                    >
                      <div className="candidate-head">
                        <div>
                          <strong>{candidate.gap_id}</strong>
                          <small>{candidate.score !== null ? `综合评分 ${candidate.score.toFixed(2)}` : "已进入候选池"}</small>
                        </div>
                        <StatusPill value="waiting_approval" />
                      </div>
                      <p>{gap?.description || candidate.rationale || "当前候选方向暂时没有详细描述。"}</p>
                      <div className="candidate-meta">
                        <span>可行性 {gap?.feasibility || candidate.feasibility || "-"}</span>
                        <span>新颖度 {formatScore(gap?.noveltyScore ?? candidate.novelty_score)}</span>
                        <span>难度 {gap?.difficulty || "-"}</span>
                      </div>
                      <div className="candidate-evidence">
                        <strong>证据摘要</strong>
                        <p>{gap?.evidenceSummary || candidate.evidence_summary || "当前还没有证据摘要。"}</p>
                      </div>
                      <div className="candidate-paper-list">
                        {paperLabels.length ? paperLabels.slice(0, 3).map((label) => <small key={label}>{label}</small>) : <small>暂时没有关联论文标题</small>}
                      </div>
                    </button>
                  );
                })}
              </div>
            </div>

            <aside className="discussion-panel">
              <div className="discussion-head discussion-head-chat">
                <div>
                  <strong>选题对话</strong>
                  <small>{selectedGapId || "先选一个候选方向"}</small>
                </div>
                {currentDiscussion ? (
                  <div className="assistant-chip-group">
                    <span className="assistant-chip">{currentDiscussion.assistant_role}</span>
                    <span className="assistant-chip">{currentDiscussion.provider_name} / {currentDiscussion.model_name}</span>
                    <span className="assistant-chip">推理 {currentDiscussion.reasoning_effort}</span>
                  </div>
                ) : null}
              </div>
              {selectedGap ? (
                <div className="discussion-chat-shell">
                  <div className="discussion-brief-card">
                    <div className="discussion-brief-head">
                      <div>
                        <strong>{selectedGapId}</strong>
                        <small>{currentDiscussion?.skill_name || "research-direction-advisor"}</small>
                      </div>
                      <StatusPill value="running" />
                    </div>
                    <p>{selectedGap.description}</p>
                    <div className="candidate-meta">
                      <span>可行性 {selectedGap.feasibility || "-"}</span>
                      <span>新颖度 {formatScore(selectedGap.noveltyScore)}</span>
                      <span>攻击面 {selectedGap.attackSurface || topic || "-"}</span>
                    </div>
                    <div className="discussion-summary-grid">
                      <div className="discussion-mini-card">
                        <strong>证据摘要</strong>
                        <p>{selectedGap.evidenceSummary || "当前还没有补充证据摘要。"}</p>
                      </div>
                      <div className="discussion-mini-card">
                        <strong>关联论文</strong>
                        <ul className="plain-list">
                          {selectedGap.supportingPapers.length ? selectedGap.supportingPapers.map((paperId) => <li key={paperId}>{paperTitleById.get(paperId) || paperId}</li>) : <li>当前没有挂接论文标题。</li>}
                        </ul>
                      </div>
                    </div>
                  </div>

                  <div className="discussion-thread-shell">
                    <div className="discussion-thread">
                      {currentThread.length ? currentThread.map((message, index) => (
                        <div key={`${message.role}-${message.message_id ?? index}`} className={message.role === "assistant" ? "chat-message chat-message-assistant" : "chat-message chat-message-user"}>
                          <div className="chat-avatar">{message.role === "assistant" ? "AI" : "你"}</div>
                          <div className="chat-message-body">
                            <div className="chat-message-meta">
                              <strong>{message.role === "assistant" ? "ResearchOS Advisor" : "你"}</strong>
                              <small>{message.role === "assistant" ? "基于 paper card / gap map 回答" : "追问"}</small>
                            </div>
                            <p>{message.content}</p>
                          </div>
                        </div>
                      )) : (
                        <div className="chat-message chat-message-assistant">
                          <div className="chat-avatar">AI</div>
                          <div className="chat-message-body">
                            <div className="chat-message-meta">
                              <strong>ResearchOS Advisor</strong>
                              <small>初始化中</small>
                            </div>
                            <p>正在读取当前 gap、候选方向和关联 paper card。</p>
                          </div>
                        </div>
                      )}
                      <div ref={threadEndRef} />
                    </div>
                  </div>

                  <div className="discussion-insight-grid">
                    <div className="discussion-card discussion-insight-card">
                      <strong>优势</strong>
                      <ul className="plain-list">{(currentDiscussion?.strengths || []).map((item) => <li key={item}>{item}</li>)}</ul>
                    </div>
                    <div className="discussion-card discussion-insight-card">
                      <strong>风险</strong>
                      <ul className="plain-list">{(currentDiscussion?.risks || []).map((item) => <li key={item}>{item}</li>)}</ul>
                    </div>
                    <div className="discussion-card discussion-insight-card">
                      <strong>接下来先确认什么</strong>
                      <ul className="plain-list">{(currentDiscussion?.next_checks || []).map((item) => <li key={item}>{item}</li>)}</ul>
                    </div>
                  </div>

                  <div className="discussion-composer-shell">
                    <div className="discussion-composer-card">
                      <textarea
                        value={chatDraft}
                        onChange={(event) => setChatDraft(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Enter" && !event.shiftKey) {
                            event.preventDefault();
                            if (chatDraft.trim()) void continueDiscussion(chatDraft);
                          }
                        }}
                        className="discussion-composer-input"
                        placeholder="继续追问这个方向。按 Enter 发送，Shift + Enter 换行。"
                      />
                      <div className="discussion-composer-actions">
                        <small>对话记录会作为 operator note 一并带入后续 topic freeze。</small>
                        <button className="button" type="button" disabled={!selectedGapId || !chatDraft.trim() || props.isBusy(`discuss-${selectedGapId}`)} onClick={() => { void continueDiscussion(chatDraft); }}>发送</button>
                      </div>
                    </div>

                    <div className="discussion-freeze-card">
                      <label className="discussion-form">
                        <span>冻结用研究问题</span>
                        <textarea
                          value={researchQuestion}
                          onChange={(event) => {
                            if (!selectedGapId) return;
                            setResearchQuestionByGap((current) => ({ ...current, [selectedGapId]: event.target.value }));
                          }}
                          placeholder="如果不填，系统会采用顾问给出的研究问题建议。"
                        />
                      </label>
                      <button className="button" type="button" disabled={!selectedGapId || props.isBusy(`adopt-${selectedGapId}`)} onClick={() => {
                        if (!humanSelectTask || !selectedGapId) return;
                        void props.adoptDirection({
                          humanSelectTaskId: humanSelectTask.task_id,
                          gapId: selectedGapId,
                          researchQuestion: researchQuestion || suggestedResearchQuestion,
                          operatorNote: operatorNotes,
                        });
                      }}>采用这个方向并继续</button>
                    </div>
                  </div>
                </div>
              ) : <EmptyState title="先选一个候选方向" body="点击左侧任意候选卡片，右侧就会载入真实 LLM 对话。" />}
            </aside>
          </div>
        </Panel>
      ) : (
        <Panel className="overview-wide-panel" title="方向工作台" subtitle="自动流程跑到 human_select 后，这里会出现候选方向矩阵和选题对话。">
          <EmptyState title="还没有候选方向" body="先点上面的“开始自动调研”或“继续自动推进”。系统跑到 human_select 时，这里会自动出现候选 idea。" />
        </Panel>
      )}

      <Panel title="路由系统" subtitle="当前默认 dispatch 和 provider 健康状态。">
        <div className="stack-md">
          <KeyValue label="Provider" value={props.routingSystem.resolved_dispatch.provider_name} />
          <KeyValue label="模型" value={props.routingSystem.resolved_dispatch.model ?? "<default>"} />
          <KeyValue label="决策来源" value={props.routingSystem.resolved_dispatch.decision_reason ?? "system_default"} />
          <div className="provider-list compact">
            {props.providers.map((provider) => (
              <div key={provider.provider_family} className="provider-row">
                <div>
                  <strong>{provider.provider_family}</strong>
                  <small>{provider.detail || "当前状态正常。"}</small>
                </div>
                <StatusPill value={provider.state} />
              </div>
            ))}
          </div>
        </div>
      </Panel>

      <Panel title="待处理审批" subtitle="仍然需要人工确认的决定。">
        {props.approvals.length ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>审批单</th>
                  <th>目标</th>
                  <th>决定</th>
                  <th>操作人</th>
                </tr>
              </thead>
              <tbody>
                {props.approvals.map((approval) => (
                  <tr key={approval.approval_id}>
                    <td>{approval.approval_id}</td>
                    <td>{approval.target_type}:{approval.target_id}</td>
                    <td><StatusPill value={approval.decision} /></td>
                    <td>{approval.approved_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : <EmptyState title="当前没有待处理审批" body="自动流程会尽量往前推，只在真的需要拍板时才会停下来。" />}
      </Panel>
    </div>
  );
}

function buildSession(
  project: Project,
  ingestCount: number,
  gapCount: number,
  currentLabel: string,
  helperText: string,
  actionLabel: string,
  actionTab: WorkbenchTab,
  waitingHuman: boolean,
): SessionSummary {
  return { projectId: project.project_id, name: project.name, ingestCount, gapCount, currentLabel, helperText, actionLabel, actionTab, waitingHuman };
}

function discussionMetadata(response: GuideDiscussDirectionResponse): Record<string, unknown> {
  return {
    thread_id: response.thread_id,
    gap_id: response.gap_id,
    topic: response.topic,
    strengths: response.strengths,
    risks: response.risks,
    next_checks: response.next_checks,
    cited_papers: response.cited_papers,
    research_question_suggestion: response.research_question_suggestion,
    assistant_role: response.assistant_role,
    provider_name: response.provider_name,
    model_name: response.model_name,
    reasoning_effort: response.reasoning_effort,
    skill_name: response.skill_name,
  };
}

function discussionFromHistory(history: DiscussionHistory, gapId: string): GuideDiscussDirectionResponse | null {
  const assistant = [...history.messages].reverse().find((message) => message.role === "assistant" && message.metadata);
  if (!assistant?.metadata) return null;
  const metadata = assistant.metadata;
  return {
    thread_id: typeof metadata.thread_id === "string" ? metadata.thread_id : history.thread_id,
    assistant_message: assistant.content,
    gap_id: gapId,
    topic: typeof metadata.topic === "string" ? metadata.topic : "",
    strengths: Array.isArray(metadata.strengths) ? metadata.strengths.map(String) : [],
    risks: Array.isArray(metadata.risks) ? metadata.risks.map(String) : [],
    next_checks: Array.isArray(metadata.next_checks) ? metadata.next_checks.map(String) : [],
    cited_papers: Array.isArray(metadata.cited_papers) ? metadata.cited_papers.map(String) : [],
    research_question_suggestion: typeof metadata.research_question_suggestion === "string" ? metadata.research_question_suggestion : "",
    assistant_role: typeof metadata.assistant_role === "string" ? metadata.assistant_role : "Advisor",
    provider_name: typeof metadata.provider_name === "string" ? metadata.provider_name : "codex",
    model_name: typeof metadata.model_name === "string" ? metadata.model_name : "gpt-5.4",
    reasoning_effort: typeof metadata.reasoning_effort === "string" ? metadata.reasoning_effort : "high",
    skill_name: typeof metadata.skill_name === "string" ? metadata.skill_name : "research-direction-advisor",
  };
}

function normalizeNovelty(candidate: RankedCandidate, gap: GapSummary | null | undefined) {
  const raw = gap?.noveltyScore || candidate.novelty_score || candidate.score || 0;
  return Math.max(0, Math.min(5, raw));
}

function normalizeFeasibility(candidate: RankedCandidate, gap: GapSummary | null | undefined) {
  const label = (gap?.feasibility || candidate.feasibility || "").toLowerCase();
  if (label.includes("high")) return 3;
  if (label.includes("medium")) return 2;
  if (label.includes("low")) return 1;
  return 2;
}

function formatScore(value: number) {
  return value ? value.toFixed(1) : "-";
}
