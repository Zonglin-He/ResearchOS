import { useEffect, useMemo, useState } from "react";
import type {
  Claim,
  DiscussionSession,
  PaperCard,
  Project,
  ResultsFreeze,
  RunManifest,
  SpecFreeze,
  Task,
  TopicFreeze,
} from "../api";
import { EmptyState, Panel, StatusPill } from "./ui";

type Props = {
  selectedProject: Project | null;
  projectTasks: Task[];
  projectRuns: RunManifest[];
  claims: Claim[];
  paperCards: PaperCard[];
  topicFreeze: TopicFreeze | null;
  specFreeze: SpecFreeze | null;
  resultsFreeze: ResultsFreeze | null;
  discussions: DiscussionSession[];
  runAction: (key: string, callback: () => Promise<unknown>, refresh?: boolean) => Promise<void>;
  isBusy: (key: string) => boolean;
  createDiscussion: (payload: unknown) => Promise<DiscussionSession>;
  importDiscussion: (sessionId: string, payload: unknown) => Promise<DiscussionSession>;
  adoptDiscussion: (sessionId: string, payload: unknown) => Promise<DiscussionSession>;
  promoteDiscussionKb: (sessionId: string) => Promise<unknown>;
  promoteDiscussionApproval: (sessionId: string, payload: unknown) => Promise<unknown>;
  promoteDiscussionTask: (sessionId: string, payload: unknown) => Promise<unknown>;
};

type TargetOption = {
  value: string;
  kind: string;
  id: string;
  label: string;
  detail: string;
};

const BRANCH_OPTIONS = [
  "idea-branch",
  "method-branch",
  "baseline-branch",
  "negative-results-branch",
  "writing-branch",
] as const;

const SOURCE_OPTIONS = ["web_handoff", "cli_handoff", "internal_managed"] as const;
const IMPORT_SOURCE_OPTIONS = ["web", "cli", "internal"] as const;

