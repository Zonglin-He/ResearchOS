import { useEffect, useMemo, useRef, useState } from "react";
import type {
  DiscussionHistory,
  GapMap,
  GapMapDetail,
  GuideDiscussDirectionResponse,
  GuideDiscussionMessage,
  KnowledgeRecord,
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

type MainTab = "workspace" | "registry";
type SystemSection = "operations" | "advanced";

type Props = {
  projects: Project[];
  selectedProject: Project | null;
  allTasks: Task[];
  projectTasks: Task[];
  projectDashboard: ProjectDashboard | null;
  providers: ProviderHealthSnapshot[];
  routingSystem: RoutingInspection;
  approvals: Array<{ approval_id: string; target_type: string; target_id: string; decision: string; approved_by: string }>;
  paperCards: PaperCard[];
  gapMaps: GapMap[];
  openQuestions: KnowledgeRecord[];
  topicFreeze: TopicFreeze | null;
  specFreeze: SpecFreeze | null;
  activityLog: string[];
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
  openProject: (projectId: string, tab?: MainTab) => void;
  openSystem: (section: SystemSection, focus?: "project" | "topic_freeze" | null) => void;
  isBusy: (key: string) => boolean;
};

type Candidate = {
  gapId: string;
  summary: string;
  rationale: string;
  score: number | null;
  feasibility: string;
  novelty: number;
  supportingPapers: string[];
  difficulty: string;
  noveltyType: string;
  attackSurface: string;
};

type SessionSummary = {
  projectId: string;
  name: string;
  stage: string;
  ingestCount: number;
  gapCount: number;
  helperText: string;
  actionLabel: string;
};

const PIPELINE_STEPS = [
  { label: "论文摄入", stages: ["INGEST_PAPERS"] },
  { label: "构建卡片", stages: ["BUILD_PAPER_CARDS"] },
  { label: "Gap 分析", stages: ["MAP_GAPS"] },
  { label: "选方向", stages: ["HUMAN_SELECT"] },
  { label: "冻结", stages: ["FREEZE_TOPIC", "FREEZE_SPEC", "REPRO_BASELINES", "IMPLEMENT_IDEA"] },
  { label: "实验", stages: ["RUN_EXPERIMENTS", "AUDIT_RESULTS", "FREEZE_RESULTS"] },
  { label: "写作", stages: ["WRITE_DRAFT", "REVIEW_DRAFT", "STYLE_PASS", "SUBMISSION_READY"] },
] as const;

const TASK_KIND_META: Record<string, { icon: string; label: string }> = {
  paper_ingest: { icon: "📄", label: "摄入论文" },
  gap_mapping: { icon: "🗺", label: "分析 Gap" },
  human_select: { icon: "🎯", label: "选择方向" },
  build_spec: { icon: "🧩", label: "生成规格" },
  experiment_spec: { icon: "🧩", label: "实验规格" },
  branch_plan: { icon: "🌿", label: "规划分支" },
  branch_review: { icon: "🏁", label: "分支收敛" },
  implement_experiment: { icon: "🔬", label: "实现实验" },
  run_experiment: { icon: "⚡", label: "运行实验" },
  analyze_run: { icon: "📊", label: "分析结果" },
  review_build: { icon: "🛡", label: "复核构建" },
  write_draft: { icon: "✍", label: "写作草稿" },
};

export function OverviewTab(props: Props) {
  const [researchGoal, setResearchGoal] = useState("");
  const [projectName, setProjectName] = useState("");
  const [selectedGapId, setSelectedGapId] = useState("");
  const [chatDraft, setChatDraft] = useState("");
  const [gapMapDetail, setGapMapDetail] = useState<GapMapDetail | null>(null);
  const [discussionByGap, setDiscussionByGap] = useState<Record<string, GuideDiscussDirectionResponse>>({});
  const [threadByGap, setThreadByGap] = useState<Record<string, GuideDiscussionMessage[]>>({});
  const [questionByGap, setQuestionByGap] = useState<Record<string, string>>({});
  const [historyLoadedByGap, setHistoryLoadedByGap] = useState<Record<string, boolean>>({});
  const [expandedDebates, setExpandedDebates] = useState<Record<string, boolean>>({});
  const [minNovelty, setMinNovelty] = useState(0);
  const [minFeasibility, setMinFeasibility] = useState(1);
  const threadEndRef = useRef<HTMLDivElement | null>(null);

  const humanSelectTask = useMemo(
    () =>
      props.projectTasks.find(
        (task) => task.kind === "human_select" && task.status !== "cancelled" && task.status !== "succeeded",
      ) ?? null,
    [props.projectTasks],
  );

  const topic = typeof humanSelectTask?.input_payload.topic === "string" ? humanSelectTask.input_payload.topic : "";

  const candidates = useMemo<Candidate[]>(() => {
    const raw = humanSelectTask?.input_payload.ranked_candidates;
    if (!Array.isArray(raw)) return [];
    return raw
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
      .map((item) => ({
        gapId: typeof item.gap_id === "string" ? item.gap_id : "",
        summary:
          firstNonEmptyString(item.evidence_summary, item.description, item.rationale) ||
          (typeof item.gap_id === "string" ? item.gap_id : ""),
        rationale: firstNonEmptyString(item.rationale, item.evidence_summary),
        score: typeof item.score === "number" ? item.score : null,
        feasibility: typeof item.feasibility === "string" ? item.feasibility : "",
        novelty: typeof item.novelty_score === "number" ? item.novelty_score : 0,
        supportingPapers: Array.isArray(item.supporting_papers) ? item.supporting_papers.map(String) : [],
        difficulty: typeof item.difficulty === "string" ? item.difficulty : "",
        noveltyType: typeof item.novelty_type === "string" ? item.novelty_type : "",
        attackSurface: typeof item.attack_surface === "string" ? item.attack_surface : "",
      }))
      .filter((item) => item.gapId);
  }, [humanSelectTask]);

  const candidateGapIds = useMemo(() => new Set(candidates.map((candidate) => candidate.gapId)), [candidates]);

  const debateByGap = useMemo(() => {
    const grouped: Record<string, KnowledgeRecord[]> = {};
    for (const record of props.openQuestions) {
      if (props.selectedProject && record.project_id !== props.selectedProject.project_id) {
        continue;
      }
      const payload = record.payload ?? {};
      const payloadGapId =
        typeof payload.candidate_gap_id === "string"
          ? payload.candidate_gap_id
          : typeof payload.gap_id === "string"
            ? payload.gap_id
            : "";
      const taggedGapId = record.context_tags.find((tag) => candidateGapIds.has(tag)) ?? "";
      const gapId = payloadGapId || taggedGapId;
      if (!gapId) continue;
      grouped[gapId] = [...(grouped[gapId] ?? []), record];
    }
    return grouped;
  }, [candidateGapIds, props.openQuestions, props.selectedProject]);

  const filteredCandidates = useMemo(
    () =>
      candidates.filter(
        (candidate) =>
          candidate.novelty >= minNovelty && feasibilityScore(candidate.feasibility) >= minFeasibility,
      ),
    [candidates, minNovelty, minFeasibility],
  );

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
    if (!filteredCandidates.length) {
      setSelectedGapId("");
      return;
    }
    setSelectedGapId((current) =>
      filteredCandidates.some((item) => item.gapId === current) ? current : filteredCandidates[0].gapId,
    );
  }, [filteredCandidates]);

  useEffect(() => {
    if (!selectedGapId || !humanSelectTask || historyLoadedByGap[selectedGapId]) return;
    let cancelled = false;
    const task = humanSelectTask;
    async function loadHistoryOnly() {
      try {
        const history = await props.loadDiscussionHistory(task.task_id, selectedGapId);
        if (cancelled) return;
        if (history.messages.length) {
          setThreadByGap((current) => ({ ...current, [selectedGapId]: history.messages }));
          const restored = discussionFromHistory(history, selectedGapId);
          if (restored) {
            setDiscussionByGap((current) => ({ ...current, [selectedGapId]: restored }));
            setQuestionByGap((current) => ({
              ...current,
              [selectedGapId]: restored.research_question_suggestion,
            }));
          }
        }
      } catch {
        if (cancelled) return;
      } finally {
        if (!cancelled) {
          setHistoryLoadedByGap((current) => ({ ...current, [selectedGapId]: true }));
        }
      }
    }
    void loadHistoryOnly();
    return () => {
      cancelled = true;
    };
  }, [historyLoadedByGap, humanSelectTask, props, selectedGapId]);

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [selectedGapId, threadByGap]);

  const selectedCandidate = filteredCandidates.find((candidate) => candidate.gapId === selectedGapId) ?? null;
  const selectedGapDetail = useMemo(() => findGapDetail(gapMapDetail, selectedGapId), [gapMapDetail, selectedGapId]);
  const currentDiscussion = selectedGapId ? discussionByGap[selectedGapId] ?? null : null;
  const currentThread = selectedGapId ? threadByGap[selectedGapId] ?? [] : [];
  const researchQuestion = selectedGapId
    ? questionByGap[selectedGapId] ?? currentDiscussion?.research_question_suggestion ?? ""
    : "";
  const stageIndex = stageStepIndex(props.selectedProject?.stage ?? "NEW_TOPIC");
  const recentTasks = props.projectTasks
    .slice()
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
    .slice(0, 6);
  const attention = buildAttention(props, humanSelectTask);
  const shouldShowLoadAdvisorPrompt =
    Boolean(selectedGapId) &&
    !currentThread.length &&
    Boolean(historyLoadedByGap[selectedGapId]) &&
    !props.isBusy(`discuss-${selectedGapId}`);

  async function hydrateGap(gapId: string) {
    if (!humanSelectTask || !gapId) return;
    const history = threadByGap[gapId] ?? [];
    const response = await props.discussDirection({
      humanSelectTaskId: humanSelectTask.task_id,
      gapId,
      userMessage: "",
      history,
    });
    setDiscussionByGap((current) => ({ ...current, [gapId]: response }));
    setThreadByGap((current) => ({
      ...current,
      [gapId]: [...history, { role: "assistant", content: response.assistant_message, metadata: discussionMetadata(response) }],
    }));
    setQuestionByGap((current) => ({ ...current, [gapId]: current[gapId] || response.research_question_suggestion }));
  }

  async function continueDiscussion() {
    if (!humanSelectTask || !selectedGapId || !chatDraft.trim()) return;
    const history = currentThread.slice();
    const message = chatDraft.trim();
    const response = await props.discussDirection({
      humanSelectTaskId: humanSelectTask.task_id,
      gapId: selectedGapId,
      userMessage: message,
      history,
    });
    setDiscussionByGap((current) => ({ ...current, [selectedGapId]: response }));
    setThreadByGap((current) => ({
      ...current,
      [selectedGapId]: [
        ...history,
        { role: "user", content: message },
        { role: "assistant", content: response.assistant_message, metadata: discussionMetadata(response) },
      ],
    }));
    setQuestionByGap((current) => ({
      ...current,
      [selectedGapId]: current[selectedGapId] || response.research_question_suggestion,
    }));
    setChatDraft("");
  }

  function toggleDebate(gapId: string) {
    setExpandedDebates((current) => ({ ...current, [gapId]: !current[gapId] }));
  }

  return (
    <div className="content-grid workspace-grid">
      <Panel
        className="workspace-wide-panel"
        title="研究流程"
        subtitle={
          props.selectedProject
            ? `当前阶段：${stageLabel(props.selectedProject.stage)}`
            : "启动一个研究主题后，这里会显示完整流程。"
        }
      >
        <div className="stage-pipeline">
          {PIPELINE_STEPS.map((step, index) => (
            <div
              key={step.label}
              className={
                stageIndex === index ? "stage-step active" : stageIndex > index ? "stage-step done" : "stage-step"
              }
            >
              <div className="stage-step-index">{stageIndex > index ? "✓" : index + 1}</div>
              <div className="stage-step-copy">
                <strong>{step.label}</strong>
                <small>{stageIndex === index ? "你在这里" : stageIndex > index ? "已完成" : "尚未到达"}</small>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      {humanSelectTask && candidates.length ? (
        <Panel
          className="workspace-wide-panel"
          title="方向工作台"
          subtitle="先用矩阵筛一遍候选方向，再按需加载顾问分析。"
        >
          <div className="idea-workbench">
            <div className="candidate-stack">
              <div className="candidate-matrix-card">
                <div className="candidate-matrix-head">
                  <div>
                    <strong>Novelty × Feasibility</strong>
                    <small>点击矩阵上的点或左下角卡片，右侧再决定是否加载顾问分析。</small>
                  </div>
                  <span>{filteredCandidates.length} 个候选</span>
                </div>
                <div className="matrix-filter-bar">
                  <label className="matrix-filter-group">
                    <span>最低新颖度：{minNovelty.toFixed(1)}</span>
                    <input
                      type="range"
                      min="0"
                      max="5"
                      step="0.5"
                      value={minNovelty}
                      onChange={(event) => setMinNovelty(Number(event.target.value))}
                    />
                  </label>
                  <label className="matrix-filter-group">
                    <span>最低可行性：{feasibilityLabel(minFeasibility)}</span>
                    <input
                      type="range"
                      min="1"
                      max="3"
                      step="1"
                      value={minFeasibility}
                      onChange={(event) => setMinFeasibility(Number(event.target.value))}
                    />
                  </label>
                </div>
                <div className="candidate-matrix">
                  <div className="candidate-matrix-axis candidate-matrix-axis-y">
                    <span>高可行</span>
                    <span>低可行</span>
                  </div>
                  <div className="candidate-matrix-axis candidate-matrix-axis-x">
                    <span>低新颖</span>
                    <span>高新颖</span>
                  </div>
                  {filteredCandidates.map((candidate) => (
                    <button
                      key={candidate.gapId}
                      type="button"
                      className={selectedGapId === candidate.gapId ? "matrix-point matrix-point-active" : "matrix-point"}
                      style={matrixPointStyle(candidate)}
                      onClick={() => setSelectedGapId(candidate.gapId)}
                    >
                      {candidate.gapId}
                    </button>
                  ))}
                </div>
                {!filteredCandidates.length ? (
                  <div className="matrix-empty">当前筛选条件下没有候选方向，调低阈值后再看。</div>
                ) : null}
              </div>

              <div className="candidate-stack-header">
                <strong>候选方向</strong>
                <small>卡片标题直接显示方向描述，技术 ID 放到副标题。</small>
              </div>

              {filteredCandidates.length ? (
                filteredCandidates.map((candidate) => {
                  const debates = debateByGap[candidate.gapId] ?? [];
                  return (
                    <button
                      key={candidate.gapId}
                      type="button"
                      className={selectedGapId === candidate.gapId ? "candidate-card candidate-card-active" : "candidate-card"}
                      onClick={() => setSelectedGapId(candidate.gapId)}
                    >
                      <div className="candidate-head">
                        <div>
                          <strong>{candidate.summary.slice(0, 88)}</strong>
                          <small>
                            {candidate.gapId}
                            {candidate.score !== null ? ` · 评分 ${candidate.score.toFixed(2)}` : " · 候选方向"}
                          </small>
                        </div>
                        <StatusPill value="waiting_approval" />
                      </div>
                      <p>{candidate.rationale || candidate.summary}</p>
                      <div className="candidate-evidence">
                        <strong>方向画像</strong>
                        <p>
                          攻击面：{candidate.attackSurface || "未说明"} · 难度：{candidate.difficulty || "未说明"} ·
                          可行性：{candidate.feasibility || "未说明"} · 新颖类型：{candidate.noveltyType || "未说明"}
                        </p>
                      </div>
                      {candidate.supportingPapers.length ? (
                        <div className="candidate-paper-list">
                          {candidate.supportingPapers.slice(0, 4).map((paperId) => (
                            <small key={paperId}>{paperId}</small>
                          ))}
                        </div>
                      ) : null}
                      <div className="candidate-meta">
                        <span>可行性：{candidate.feasibility || "-"}</span>
                        <span>新颖度：{candidate.novelty ? candidate.novelty.toFixed(1) : "-"}</span>
                      </div>
                      {debates.length ? (
                        <div className="candidate-debate-block" onClick={(event) => event.stopPropagation()}>
                          <button
                            className="button tiny secondary candidate-debate-toggle"
                            type="button"
                            onClick={() => toggleDebate(candidate.gapId)}
                          >
                            {expandedDebates[candidate.gapId] ? "收起质疑记录" : `展开质疑记录 (${debates.length})`}
                          </button>
                          {expandedDebates[candidate.gapId] ? (
                            <div className="candidate-debate-panel">
                              {debates.map((record) => {
                                const constraints = Array.isArray(record.payload.recommended_constraints)
                                  ? record.payload.recommended_constraints.map(String)
                                  : [];
                                return (
                                  <article key={record.record_id} className="candidate-debate-item">
                                    <strong>{record.title}</strong>
                                    <p>{record.summary}</p>
                                    {constraints.length ? (
                                      <small>建议约束：{constraints.join("；")}</small>
                                    ) : null}
                                  </article>
                                );
                              })}
                            </div>
                          ) : null}
                        </div>
                      ) : null}
                    </button>
                  );
                })
              ) : (
                <EmptyState title="没有符合筛选条件的方向" body="调低筛选条件，或者先回看原始 Gap Map。" />
              )}
            </div>

            <aside className="discussion-panel">
              <div className="discussion-head discussion-head-chat">
                <div>
                  <strong>选题顾问</strong>
                  <small>{selectedGapId || "先选一个候选方向"}</small>
                </div>
                {currentDiscussion ? (
                  <div className="assistant-chip-group">
                    <span className="assistant-chip">{currentDiscussion.assistant_role}</span>
                    <span className="assistant-chip">
                      {currentDiscussion.provider_name} / {currentDiscussion.model_name}
                    </span>
                    <span className="assistant-chip">推理 {currentDiscussion.reasoning_effort}</span>
                  </div>
                ) : null}
              </div>

              {selectedGapId && selectedCandidate ? (
                <div className="discussion-chat-shell">
                  <div className="discussion-brief-card">
                    <div className="discussion-brief-head">
                      <div>
                        <strong>{selectedCandidate.summary}</strong>
                        <small>{selectedCandidate.gapId}</small>
                      </div>
                      <StatusPill value="waiting_approval" />
                    </div>
                    <p>{selectedCandidate.rationale || selectedCandidate.summary}</p>
                    <div className="candidate-meta">
                      <span>可行性：{selectedCandidate.feasibility || "-"}</span>
                      <span>新颖度：{selectedCandidate.novelty ? selectedCandidate.novelty.toFixed(1) : "-"}</span>
                      {selectedGapDetail?.difficulty ? <span>难度：{selectedGapDetail.difficulty}</span> : null}
                    </div>
                  </div>

                  {selectedGapDetail ? (
                    <div className="discussion-card discussion-detail-card">
                      <strong>Gap 详情</strong>
                      <p>{selectedGapDetail.description}</p>
                      <div className="discussion-support-papers">
                        <span>支撑论文</span>
                        <div className="candidate-paper-list">
                          {selectedGapDetail.supporting_papers.map((paperId) => (
                            <small key={paperId}>{paperId}</small>
                          ))}
                        </div>
                      </div>
                    </div>
                  ) : null}

                  {shouldShowLoadAdvisorPrompt ? (
                    <div className="discussion-load-prompt">
                      <strong>顾问分析尚未加载</strong>
                      <p>只有在你真的想深聊这个方向时，才会触发模型分析。首次加载通常需要约 30 秒。</p>
                      <button
                        className="button"
                        type="button"
                        onClick={() => void hydrateGap(selectedGapId)}
                        disabled={props.isBusy(`discuss-${selectedGapId}`)}
                      >
                        加载顾问分析
                      </button>
                    </div>
                  ) : (
                    <>
                      <div className="discussion-thread-shell">
                        <div className="discussion-thread">
                          {currentThread.length ? (
                            currentThread.map((message, index) => (
                              <div
                                key={`${message.role}-${message.message_id ?? index}`}
                                className={
                                  message.role === "assistant"
                                    ? "chat-message chat-message-assistant"
                                    : "chat-message chat-message-user"
                                }
                              >
                                <div className="chat-avatar">{message.role === "assistant" ? "AI" : "你"}</div>
                                <div className="chat-message-body">
                                  <div className="chat-message-meta">
                                    <strong>{message.role === "assistant" ? "Research Advisor" : "你"}</strong>
                                    <small>{message.role === "assistant" ? "基于当前证据回答" : "追问"}</small>
                                  </div>
                                  <p>{message.content}</p>
                                </div>
                              </div>
                            ))
                          ) : props.isBusy(`discuss-${selectedGapId}`) ? (
                            <EmptyState title="顾问分析生成中" body="正在读取 Gap Map 和相关论文卡片。" />
                          ) : (
                            <EmptyState title="还没有讨论内容" body="先点击上面的按钮加载顾问分析，再继续追问。" />
                          )}
                          <div ref={threadEndRef} />
                        </div>
                      </div>

                      {currentDiscussion ? (
                        <div className="discussion-insight-grid">
                          <div className="discussion-card discussion-insight-card">
                            <strong>优势</strong>
                            <ul className="plain-list">
                              {currentDiscussion.strengths.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                          <div className="discussion-card discussion-insight-card">
                            <strong>风险</strong>
                            <ul className="plain-list">
                              {currentDiscussion.risks.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                          <div className="discussion-card discussion-insight-card">
                            <strong>下一步确认</strong>
                            <ul className="plain-list">
                              {currentDiscussion.next_checks.map((item) => (
                                <li key={item}>{item}</li>
                              ))}
                            </ul>
                          </div>
                        </div>
                      ) : null}

                      <div className="discussion-composer-card">
                        <textarea
                          value={chatDraft}
                          onChange={(event) => setChatDraft(event.target.value)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" && !event.shiftKey) {
                              event.preventDefault();
                              void continueDiscussion();
                            }
                          }}
                          className="discussion-composer-input"
                          placeholder="继续追问这个方向。Enter 发送，Shift + Enter 换行。"
                        />
                        <div className="discussion-composer-actions">
                          <small>讨论历史会保存在当前项目里，再次进入会恢复。</small>
                          <button
                            className="button"
                            type="button"
                            onClick={() => void continueDiscussion()}
                            disabled={!chatDraft.trim() || props.isBusy(`discuss-${selectedGapId}`)}
                          >
                            发送
                          </button>
                        </div>
                      </div>

                      <div className="discussion-freeze-card">
                        <label className="discussion-form">
                          <span>冻结用研究问题</span>
                          <textarea
                            value={researchQuestion}
                            onChange={(event) =>
                              setQuestionByGap((current) => ({ ...current, [selectedGapId]: event.target.value }))
                            }
                            placeholder="不填就采用顾问建议。"
                          />
                        </label>
                        <button
                          className="button"
                          type="button"
                          onClick={() => {
                            if (!humanSelectTask || !selectedGapId) return;
                            void props.adoptDirection({
                              humanSelectTaskId: humanSelectTask.task_id,
                              gapId: selectedGapId,
                              researchQuestion:
                                researchQuestion || currentDiscussion?.research_question_suggestion || "",
                              operatorNote: currentThread
                                .filter((message) => message.role === "user")
                                .map((message) => message.content)
                                .join("\n\n"),
                            });
                          }}
                          disabled={!selectedGapId || props.isBusy(`adopt-${selectedGapId}`)}
                        >
                          采用这个方向并继续
                        </button>
                      </div>
                    </>
                  )}
                </div>
              ) : (
                <EmptyState title="先选一个候选方向" body="左边点击一个方向，右边会显示顾问对话区。" />
              )}
            </aside>
          </div>
        </Panel>
      ) : null}

      <div className="workspace-focus-grid workspace-wide-panel">
        <Panel title="现在需要你" subtitle="这里只放当前最重要的一件事。">
          {!props.selectedProject ? (
            <form
              className="pilot-form"
              onSubmit={(event) => {
                event.preventDefault();
                void props.startResearch({ researchGoal, projectName });
              }}
            >
              <label>
                <span>研究方向</span>
                <textarea
                  value={researchGoal}
                  onChange={(event) => setResearchGoal(event.target.value)}
                  placeholder="例如：研究 CIFAR-10 对抗鲁棒性的低算力可复现改进方向。"
                  required
                />
              </label>
              <label>
                <span>项目名称（可选）</span>
                <input
                  value={projectName}
                  onChange={(event) => setProjectName(event.target.value)}
                  placeholder="不填就自动生成"
                />
              </label>
              <div className="pilot-actions">
                <button className="button" type="submit" disabled={props.isBusy("guide-start")}>
                  开始自动调研
                </button>
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => props.openSystem("advanced", "project")}
                >
                  手动立项
                </button>
              </div>
            </form>
          ) : (
            <div
              className={
                attention.tone === "warn"
                  ? "workspace-action-card warn"
                  : attention.tone === "good"
                    ? "workspace-action-card good"
                    : "workspace-action-card"
              }
            >
              <div className="workspace-action-head">
                <div>
                  <strong>{attention.title}</strong>
                  <small>{attention.body}</small>
                </div>
                <StatusPill
                  value={attention.tone === "warn" ? "blocked" : attention.tone === "good" ? "succeeded" : "running"}
                />
              </div>
              <div className="workspace-action-actions">
                {attention.onAction ? (
                  <button className="button" type="button" onClick={attention.onAction}>
                    {attention.actionLabel}
                  </button>
                ) : null}
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => void props.continueAutopilot()}
                  disabled={props.isBusy("guide-autopilot")}
                >
                  继续自动推进
                </button>
              </div>
              {props.isBusy("guide-autopilot") && props.activityLog.length ? (
                <div className="activity-log">
                  {props.activityLog.map((line, index) => (
                    <p key={`${line}-${index}`}>{line}</p>
                  ))}
                </div>
              ) : null}
            </div>
          )}
        </Panel>

        <Panel title="项目状态" subtitle="右侧只保留稳定快照，不夹杂操作。">
          {props.selectedProject && props.projectDashboard ? (
            <div className="workspace-status-stack">
              <div className="workspace-status-stats">
                <StatCard label="运行中" value={props.projectDashboard.running_tasks} />
                <StatCard label="等待审批" value={props.projectDashboard.waiting_approval_tasks} />
                <StatCard label="已完成" value={props.projectDashboard.succeeded_tasks} />
                <StatCard label="失败" value={props.projectDashboard.failed_tasks} />
              </div>
              <div className="workspace-status-list">
                <KeyValue label="当前阶段" value={stageLabel(props.selectedProject.stage)} />
                <KeyValue label="推荐下一步" value={props.projectDashboard.recommended_next_task_kind || "-"} />
                <KeyValue label="推荐原因" value={props.projectDashboard.recommendation_reason || "-"} />
                <KeyValue label="最近证据" value={latestEvidence(props.paperCards, props.gapMaps)} />
              </div>
            </div>
          ) : (
            <EmptyState title="还没有项目状态" body="启动一个主题后，这里会显示项目快照。" />
          )}
        </Panel>
      </div>

      <Panel className="workspace-wide-panel overview-studio-panel" title="像素研究楼层" subtitle="地图占整行，不再被工作台挤压。">
        <PixelStudio projectTasks={props.projectTasks} projectDashboard={props.projectDashboard} />
      </Panel>

      <div className="workspace-secondary-grid workspace-wide-panel">
        <Panel title="当前任务流" subtitle="默认显示语义化任务，而不是技术 ID。">
          {recentTasks.length ? (
            <div className="semantic-task-list">
              {recentTasks.map((task) => {
                const meta = taskMeta(task.kind);
                return (
                  <div key={task.task_id} className="semantic-task-card">
                    <div className="semantic-task-main">
                      <div className="semantic-task-icon">{meta.icon}</div>
                      <div className="semantic-task-copy">
                        <strong>{meta.label}</strong>
                        <p>{taskSummary(task)}</p>
                        <small>{task.created_at.replace("T", " ").slice(0, 16)}</small>
                      </div>
                    </div>
                    <StatusPill value={task.status} />
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState title="当前没有任务" body="流程启动后，这里会按阶段显示最近任务。" />
          )}
        </Panel>

        <Panel title="继续中的研究会话" subtitle="每个项目都标出当前卡点，直接点继续。">
          {props.projects.length ? (
            <div className="session-grid">
              {buildSessions(props).map((session) => (
                <article
                  key={session.projectId}
                  className={
                    props.selectedProject?.project_id === session.projectId ? "session-card session-card-active" : "session-card"
                  }
                >
                  <div className="session-card-head">
                    <div>
                      <strong>{session.name}</strong>
                      <small>{session.projectId}</small>
                    </div>
                    <StatusPill value="running" />
                  </div>
                  <div className="session-card-stats">
                    <span>已 ingest {session.ingestCount} 篇论文</span>
                    <span>已生成 {session.gapCount} 个 Gap Map</span>
                  </div>
                  <div className="session-card-focus">
                    <strong>{session.stage}</strong>
                    <p>{session.helperText}</p>
                  </div>
                  <button className="button" type="button" onClick={() => props.openProject(session.projectId, "workspace")}>
                    {session.actionLabel}
                  </button>
                </article>
              ))}
            </div>
          ) : (
            <EmptyState title="还没有研究会话" body="输入一个研究方向，系统会自动创建项目并开始跑前半段流程。" />
          )}
        </Panel>
      </div>

      <Panel className="workspace-wide-panel" title="系统快照" subtitle="不切到系统抽屉也能看到默认路由和 Provider 健康。">
        <div className="workspace-system-grid">
          <KeyValue label="默认 Provider" value={props.routingSystem.resolved_dispatch.provider_name} />
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
    </div>
  );
}

function taskMeta(kind: string) {
  return TASK_KIND_META[kind] ?? { icon: "🧠", label: kind };
}

function taskSummary(task: Task) {
  if (typeof task.input_payload.title === "string" && task.input_payload.title) return task.input_payload.title;
  if (typeof task.input_payload.goal === "string" && task.input_payload.goal) return task.input_payload.goal;
  if (typeof task.input_payload.source_summary === "object" && task.input_payload.source_summary) {
    const title = (task.input_payload.source_summary as Record<string, unknown>).title;
    if (typeof title === "string" && title) return title;
  }
  return task.goal || "暂无补充说明";
}

function buildSessions(props: Props): SessionSummary[] {
  return props.projects.map((project) => {
    const tasks = props.allTasks.filter((task) => task.project_id === project.project_id);
    const ingestCount = tasks.filter((task) => task.kind === "paper_ingest" && task.status === "succeeded").length;
    const gapCount = tasks.filter((task) => task.kind === "gap_mapping" && task.status === "succeeded").length;
    const pendingHuman = tasks.find(
      (task) => task.kind === "human_select" && task.status !== "cancelled" && task.status !== "succeeded",
    );
    const running = tasks.find((task) => task.status === "running");
    const blocked = tasks.find((task) => ["blocked", "failed", "waiting_approval"].includes(task.status));
    return {
      projectId: project.project_id,
      name: project.name,
      stage: stageLabel(project.stage),
      ingestCount,
      gapCount,
      helperText: pendingHuman
        ? "候选方向已经整理好，等待你拍板。"
        : running
          ? `${taskMeta(running.kind).label} 正在后台运行。`
          : blocked
            ? `${taskMeta(blocked.kind).label} 卡住了，需要人工处理。`
            : "当前没有明显阻塞点，可以继续推进。",
      actionLabel: pendingHuman ? "继续选题" : running ? "查看研究台" : blocked ? "处理问题" : "打开项目",
    };
  });
}

function buildAttention(props: Props, humanSelectTask: Task | null) {
  if (!props.selectedProject) {
    return {
      title: "还没有项目",
      body: "从一个研究方向开始，系统会自动帮你检索论文并推进到需要人工拍板的阶段。",
      tone: "normal" as const,
    };
  }
  const blockedTask = props.projectTasks.find((task) => ["blocked", "failed", "waiting_approval"].includes(task.status));
  const runningTask = props.projectTasks.find((task) => task.status === "running");
  const queuedTask = props.projectTasks.find((task) => task.status === "queued");
  if (humanSelectTask) {
    return {
      title: "现在需要你选方向",
      body: "文献摄入和 Gap 聚合已经完成。方向工作台已经被提到上方，直接筛方向、看质疑记录和顾问分析即可。",
      actionLabel: "查看方向工作台",
      onAction: () => document.querySelector(".idea-workbench")?.scrollIntoView({ behavior: "smooth", block: "start" }),
      tone: "warn" as const,
    };
  }
  if (blockedTask) {
    return {
      title: `${taskMeta(blockedTask.kind).label} 需要处理`,
      body: blockedTask.last_error || blockedTask.goal,
      actionLabel: "打开系统面板",
      onAction: () => props.openSystem("operations"),
      tone: "warn" as const,
    };
  }
  if (runningTask) {
    return {
      title: `${taskMeta(runningTask.kind).label} 正在后台运行`,
      body: runningTask.goal,
      actionLabel: "查看系统面板",
      onAction: () => props.openSystem("operations"),
      tone: "good" as const,
    };
  }
  if (queuedTask) {
    return {
      title: `${taskMeta(queuedTask.kind).label} 已经排队`,
      body: queuedTask.goal,
      actionLabel: "去调度面板",
      onAction: () => props.openSystem("operations"),
      tone: "normal" as const,
    };
  }
  return {
    title: "当前没有人工阻塞点",
    body: "流程处于可继续推进状态。你可以让系统继续自动跑。",
    tone: "good" as const,
  };
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
    STYLE_PASS: "格式整理",
    SUBMISSION_READY: "准备提交",
  };
  return labels[stage] ?? stage;
}

function stageStepIndex(stage: string) {
  return Math.max(0, PIPELINE_STEPS.findIndex((step) => step.stages.includes(stage as never)));
}

function latestEvidence(paperCards: PaperCard[], gapMaps: GapMap[]) {
  const latestGap = gapMaps[gapMaps.length - 1];
  if (latestGap) return `Gap Map · ${latestGap.topic}`;
  const latestPaper = paperCards[paperCards.length - 1];
  if (latestPaper) return `Paper Card · ${latestPaper.title}`;
  return "暂无";
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
    research_question_suggestion:
      typeof metadata.research_question_suggestion === "string" ? metadata.research_question_suggestion : "",
    assistant_role: typeof metadata.assistant_role === "string" ? metadata.assistant_role : "Advisor",
    provider_name: typeof metadata.provider_name === "string" ? metadata.provider_name : "codex",
    model_name: typeof metadata.model_name === "string" ? metadata.model_name : "gpt-5.4",
    reasoning_effort: typeof metadata.reasoning_effort === "string" ? metadata.reasoning_effort : "high",
    skill_name: typeof metadata.skill_name === "string" ? metadata.skill_name : "research-direction-advisor",
  };
}

function findGapDetail(gapMapDetail: GapMapDetail | null, gapId: string) {
  if (!gapMapDetail || !gapId) return null;
  for (const cluster of gapMapDetail.clusters) {
    const match = cluster.gaps.find((gap) => gap.gap_id === gapId);
    if (match) return match;
  }
  return null;
}

function matrixPointStyle(candidate: Candidate) {
  const left = 8 + (Math.min(5, Math.max(0, candidate.novelty)) / 5) * 84;
  const top = 88 - ((feasibilityScore(candidate.feasibility) - 1) / 2) * 72;
  return { left: `${left}%`, top: `${top}%` };
}

function feasibilityScore(value: string) {
  const normalized = value.trim().toLowerCase();
  if (["high", "高", "easy", "strong"].includes(normalized)) return 3;
  if (["medium", "中", "moderate"].includes(normalized)) return 2;
  return 1;
}

function feasibilityLabel(score: number) {
  if (score >= 3) return "高";
  if (score >= 2) return "中";
  return "低";
}

function firstNonEmptyString(...values: unknown[]) {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) {
      return value.trim();
    }
  }
  return "";
}
