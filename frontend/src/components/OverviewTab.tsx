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

type Props = {
  selectedProject: Project | null;
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
  isBusy: (key: string) => boolean;
};

type RankedCandidate = {
  gap_id: string;
  score: number | null;
  rationale: string;
};

type GapSummary = {
  description: string;
  difficulty: string;
  noveltyType: string;
  attackSurface: string;
  supportingPapers: string[];
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
    if (!humanSelectTask) {
      return [] as RankedCandidate[];
    }
    const raw = humanSelectTask.input_payload.ranked_candidates;
    if (!Array.isArray(raw)) {
      return [] as RankedCandidate[];
    }
    return raw
      .filter((item): item is Record<string, unknown> => Boolean(item) && typeof item === "object")
      .map((item) => ({
        gap_id: typeof item.gap_id === "string" ? item.gap_id : "",
        score: typeof item.score === "number" ? item.score : null,
        rationale: typeof item.rationale === "string" ? item.rationale : "",
      }))
      .filter((item) => item.gap_id);
  }, [humanSelectTask]);

  const topic = typeof humanSelectTask?.input_payload.topic === "string" ? humanSelectTask.input_payload.topic : "";

  useEffect(() => {
    if (!props.selectedProject || researchGoal) {
      return;
    }
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
    if (!gapMapDetail) {
      return map;
    }
    gapMapDetail.clusters.forEach((cluster) => {
      cluster.gaps.forEach((gap) => {
        map.set(gap.gap_id, {
          description: gap.description,
          difficulty: gap.difficulty,
          noveltyType: gap.novelty_type,
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

  useEffect(() => {
    if (!selectedGapId || !humanSelectTask || threadsByGap[selectedGapId]?.length) {
      return;
    }
    let cancelled = false;
    const humanSelectTaskId = humanSelectTask.task_id;

    async function hydrate() {
      try {
        const history = await props.loadDiscussionHistory(humanSelectTaskId, selectedGapId);
        if (cancelled) {
          return;
        }
        if (history.messages.length) {
          setThreadsByGap((current) => ({ ...current, [selectedGapId]: history.messages }));
          const restored = discussionFromHistory(history, selectedGapId);
          if (restored) {
            setDiscussionByGap((current) => ({ ...current, [selectedGapId]: restored }));
            setResearchQuestionByGap((current) => ({
              ...current,
              [selectedGapId]:
                current[selectedGapId] || restored.research_question_suggestion,
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
        if (cancelled) {
          return;
        }
        setDiscussionByGap((current) => ({ ...current, [selectedGapId]: response }));
        setThreadsByGap((current) => ({
          ...current,
          [selectedGapId]: [
            {
              role: "assistant",
              content: response.assistant_message,
              metadata: discussionMetadata(response),
            },
          ],
        }));
        setResearchQuestionByGap((current) => ({
          ...current,
          [selectedGapId]: current[selectedGapId] || response.research_question_suggestion,
        }));
      } catch {
        if (cancelled) {
          return;
        }
        setThreadsByGap((current) => ({
          ...current,
          [selectedGapId]: [{ role: "assistant", content: "当前无法连接讨论代理，请稍后再试。" }],
        }));
      }
    }

    void hydrate();
    return () => {
      cancelled = true;
    };
  }, [humanSelectTask, props, selectedGapId, threadsByGap]);

  async function continueDiscussion(message: string) {
    if (!humanSelectTask || !selectedGapId) {
      return;
    }
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
        {
          role: "assistant",
          content: response.assistant_message,
          metadata: discussionMetadata(response),
        },
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
  const operatorNotes = currentThread
    .filter((message) => message.role === "user")
    .map((message) => message.content)
    .join("\n\n");

  useEffect(() => {
    threadEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [currentThread]);

  return (
    <div className="content-grid overview-grid">
      <Panel
        title="自动研究向导"
        subtitle="只填研究方向。系统会自动创建项目、检索论文、整理 gap，并在需要你拍板时停下来。"
      >
        <div className="pilot-grid">
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
              <span>项目名（可选）</span>
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
              {props.selectedProject ? (
                <button
                  className="button secondary"
                  type="button"
                  onClick={() => void props.continueAutopilot()}
                  disabled={props.isBusy("guide-autopilot")}
                >
                  继续自动推进
                </button>
              ) : null}
            </div>
          </form>

          <div className="pilot-side">
            <div className="pilot-step-card">
              <strong>系统会自动做什么</strong>
              <ol className="pilot-steps">
                <li>创建项目并发起 `paper_ingest`。</li>
                <li>自动继续到 `gap_mapping`。</li>
                <li>停在 `human_select`，把候选方向交给你选择。</li>
                <li>选定方向后继续生成 spec、实验、审阅和初稿。</li>
              </ol>
            </div>
            {props.projectDashboard ? (
              <div className="pilot-step-card">
                <strong>当前项目状态</strong>
                <div className="stack-md">
                  <KeyValue label="推荐下一步" value={props.projectDashboard.recommended_next_task_kind || "-"} />
                  <KeyValue label="说明" value={props.projectDashboard.recommendation_reason || "-"} />
                  <KeyValue label="预期产出" value={props.projectDashboard.expected_artifact || "-"} />
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </Panel>

      <Panel
        className="overview-studio-panel"
        title="像素研究楼层"
        subtitle="点击工位看状态。地图保持完整场景，不再被右侧面板挤压。"
      >
        <PixelStudio projectTasks={props.projectTasks} projectDashboard={props.projectDashboard} />
      </Panel>

      <Panel
        className="overview-idea-panel"
        title="选题工作台"
        subtitle={
          humanSelectTask
            ? "左边看候选方向和证据，右边直接和 LLM 对话判断可行性，然后一键继续自动推进。"
            : "自动流程跑到 human_select 后，这里会出现候选方向和讨论侧栏。"
        }
      >
        {humanSelectTask && rankedCandidates.length ? (
          <div className="idea-workbench">
            <div className="idea-grid">
              {rankedCandidates.map((candidate) => {
                const gap = gapLookup.get(candidate.gap_id);
                const paperLabels = (gap?.supportingPapers ?? []).map(
                  (paperId) => paperTitleById.get(paperId) || paperId,
                );
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
                        <small>{candidate.score !== null ? `AI 评分 ${candidate.score.toFixed(2)}` : "AI 已排序"}</small>
                      </div>
                      <StatusPill value="waiting_approval" />
                    </div>
                    <p>{gap?.description || candidate.rationale || "当前候选方向暂无详细描述。"}</p>
                    <div className="candidate-meta">
                      <span>难度 {gap?.difficulty || "-"}</span>
                      <span>新颖性 {gap?.noveltyType || "-"}</span>
                      <span>攻击面 {gap?.attackSurface || topic || "-"}</span>
                    </div>
                    <div className="candidate-paper-list">
                      {paperLabels.length ? (
                        paperLabels.slice(0, 3).map((label) => <small key={label}>{label}</small>)
                      ) : (
                        <small>暂时没有关联论文标题</small>
                      )}
                    </div>
                  </button>
                );
              })}
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
                    <span className="assistant-chip">
                      {currentDiscussion.provider_name} / {currentDiscussion.model_name}
                    </span>
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
                      <span>难度 {selectedGap.difficulty || "-"}</span>
                      <span>新颖性 {selectedGap.noveltyType || "-"}</span>
                      <span>攻击面 {selectedGap.attackSurface || topic || "-"}</span>
                    </div>
                    <div className="candidate-paper-list">
                      {(currentDiscussion?.cited_papers || []).length ? (
                        currentDiscussion?.cited_papers.map((item) => <small key={item}>{item}</small>)
                      ) : (
                        <small>当前回复还没有返回明确引用。</small>
                      )}
                    </div>
                  </div>

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
                                <strong>{message.role === "assistant" ? "ResearchOS Advisor" : "你"}</strong>
                                <small>{message.role === "assistant" ? "基于 paper card / gap map 回答" : "追问"}</small>
                              </div>
                              <p>{message.content}</p>
                            </div>
                          </div>
                        ))
                      ) : (
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
                      <ul className="plain-list">
                        {(currentDiscussion?.strengths || []).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="discussion-card discussion-insight-card">
                      <strong>风险</strong>
                      <ul className="plain-list">
                        {(currentDiscussion?.risks || []).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    </div>
                    <div className="discussion-card discussion-insight-card">
                      <strong>接下来先确认什么</strong>
                      <ul className="plain-list">
                        {(currentDiscussion?.next_checks || []).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
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
                            if (chatDraft.trim()) {
                              void continueDiscussion(chatDraft);
                            }
                          }
                        }}
                        className="discussion-composer-input"
                        placeholder="继续追问这个 idea。按 Enter 发送，Shift + Enter 换行。"
                      />
                      <div className="discussion-composer-actions">
                        <small>当前对话会作为 operator note 一并带入后续 topic freeze。</small>
                        <button
                          className="button"
                          type="button"
                          disabled={!selectedGapId || !chatDraft.trim() || props.isBusy(`discuss-${selectedGapId}`)}
                          onClick={() => {
                            void continueDiscussion(chatDraft);
                          }}
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
                          onChange={(event) => {
                            if (!selectedGapId) {
                              return;
                            }
                            const value = event.target.value;
                            setResearchQuestionByGap((current) => ({ ...current, [selectedGapId]: value }));
                          }}
                          placeholder="如果不填，系统会采用 LLM 给出的研究问题建议。"
                        />
                      </label>

                      <button
                        className="button"
                        type="button"
                        disabled={!selectedGapId || props.isBusy(`adopt-${selectedGapId}`)}
                        onClick={() => {
                          if (!humanSelectTask || !selectedGapId) {
                            return;
                          }
                          void props.adoptDirection({
                            humanSelectTaskId: humanSelectTask.task_id,
                            gapId: selectedGapId,
                            researchQuestion: researchQuestion || suggestedResearchQuestion,
                            operatorNote: operatorNotes,
                          });
                        }}
                      >
                        采用这个方向并继续
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <EmptyState title="先选一个候选方向" body="点左侧任意候选卡片，右侧就会载入真实 LLM 讨论。" />
              )}
            </aside>
          </div>
        ) : (
          <EmptyState
            title="还没有候选方向"
            body="先点上面的“开始自动调研”或“继续自动推进”。系统跑到 human_select 时，这里会自动出现候选 idea。"
          />
        )}
      </Panel>

      <Panel title="项目脉搏" subtitle="当前项目的运行摘要。">
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
          <EmptyState title="还没有选中项目" body="先开始一个自动研究流程，项目脉搏会在这里出现。" />
        )}
      </Panel>

      <Panel title="最新证据" subtitle="最近生成的 paper card 和 gap map。更完整的细节可以在登记页展开。">
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
                    <td>
                      {approval.target_type}:{approval.target_id}
                    </td>
                    <td>
                      <StatusPill value={approval.decision} />
                    </td>
                    <td>{approval.approved_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="当前没有待处理审批" body="自动流程会尽量往前推，只有真正需要拍板时才会停下来。" />
        )}
      </Panel>
    </div>
  );
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

function discussionFromHistory(
  history: DiscussionHistory,
  gapId: string,
): GuideDiscussDirectionResponse | null {
  const assistant = [...history.messages]
    .reverse()
    .find((message) => message.role === "assistant" && message.metadata);
  if (!assistant?.metadata) {
    return null;
  }
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
      typeof metadata.research_question_suggestion === "string"
        ? metadata.research_question_suggestion
        : "",
    assistant_role: typeof metadata.assistant_role === "string" ? metadata.assistant_role : "Advisor",
    provider_name: typeof metadata.provider_name === "string" ? metadata.provider_name : "codex",
    model_name: typeof metadata.model_name === "string" ? metadata.model_name : "gpt-5.4",
    reasoning_effort:
      typeof metadata.reasoning_effort === "string" ? metadata.reasoning_effort : "high",
    skill_name:
      typeof metadata.skill_name === "string" ? metadata.skill_name : "research-direction-advisor",
  };
}
