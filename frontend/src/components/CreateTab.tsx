import { useEffect, useRef, useState } from "react";
import { FlaskConical, FolderPlus, Map, ShieldCheck, Sparkles } from "lucide-react";
import { parseEvidenceRefs, parseLines, parseOptionalJson, parseRequiredJson } from "../utils";
import { Panel } from "./ui";

export type TopicFreezePrefill = {
  projectId: string;
  sourceTaskId: string;
  topicId: string;
  researchQuestion: string;
  selectedGapIds: string[];
  noveltyType: string[];
};

type Props = {
  selectedProjectId: string;
  selectedProjectName: string;
  focusSection?: "project" | "topic_freeze" | null;
  topicFreezePrefill?: TopicFreezePrefill | null;
  runAction: (key: string, callback: () => Promise<unknown>, refresh?: boolean) => Promise<void>;
  createProject: (payload: unknown) => Promise<unknown>;
  createTask: (payload: unknown) => Promise<unknown>;
  createClaim: (payload: unknown) => Promise<unknown>;
  createRun: (payload: unknown) => Promise<unknown>;
  createPaperCard: (payload: unknown) => Promise<unknown>;
  createGapMap: (payload: unknown) => Promise<unknown>;
  createLesson: (payload: unknown) => Promise<unknown>;
  createApproval: (payload: unknown) => Promise<unknown>;
  saveTopicFreeze: (payload: unknown) => Promise<unknown>;
  saveSpecFreeze: (payload: unknown) => Promise<unknown>;
  saveResultsFreeze: (payload: unknown) => Promise<unknown>;
  setNotice: (value: string) => void;
};