export function DiscussTab(props: Props) {
  const [selectedSessionId, setSelectedSessionId] = useState("");
  const [targetValue, setTargetValue] = useState("");
  const [branchKind, setBranchKind] = useState<(typeof BRANCH_OPTIONS)[number]>("idea-branch");
  const [sourceType, setSourceType] = useState<(typeof SOURCE_OPTIONS)[number]>("web_handoff");
  const [sourceLabel, setSourceLabel] = useState("");
  const [title, setTitle] = useState("");
  const [focusQuestion, setFocusQuestion] = useState("");
  const [operatorPrompt, setOperatorPrompt] = useState("");
  const [selectedRefs, setSelectedRefs] = useState<string[]>([]);
  const [manualRefs, setManualRefs] = useState("");
  const [importSourceMode, setImportSourceMode] = useState<(typeof IMPORT_SOURCE_OPTIONS)[number]>("web");
  const [importProviderLabel, setImportProviderLabel] = useState("");
  const [importTranscriptTitle, setImportTranscriptTitle] = useState("");
  const [importText, setImportText] = useState("");

  const targetOptions = useMemo(() => buildTargetOptions(props), [props]);
  const selectedTarget = useMemo(
    () => targetOptions.find((option) => option.value === targetValue) ?? targetOptions[0] ?? null,
    [targetOptions, targetValue],
  );
  const selectedSession = useMemo(
    () => props.discussions.find((session) => session.session_id === selectedSessionId) ?? props.discussions[0] ?? null,
    [props.discussions, selectedSessionId],
  );

  useEffect(() => {
    if (!selectedTarget && targetOptions.length) {
      setTargetValue(targetOptions[0].value);
      setTitle(targetOptions[0].label);
      setFocusQuestion(`如何围绕 ${targetOptions[0].label} 做出下一步决策？`);
    }
  }, [selectedTarget, targetOptions]);

  useEffect(() => {
    if (!selectedSession && props.discussions.length) {
      setSelectedSessionId(props.discussions[0].session_id);
    }
  }, [props.discussions, selectedSession]);

  function toggleRef(value: string) {
    setSelectedRefs((current) => (current.includes(value) ? current.filter((item) => item !== value) : [...current, value]));
  }

  async function handleCreateSession() {
    if (!props.selectedProject || !selectedTarget) {
      return;
    }
    const attached = selectedRefs
      .map((value) => targetOptions.find((option) => option.value === value))
      .filter((option): option is TargetOption => option !== undefined && option.value !== selectedTarget.value)
      .map((option) => ({
        entity_type: option.kind,
        entity_id: option.id,
        label: option.label,
      }));
    const externalRefs = manualRefs
      .split(/[\n,]+/)
      .map((item) => item.trim())
      .filter(Boolean)
      .map((item) => {
        const [kind, ...rest] = item.split(":");
        if (!rest.length) {
          return { entity_type: "doi", entity_id: item, label: item };
        }
        return {
          entity_type: kind.trim() || "doi",
          entity_id: rest.join(":").trim(),
          label: rest.join(":").trim(),
        };
      });
    const sessionId = `discussion-${props.selectedProject.project_id}-${Date.now()}`;
    await props.runAction(`discussion-create-${sessionId}`, async () => {
      const session = await props.createDiscussion({
        session_id: sessionId,
        project_id: props.selectedProject?.project_id,
        title: title.trim() || selectedTarget.label,
        source_type: sourceType,
        source_label: sourceLabel,
        branch_kind: branchKind,
        target_kind: selectedTarget.kind,
        target_id: selectedTarget.id,
        target_label: selectedTarget.label,
        focus_question: focusQuestion,
        operator_prompt: operatorPrompt,
        questions_to_answer: focusQuestion.trim() ? [focusQuestion.trim()] : [],
        attached_entities: [...attached, ...externalRefs],
      });
      setSelectedSessionId(session.session_id);
      setImportText("");
      setImportTranscriptTitle("");
      setImportProviderLabel("");
      setManualRefs("");
    });
  }

  async function copyPacket() {
    if (!selectedSession?.context_bundle?.handoff_packet) {
      return;
    }
    await navigator.clipboard.writeText(selectedSession.context_bundle.handoff_packet);
  }

  async function handleImport() {
    if (!selectedSession || !importText.trim()) {
      return;
    }
    await props.runAction(`discussion-import-${selectedSession.session_id}`, () =>
      props.importDiscussion(selectedSession.session_id, {
        source_mode: importSourceMode,
        provider_label: importProviderLabel,
        transcript_title: importTranscriptTitle,
        verbatim_text: importText,
      }),
    );
  }

  async function handleAdopt() {
    if (!selectedSession) {
      return;
    }
    await props.runAction(`discussion-adopt-${selectedSession.session_id}`, () =>
      props.adoptDiscussion(selectedSession.session_id, {
        approved_by: "operator",
        adopted_summary: selectedSession.machine_distilled?.summary ?? "",
        route_to_kb: true,
      }),
    );
  }

  return (
    <div className="discuss-layout">
      <Panel title="Discuss Cockpit" subtitle="把讨论升级为可回流、可追踪、可转化的研究对象。">
        <div className="discuss-create-grid">
          <label>
            当前对象
            <select
              value={selectedTarget?.value ?? ""}
              onChange={(event) => {
                const next = targetOptions.find((option) => option.value === event.target.value);
                setTargetValue(event.target.value);
                if (next) {
                  setTitle(next.label);
                  setFocusQuestion(`如何围绕 ${next.label} 做出下一步决策？`);
                }
              }}
            >
              {targetOptions.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.detail}
                </option>
              ))}
            </select>
          </label>
          <label>
            分支
            <select value={branchKind} onChange={(event) => setBranchKind(event.target.value as (typeof BRANCH_OPTIONS)[number])}>
              {BRANCH_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label>
            Handoff 模式
            <select value={sourceType} onChange={(event) => setSourceType(event.target.value as (typeof SOURCE_OPTIONS)[number])}>
              {SOURCE_OPTIONS.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>
          <label>
            来源标签
            <input value={sourceLabel} onChange={(event) => setSourceLabel(event.target.value)} placeholder="例如 GPT-5 web / codex cli" />
          </label>
          <label>
            会话标题
            <input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="例如 讨论 run_003 的异常结果" />
          </label>
          <label>
            Focus Question
            <input value={focusQuestion} onChange={(event) => setFocusQuestion(event.target.value)} placeholder="希望外部 AI 回答什么" />
          </label>
          <label className="discuss-wide">
            Operator Prompt
            <textarea value={operatorPrompt} onChange={(event) => setOperatorPrompt(event.target.value)} placeholder="给外部 AI 的附加要求，例如重点质疑 baseline、公平性、算力约束。" />
          </label>
          <div className="discuss-wide">
            <strong>相关对象</strong>
            <div className="ref-picker">
              {targetOptions
                .filter((option) => option.value !== selectedTarget?.value)
                .slice(0, 12)
                .map((option) => (
                  <label key={option.value} className="ref-chip">
                    <input type="checkbox" checked={selectedRefs.includes(option.value)} onChange={() => toggleRef(option.value)} />
                    <span>{option.detail}</span>
                  </label>
                ))}
            </div>
          </div>
          <label className="discuss-wide">
            外部 DOI / Ref
            <textarea value={manualRefs} onChange={(event) => setManualRefs(event.target.value)} placeholder="支持直接写 DOI，或用 kind:id 形式，例如 doi:10.1000/test-doi, claim:claim-1" />
          </label>
          <div className="discuss-wide">
            <button className="button" type="button" onClick={() => void handleCreateSession()} disabled={!selectedTarget || props.isBusy("discussion-create")}>
              创建讨论会话
            </button>
          </div>
        </div>
      </Panel>

      <div className="discuss-main-grid">
        <Panel title="会话列表" subtitle="按最近更新时间排序。">
          {props.discussions.length ? (
            <div className="discussion-list">
              {props.discussions.map((session) => (
                <button
                  key={session.session_id}
                  className={selectedSession?.session_id === session.session_id ? "discussion-card active" : "discussion-card"}
                  type="button"
                  onClick={() => setSelectedSessionId(session.session_id)}
                >
                  <div className="discussion-card-head">
                    <strong>{session.title}</strong>
                    <StatusPill value={session.status} />
                  </div>
                  <small>{session.branch_kind}</small>
                  <p>{session.target_kind}:{session.target_id}</p>
                </button>
              ))}
            </div>
          ) : (
            <EmptyState title="还没有讨论会话" body="先从一个 freeze、run、claim、paper 或 task 建立会话。" />
          )}
        </Panel>

        <div className="discussion-detail-column">
          {selectedSession ? (
            <>
              <Panel
                title="当前对象与 Context Bundle"
                subtitle={`${selectedSession.target_kind}:${selectedSession.target_id} · ${selectedSession.source_type}`}
                action={
                  <button className="button secondary tiny" type="button" onClick={() => void copyPacket()} disabled={!selectedSession.context_bundle?.handoff_packet}>
                    复制 Context Packet
                  </button>
                }
              >
                <div className="record-grid">
                  <div className="record-card">
                    <strong>当前对象</strong>
                    <p>{selectedSession.target_label || selectedSession.target_id}</p>
                    <small>{selectedSession.focus_question || "未填写 focus question"}</small>
                  </div>
                  <div className="record-card">
                    <strong>争议点</strong>
                    <p>{selectedSession.context_bundle?.controversies.join("；") || "当前还没有自动抽出的争议点。"}</p>
                  </div>
                </div>
                <textarea readOnly value={selectedSession.context_bundle?.handoff_packet ?? ""} className="mono" />
              </Panel>

              <Panel title="回流外部 AI 结果" subtitle="粘贴 verbatim transcript，系统会生成 distilled summary 和 coverage。">
                <div className="discuss-import-grid">
                  <label>
                    来源
                    <select value={importSourceMode} onChange={(event) => setImportSourceMode(event.target.value as (typeof IMPORT_SOURCE_OPTIONS)[number])}>
                      {IMPORT_SOURCE_OPTIONS.map((option) => (
                        <option key={option} value={option}>
                          {option}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    Provider 标签
                    <input value={importProviderLabel} onChange={(event) => setImportProviderLabel(event.target.value)} placeholder="例如 gpt-5 web" />
                  </label>
                  <label className="discuss-wide">
                    Transcript 标题
                    <input value={importTranscriptTitle} onChange={(event) => setImportTranscriptTitle(event.target.value)} placeholder="例如 Web debate on spec freeze" />
                  </label>
                  <label className="discuss-wide">
                    Verbatim Import
                    <textarea value={importText} onChange={(event) => setImportText(event.target.value)} placeholder="把网页 AI 或 CLI AI 的讨论结果完整贴回这里。" />
                  </label>
                  <div className="discuss-wide">
                    <button className="button" type="button" onClick={() => void handleImport()} disabled={!importText.trim() || props.isBusy(`discussion-import-${selectedSession.session_id}`)}>
                      导入并蒸馏
                    </button>
                  </div>
                </div>
              </Panel>

              <Panel title="可信度分层" subtitle="verbatim import / machine distilled / adopted decision">
                <div className="discussion-layer-stack">
                  <article className="record-card">
                    <strong>Verbatim Import</strong>
                    <p>{selectedSession.latest_import?.transcript_title || selectedSession.latest_import?.provider_label || "尚未导入"}</p>
                    <small>{selectedSession.latest_import?.source_mode ?? ""}</small>
                  </article>
                  <article className="record-card">
                    <strong>Machine Distilled</strong>
                    <p>{selectedSession.machine_distilled?.summary || "尚未生成 distilled summary。"}</p>
                  </article>
                  <article className="record-card">
                    <strong>Adopted Decision</strong>
                    <p>{selectedSession.adopted_decision?.summary || "尚未 adopt 到正式决策层。"}</p>
                  </article>
                </div>
              </Panel>

              <Panel title="Coverage 与 Promote" subtitle="检查 DOI / claim 覆盖情况，并把讨论结果转成 KB、approval 或 task。">
                <div className="record-grid">
                  <div className="record-card">
                    <strong>Evidence Coverage</strong>
                    <p>{selectedSession.coverage_report?.summary || "还没有 coverage 报告。"}</p>
                    {selectedSession.coverage_report?.checks.length ? (
                      <ul className="flat-list">
                        {selectedSession.coverage_report.checks.map((check) => (
                          <li key={`${check.ref_type}-${check.ref}`}>
                            <span>{check.ref_type}:{check.ref}</span>
                            <StatusPill value={check.status} />
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </div>
                  <div className="record-card">
                    <strong>Distilled Actions</strong>
                    {selectedSession.machine_distilled?.suggested_next_actions.length ? (
                      <ul className="flat-list">
                        {selectedSession.machine_distilled.suggested_next_actions.map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p>当前还没有抽取到下一步动作。</p>
                    )}
                  </div>
                </div>
                <div className="button-row">
                  <button className="button tiny" type="button" onClick={() => void handleAdopt()} disabled={props.isBusy(`discussion-adopt-${selectedSession.session_id}`)}>
                    Adopt + 写入 KB
                  </button>
                  <button className="button tiny secondary" type="button" onClick={() => void props.runAction(`discussion-kb-${selectedSession.session_id}`, () => props.promoteDiscussionKb(selectedSession.session_id))}>
                    仅写入 KB
                  </button>
                  <button className="button tiny secondary" type="button" onClick={() => void props.runAction(`discussion-approval-${selectedSession.session_id}`, () => props.promoteDiscussionApproval(selectedSession.session_id, { approved_by: "operator" }))}>
                    生成审批
                  </button>
                  <button className="button tiny secondary" type="button" onClick={() => void props.runAction(`discussion-task-${selectedSession.session_id}`, () => props.promoteDiscussionTask(selectedSession.session_id, { owner: "operator" }))}>
                    生成任务
                  </button>
                </div>
              </Panel>
            </>
          ) : (
            <EmptyState title="请选择一个讨论会话" body="创建后即可复制 context packet、导入外部讨论，并把结果 promote 回系统。" />
          )}
        </div>
      </div>
    </div>
  );
}

function buildTargetOptions(props: Props): TargetOption[] {
  const project = props.selectedProject;
  if (!project) {
    return [];
  }
  const options: TargetOption[] = [
    {
      value: `project::${project.project_id}`,
      kind: "project",
      id: project.project_id,
      label: project.name,
      detail: `project · ${project.name}`,
    },
  ];
  if (props.topicFreeze) {
    options.push({
      value: `topic_freeze::${props.topicFreeze.topic_id}`,
      kind: "topic_freeze",
      id: props.topicFreeze.topic_id,
      label: props.topicFreeze.research_question,
      detail: `topic_freeze · ${props.topicFreeze.research_question}`,
    });
  }
  if (props.specFreeze) {
    options.push({
      value: `spec_freeze::${props.specFreeze.spec_id}`,
      kind: "spec_freeze",
      id: props.specFreeze.spec_id,
      label: props.specFreeze.spec_id,
      detail: `spec_freeze · ${props.specFreeze.spec_id}`,
    });
  }
  if (props.resultsFreeze) {
    options.push({
      value: `results_freeze::${props.resultsFreeze.results_id}`,
      kind: "results_freeze",
      id: props.resultsFreeze.results_id,
      label: props.resultsFreeze.results_id,
      detail: `results_freeze · ${props.resultsFreeze.results_id}`,
    });
  }
  for (const task of props.projectTasks.slice().sort((a, b) => b.created_at.localeCompare(a.created_at)).slice(0, 8)) {
    options.push({
      value: `task::${task.task_id}`,
      kind: "task",
      id: task.task_id,
      label: task.goal,
      detail: `task · ${task.kind} · ${task.goal}`,
    });
  }
  for (const run of props.projectRuns.slice(0, 6)) {
    options.push({
      value: `run::${run.run_id}`,
      kind: "run",
      id: run.run_id,
      label: run.run_id,
      detail: `run · ${run.run_id}`,
    });
  }
  for (const claim of props.claims.slice(0, 6)) {
    options.push({
      value: `claim::${claim.claim_id}`,
      kind: "claim",
      id: claim.claim_id,
      label: claim.text,
      detail: `claim · ${claim.claim_id}`,
    });
  }
  for (const paper of props.paperCards.slice(0, 6)) {
    options.push({
      value: `paper_card::${paper.paper_id}`,
      kind: "paper_card",
      id: paper.paper_id,
      label: paper.title,
      detail: `paper · ${paper.title}`,
    });
  }
  return options;
}