export function CreateTab(props: Props) {
  const projectRef = useRef<HTMLDivElement | null>(null);
  const topicFreezeRef = useRef<HTMLDivElement | null>(null);

  const [projectForm, setProjectForm] = useState({
    project_id: props.selectedProjectId || "",
    name: props.selectedProjectName || "",
    description: "",
    status: "active",
    dispatch_profile_json: "",
  });
  const [taskForm, setTaskForm] = useState({
    task_id: "",
    project_id: props.selectedProjectId || "",
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
    status: "completed",
    metrics_json: "{}",
    artifacts: "",
    source_type: "internal",
    source_label: "",
    source_metadata_json: "{}",
    notes: "",
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
    project_id: props.selectedProjectId || "",
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
    supporting_run_ids: "",
    external_sources: "",
    notes: "",
    approved_by: "operator",
    status: "approved",
  });

  useEffect(() => {
    setProjectForm((current) => ({
      ...current,
      project_id: current.project_id || props.selectedProjectId,
      name: current.name || props.selectedProjectName,
    }));
    setTaskForm((current) => ({
      ...current,
      project_id: current.project_id || props.selectedProjectId,
    }));
    setApprovalForm((current) => ({
      ...current,
      project_id: current.project_id || props.selectedProjectId,
    }));
  }, [props.selectedProjectId, props.selectedProjectName]);

  useEffect(() => {
    if (!props.topicFreezePrefill) {
      return;
    }
    setTopicFreezeForm({
      topic_id: props.topicFreezePrefill.topicId,
      research_question: props.topicFreezePrefill.researchQuestion,
      selected_gap_ids: props.topicFreezePrefill.selectedGapIds.join("\n"),
      novelty_type: props.topicFreezePrefill.noveltyType.join("\n"),
      owner: "operator",
      status: "approved",
    });
  }, [props.topicFreezePrefill]);

  useEffect(() => {
    if (props.focusSection === "project") {
      projectRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
    if (props.focusSection === "topic_freeze") {
      topicFreezeRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [props.focusSection]);

  return (
    <div className="content-grid create-grid create-grid-compact">
      <Panel
        title="高级操作"
        subtitle="普通流程请优先走研究台。这里保留手动修正、补录、调试和紧急干预能力。"
      >
        <div className="workflow-strip">
          <WorkflowStep icon={FolderPlus} title="立项" body="手动创建项目或补一个空项目壳。" />
          <WorkflowStep icon={Map} title="证据" body="补录论文卡片和 Gap Map，修正证据层。" />
          <WorkflowStep icon={FlaskConical} title="实验" body="手动补 run、topic freeze、spec freeze。" />
          <WorkflowStep icon={ShieldCheck} title="收口" body="补 claim、lesson、approval 和 results freeze。" />
        </div>
      </Panel>

      <div ref={projectRef}>
        <Panel title="项目与任务" subtitle="只有在自动流程不适用时，才建议手动创建。">
          <div className="double-form">
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-project", async () => {
                await props.createProject({
                  project_id: projectForm.project_id,
                  name: projectForm.name,
                  description: projectForm.description,
                  status: projectForm.status,
                  dispatch_profile: parseOptionalJson(projectForm.dispatch_profile_json),
                });
                props.setNotice(`已创建项目 ${projectForm.project_id}`);
              });
            }}
          >
            <FormHint title="新建项目" body="只填项目 ID、名称和说明即可。其余字段主要用于覆盖系统默认行为。" />
            <InputPair label="Project id" value={projectForm.project_id} onChange={(value) => setProjectForm({ ...projectForm, project_id: value })} required />
            <InputPair label="项目名称" value={projectForm.name} onChange={(value) => setProjectForm({ ...projectForm, name: value })} required />
            <TextPair label="项目描述" value={projectForm.description} onChange={(value) => setProjectForm({ ...projectForm, description: value })} required span />
            <InputPair label="状态" value={projectForm.status} onChange={(value) => setProjectForm({ ...projectForm, status: value })} />
            <TextPair label="Dispatch profile JSON" value={projectForm.dispatch_profile_json} onChange={(value) => setProjectForm({ ...projectForm, dispatch_profile_json: value })} span />
            <button className="button" type="submit">
              创建项目
            </button>
          </form>

          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-task", async () => {
                await props.createTask({
                  task_id: taskForm.task_id,
                  project_id: taskForm.project_id,
                  kind: taskForm.kind,
                  goal: taskForm.goal,
                  owner: taskForm.owner,
                  assigned_agent: taskForm.assigned_agent || null,
                  parent_task_id: taskForm.parent_task_id || null,
                  input_payload: parseRequiredJson(taskForm.input_payload_json),
                  dispatch_profile: parseOptionalJson(taskForm.dispatch_profile_json),
                });
                props.setNotice(`已创建任务 ${taskForm.task_id}`);
              });
            }}
          >
            <FormHint title="手动建任务" body="如果自动流程断了，在这里补任务。优先填目标和输入，ID 用你自己可读的命名。" />
            <InputPair label="Task id" value={taskForm.task_id} onChange={(value) => setTaskForm({ ...taskForm, task_id: value })} required />
            <InputPair label="Project id" value={taskForm.project_id} onChange={(value) => setTaskForm({ ...taskForm, project_id: value })} required />
            <InputPair label="任务类型" value={taskForm.kind} onChange={(value) => setTaskForm({ ...taskForm, kind: value })} required />
            <InputPair label="负责人" value={taskForm.owner} onChange={(value) => setTaskForm({ ...taskForm, owner: value })} required />
            <TextPair label="目标" value={taskForm.goal} onChange={(value) => setTaskForm({ ...taskForm, goal: value })} required span />
            <InputPair label="指定 agent" value={taskForm.assigned_agent} onChange={(value) => setTaskForm({ ...taskForm, assigned_agent: value })} />
            <InputPair label="父任务 id" value={taskForm.parent_task_id} onChange={(value) => setTaskForm({ ...taskForm, parent_task_id: value })} />
            <TextPair label="输入负载 JSON" value={taskForm.input_payload_json} onChange={(value) => setTaskForm({ ...taskForm, input_payload_json: value })} required span />
            <TextPair label="Dispatch profile JSON" value={taskForm.dispatch_profile_json} onChange={(value) => setTaskForm({ ...taskForm, dispatch_profile_json: value })} span />
            <button className="button" type="submit">
              创建任务
            </button>
          </form>
          </div>
        </Panel>
      </div>

      <Panel title="研究登记" subtitle="补录 paper card、gap map、lesson 等结构化对象。">
        <div className="double-form">
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-paper-card", async () => {
                await props.createPaperCard({
                  paper_id: paperCardForm.paper_id,
                  title: paperCardForm.title,
                  problem: paperCardForm.problem,
                  setting: paperCardForm.setting,
                  task_type: paperCardForm.task_type,
                  strongest_result: paperCardForm.strongest_result,
                  method_summary: paperCardForm.method_summary,
                  evidence_refs: parseEvidenceRefs(paperCardForm.evidence_refs),
                });
                props.setNotice(`已创建 paper card ${paperCardForm.paper_id}`);
              });
            }}
          >
            <FormHint title="Paper card" body="用于补录论文问题、方法和 strongest result，优先保证可检索和可追溯。" />
            <InputPair label="Paper id" value={paperCardForm.paper_id} onChange={(value) => setPaperCardForm({ ...paperCardForm, paper_id: value })} required />
            <InputPair label="标题" value={paperCardForm.title} onChange={(value) => setPaperCardForm({ ...paperCardForm, title: value })} required />
            <InputPair label="任务类型" value={paperCardForm.task_type} onChange={(value) => setPaperCardForm({ ...paperCardForm, task_type: value })} required />
            <InputPair label="研究场景" value={paperCardForm.setting} onChange={(value) => setPaperCardForm({ ...paperCardForm, setting: value })} required />
            <TextPair label="问题定义" value={paperCardForm.problem} onChange={(value) => setPaperCardForm({ ...paperCardForm, problem: value })} required span />
            <TextPair label="方法摘要" value={paperCardForm.method_summary} onChange={(value) => setPaperCardForm({ ...paperCardForm, method_summary: value })} span />
            <TextPair label="最强结果" value={paperCardForm.strongest_result} onChange={(value) => setPaperCardForm({ ...paperCardForm, strongest_result: value })} span />
            <InputPair label="证据引用" value={paperCardForm.evidence_refs} onChange={(value) => setPaperCardForm({ ...paperCardForm, evidence_refs: value })} span />
            <button className="button" type="submit">
              保存 paper card
            </button>
          </form>

          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-gap-map", async () => {
                await props.createGapMap({
                  topic: gapMapForm.topic,
                  clusters: [
                    {
                      name: gapMapForm.cluster_name,
                      gaps: [
                        {
                          gap_id: gapMapForm.gap_id,
                          description: gapMapForm.description,
                          supporting_papers: parseLines(gapMapForm.supporting_papers),
                          attack_surface: gapMapForm.attack_surface,
                          difficulty: gapMapForm.difficulty,
                          novelty_type: gapMapForm.novelty_type,
                        },
                      ],
                    },
                  ],
                });
                props.setNotice(`已创建 gap map ${gapMapForm.topic}`);
              });
            }}
          >
            <FormHint title="Gap map" body="支持快速补一条 Gap 记录，先让方向可见，再慢慢扩充 cluster。" />
            <InputPair label="主题" value={gapMapForm.topic} onChange={(value) => setGapMapForm({ ...gapMapForm, topic: value })} required />
            <InputPair label="Cluster 名称" value={gapMapForm.cluster_name} onChange={(value) => setGapMapForm({ ...gapMapForm, cluster_name: value })} required />
            <InputPair label="Gap id" value={gapMapForm.gap_id} onChange={(value) => setGapMapForm({ ...gapMapForm, gap_id: value })} required />
            <InputPair label="难度" value={gapMapForm.difficulty} onChange={(value) => setGapMapForm({ ...gapMapForm, difficulty: value })} />
            <InputPair label="新颖性类型" value={gapMapForm.novelty_type} onChange={(value) => setGapMapForm({ ...gapMapForm, novelty_type: value })} />
            <InputPair label="攻击面" value={gapMapForm.attack_surface} onChange={(value) => setGapMapForm({ ...gapMapForm, attack_surface: value })} />
            <TextPair label="描述" value={gapMapForm.description} onChange={(value) => setGapMapForm({ ...gapMapForm, description: value })} required span />
            <TextPair label="支持论文" value={gapMapForm.supporting_papers} onChange={(value) => setGapMapForm({ ...gapMapForm, supporting_papers: value })} span />
            <button className="button" type="submit">
              保存 gap map
            </button>
          </form>

          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-lesson", async () => {
                await props.createLesson({
                  ...lessonForm,
                  task_kind: lessonForm.task_kind || null,
                  agent_name: lessonForm.agent_name || null,
                  provider_name: lessonForm.provider_name || null,
                  model_name: lessonForm.model_name || null,
                  source_task_id: lessonForm.source_task_id || null,
                  source_run_id: lessonForm.source_run_id || null,
                  source_claim_id: lessonForm.source_claim_id || null,
                  context_tags: parseLines(lessonForm.context_tags),
                  evidence_refs: parseLines(lessonForm.evidence_refs),
                  artifact_ids: parseLines(lessonForm.artifact_ids),
                });
                props.setNotice(`已创建 lesson ${lessonForm.lesson_id}`);
              });
            }}
          >
            <FormHint title="Lesson" body="记录这次流程的经验和返工原因。用在下游 agent 复用时，比日志更有价值。" />
            <InputPair label="Lesson id" value={lessonForm.lesson_id} onChange={(value) => setLessonForm({ ...lessonForm, lesson_id: value })} required />
            <InputPair label="类型" value={lessonForm.lesson_kind} onChange={(value) => setLessonForm({ ...lessonForm, lesson_kind: value })} required />
            <InputPair label="标题" value={lessonForm.title} onChange={(value) => setLessonForm({ ...lessonForm, title: value })} required />
            <InputPair label="任务类型" value={lessonForm.task_kind} onChange={(value) => setLessonForm({ ...lessonForm, task_kind: value })} />
            <TextPair label="摘要" value={lessonForm.summary} onChange={(value) => setLessonForm({ ...lessonForm, summary: value })} required span />
            <TextPair label="原因" value={lessonForm.rationale} onChange={(value) => setLessonForm({ ...lessonForm, rationale: value })} span />
            <TextPair label="建议动作" value={lessonForm.recommended_action} onChange={(value) => setLessonForm({ ...lessonForm, recommended_action: value })} span />
            <InputPair label="Agent name" value={lessonForm.agent_name} onChange={(value) => setLessonForm({ ...lessonForm, agent_name: value })} />
            <TextPair label="上下文标签" value={lessonForm.context_tags} onChange={(value) => setLessonForm({ ...lessonForm, context_tags: value })} span />
            <button className="button" type="submit">
              保存 lesson
            </button>
          </form>
        </div>
      </Panel>

      <div ref={topicFreezeRef}>
        <Panel title="冻结、实验与审批" subtitle="这里处理 topic freeze、spec freeze、run、claim、approval 和 results freeze。">
          <div className="triple-form">
          <form
            className={props.focusSection === "topic_freeze" ? "form-grid focus-ring" : "form-grid"}
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("save-topic-freeze", async () => {
                await props.saveTopicFreeze({
                  topic_id: topicFreezeForm.topic_id,
                  research_question: topicFreezeForm.research_question,
                  selected_gap_ids: parseLines(topicFreezeForm.selected_gap_ids),
                  novelty_type: parseLines(topicFreezeForm.novelty_type),
                  owner: topicFreezeForm.owner,
                  status: topicFreezeForm.status,
                });
                props.setNotice(`已保存 topic freeze ${topicFreezeForm.topic_id}`);
              });
            }}
          >
            <FormHint title="Topic freeze" body="这是人工拍板后的入口。系统自动流程也会在这里接棒。" />
            <InputPair label="Topic id" value={topicFreezeForm.topic_id} onChange={(value) => setTopicFreezeForm({ ...topicFreezeForm, topic_id: value })} required />
            <TextPair label="研究问题" value={topicFreezeForm.research_question} onChange={(value) => setTopicFreezeForm({ ...topicFreezeForm, research_question: value })} required span />
            <TextPair label="选中 gap ids" value={topicFreezeForm.selected_gap_ids} onChange={(value) => setTopicFreezeForm({ ...topicFreezeForm, selected_gap_ids: value })} span />
            <TextPair label="新颖性类型" value={topicFreezeForm.novelty_type} onChange={(value) => setTopicFreezeForm({ ...topicFreezeForm, novelty_type: value })} span />
            <button className="button" type="submit">
              保存 topic freeze
            </button>
          </form>

          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("save-spec-freeze", async () => {
                await props.saveSpecFreeze({
                  spec_id: specFreezeForm.spec_id,
                  topic_id: specFreezeForm.topic_id,
                  hypothesis: parseLines(specFreezeForm.hypothesis),
                  must_beat_baselines: parseLines(specFreezeForm.must_beat_baselines),
                  datasets: parseLines(specFreezeForm.datasets),
                  metrics: parseLines(specFreezeForm.metrics),
                  fairness_constraints: parseLines(specFreezeForm.fairness_constraints),
                  ablations: parseLines(specFreezeForm.ablations),
                  success_criteria: parseLines(specFreezeForm.success_criteria),
                  failure_criteria: parseLines(specFreezeForm.failure_criteria),
                  approved_by: specFreezeForm.approved_by,
                  status: specFreezeForm.status,
                });
                props.setNotice(`已保存 spec freeze ${specFreezeForm.spec_id}`);
              });
            }}
          >
            <FormHint title="Spec freeze" body="在正式开跑前把 baseline、数据集、指标和成功标准钉住。" />
            <InputPair label="Spec id" value={specFreezeForm.spec_id} onChange={(value) => setSpecFreezeForm({ ...specFreezeForm, spec_id: value })} required />
            <InputPair label="Topic id" value={specFreezeForm.topic_id} onChange={(value) => setSpecFreezeForm({ ...specFreezeForm, topic_id: value })} required />
            <TextPair label="假设" value={specFreezeForm.hypothesis} onChange={(value) => setSpecFreezeForm({ ...specFreezeForm, hypothesis: value })} span />
            <TextPair label="必须超越的 baseline" value={specFreezeForm.must_beat_baselines} onChange={(value) => setSpecFreezeForm({ ...specFreezeForm, must_beat_baselines: value })} span />
            <TextPair label="数据集" value={specFreezeForm.datasets} onChange={(value) => setSpecFreezeForm({ ...specFreezeForm, datasets: value })} span />
            <TextPair label="指标" value={specFreezeForm.metrics} onChange={(value) => setSpecFreezeForm({ ...specFreezeForm, metrics: value })} span />
            <button className="button" type="submit">
              保存 spec freeze
            </button>
          </form>

          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-run", async () => {
                await props.createRun({
                  ...runForm,
                  seed: Number(runForm.seed),
                  status: runForm.status,
                  metrics: parseOptionalJson(runForm.metrics_json) ?? {},
                  artifacts: parseLines(runForm.artifacts),
                  source_type: runForm.source_type,
                  source_label: runForm.source_label || null,
                  source_metadata: parseOptionalJson(runForm.source_metadata_json) ?? {},
                  notes: parseLines(runForm.notes),
                });
                props.setNotice(`已创建 run ${runForm.run_id}`);
              });
            }}
          >
            <FormHint title="Run / Claim / 审批" body="适合紧急补 run、补 claim 或手动登记人工审批。">
            </FormHint>
            <InputPair label="Run id" value={runForm.run_id} onChange={(value) => setRunForm({ ...runForm, run_id: value })} required />
            <InputPair label="Spec id" value={runForm.spec_id} onChange={(value) => setRunForm({ ...runForm, spec_id: value })} required />
            <InputPair label="Git commit" value={runForm.git_commit} onChange={(value) => setRunForm({ ...runForm, git_commit: value })} required />
            <InputPair label="配置哈希" value={runForm.config_hash} onChange={(value) => setRunForm({ ...runForm, config_hash: value })} required />
            <InputPair label="数据快照" value={runForm.dataset_snapshot} onChange={(value) => setRunForm({ ...runForm, dataset_snapshot: value })} required />
            <InputPair label="Seed" value={runForm.seed} onChange={(value) => setRunForm({ ...runForm, seed: value })} required />
            <InputPair label="GPU" value={runForm.gpu} onChange={(value) => setRunForm({ ...runForm, gpu: value })} required />
            <InputPair label="Run status" value={runForm.status} onChange={(value) => setRunForm({ ...runForm, status: value })} />
            <InputPair label="Source type" value={runForm.source_type} onChange={(value) => setRunForm({ ...runForm, source_type: value })} />
            <InputPair label="Source label" value={runForm.source_label} onChange={(value) => setRunForm({ ...runForm, source_label: value })} />
            <TextPair label="Metrics JSON" value={runForm.metrics_json} onChange={(value) => setRunForm({ ...runForm, metrics_json: value })} span />
            <TextPair label="Artifact ids" value={runForm.artifacts} onChange={(value) => setRunForm({ ...runForm, artifacts: value })} span />
            <TextPair label="Source metadata JSON" value={runForm.source_metadata_json} onChange={(value) => setRunForm({ ...runForm, source_metadata_json: value })} span />
            <TextPair label="Run notes" value={runForm.notes} onChange={(value) => setRunForm({ ...runForm, notes: value })} span />
            <button className="button" type="submit">
              创建 run
            </button>
          </form>
          </div>

          <div className="double-form">
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-claim", async () => {
                await props.createClaim(claimForm);
                props.setNotice(`已创建 claim ${claimForm.claim_id}`);
              });
            }}
          >
            <FormHint title="Claim" body="在 run 已经形成结论后，再把结论结构化成 claim。" />
            <InputPair label="Claim id" value={claimForm.claim_id} onChange={(value) => setClaimForm({ ...claimForm, claim_id: value })} required />
            <InputPair label="Claim 类型" value={claimForm.claim_type} onChange={(value) => setClaimForm({ ...claimForm, claim_type: value })} required />
            <InputPair label="风险级别" value={claimForm.risk_level} onChange={(value) => setClaimForm({ ...claimForm, risk_level: value })} />
            <label className="checkbox-row span-2">
              <input
                type="checkbox"
                checked={claimForm.approved_by_human}
                onChange={(event) => setClaimForm({ ...claimForm, approved_by_human: event.target.checked })}
              />
              已人工批准
            </label>
            <TextPair label="Claim 文本" value={claimForm.text} onChange={(value) => setClaimForm({ ...claimForm, text: value })} required span />
            <button className="button" type="submit">
              保存 claim
            </button>
          </form>

          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("save-results-freeze", async () => {
                await props.saveResultsFreeze({
                  results_id: resultsFreezeForm.results_id,
                  spec_id: resultsFreezeForm.spec_id,
                  main_claims: parseLines(resultsFreezeForm.main_claims),
                  tables: parseLines(resultsFreezeForm.tables),
                  figures: parseLines(resultsFreezeForm.figures),
                  supporting_run_ids: parseLines(resultsFreezeForm.supporting_run_ids),
                  external_sources: parseLines(resultsFreezeForm.external_sources),
                  notes: parseLines(resultsFreezeForm.notes),
                  approved_by: resultsFreezeForm.approved_by,
                  status: resultsFreezeForm.status,
                });
                props.setNotice(`已保存 results freeze ${resultsFreezeForm.results_id}`);
              });
            }}
          >
            <FormHint title="Results freeze" body="当表格和主结论稳定下来后，把版本钉住，后续写作才不乱。" />
            <InputPair label="Results id" value={resultsFreezeForm.results_id} onChange={(value) => setResultsFreezeForm({ ...resultsFreezeForm, results_id: value })} required />
            <InputPair label="Spec id" value={resultsFreezeForm.spec_id} onChange={(value) => setResultsFreezeForm({ ...resultsFreezeForm, spec_id: value })} required />
            <TextPair label="Supporting run ids" value={resultsFreezeForm.supporting_run_ids} onChange={(value) => setResultsFreezeForm({ ...resultsFreezeForm, supporting_run_ids: value })} span />
            <TextPair label="External sources" value={resultsFreezeForm.external_sources} onChange={(value) => setResultsFreezeForm({ ...resultsFreezeForm, external_sources: value })} span />
            <TextPair label="Results notes" value={resultsFreezeForm.notes} onChange={(value) => setResultsFreezeForm({ ...resultsFreezeForm, notes: value })} span />
            <TextPair label="主 claims" value={resultsFreezeForm.main_claims} onChange={(value) => setResultsFreezeForm({ ...resultsFreezeForm, main_claims: value })} span />
            <TextPair label="表格" value={resultsFreezeForm.tables} onChange={(value) => setResultsFreezeForm({ ...resultsFreezeForm, tables: value })} span />
            <TextPair label="图" value={resultsFreezeForm.figures} onChange={(value) => setResultsFreezeForm({ ...resultsFreezeForm, figures: value })} span />
            <button className="button" type="submit">
              保存 results freeze
            </button>
          </form>

          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-approval", async () => {
                await props.createApproval(approvalForm);
                props.setNotice(`已记录审批 ${approvalForm.approval_id}`);
              });
            }}
          >
            <FormHint title="Approval" body="高风险 claim、freeze 或人工拍板都可以在这里补登记。" />
            <InputPair label="Approval id" value={approvalForm.approval_id} onChange={(value) => setApprovalForm({ ...approvalForm, approval_id: value })} required />
            <InputPair label="Project id" value={approvalForm.project_id} onChange={(value) => setApprovalForm({ ...approvalForm, project_id: value })} required />
            <InputPair label="目标类型" value={approvalForm.target_type} onChange={(value) => setApprovalForm({ ...approvalForm, target_type: value })} required />
            <InputPair label="目标 id" value={approvalForm.target_id} onChange={(value) => setApprovalForm({ ...approvalForm, target_id: value })} required />
            <InputPair label="批准人" value={approvalForm.approved_by} onChange={(value) => setApprovalForm({ ...approvalForm, approved_by: value })} required />
            <InputPair label="决定" value={approvalForm.decision} onChange={(value) => setApprovalForm({ ...approvalForm, decision: value })} required />
            <TextPair label="备注" value={approvalForm.comment} onChange={(value) => setApprovalForm({ ...approvalForm, comment: value })} span />
            <button className="button" type="submit">
              记录审批
            </button>
          </form>
          </div>
        </Panel>
      </div>
    </div>
  );
}

function WorkflowStep(props: { icon: typeof Sparkles; title: string; body: string }) {
  const Icon = props.icon;
  return (
    <div className="workflow-step">
      <div className="workflow-icon">
        <Icon size={16} />
      </div>
      <strong>{props.title}</strong>
      <p>{props.body}</p>
    </div>
  );
}

function FormHint(props: { title: string; body: string }) {
  return (
    <div className="form-hint span-2">
      <strong>{props.title}</strong>
      <p>{props.body}</p>
    </div>
  );
}

function InputPair(props: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  span?: boolean;
}) {
  return (
    <label className={props.span ? "span-2" : undefined}>
      {props.label}
      <input value={props.value} onChange={(event) => props.onChange(event.target.value)} required={props.required} />
    </label>
  );
}

function TextPair(props: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  required?: boolean;
  span?: boolean;
}) {
  return (
    <label className={props.span ? "span-2" : undefined}>
      {props.label}
      <textarea value={props.value} onChange={(event) => props.onChange(event.target.value)} required={props.required} />
    </label>
  );
}
