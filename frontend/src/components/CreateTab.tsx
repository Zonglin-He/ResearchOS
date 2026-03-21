import { useEffect, useRef } from "react";
import { FlaskConical, FolderPlus, Map, ShieldCheck, Sparkles } from "lucide-react";
import { parseEvidenceRefs, parseLines, parseOptionalJson, parseRequiredJson } from "../utils";
import { Panel } from "./ui";

type Props = {
  projectForm: any;
  setProjectForm: (value: any) => void;
  taskForm: any;
  setTaskForm: (value: any) => void;
  claimForm: any;
  setClaimForm: (value: any) => void;
  runForm: any;
  setRunForm: (value: any) => void;
  paperCardForm: any;
  setPaperCardForm: (value: any) => void;
  gapMapForm: any;
  setGapMapForm: (value: any) => void;
  lessonForm: any;
  setLessonForm: (value: any) => void;
  approvalForm: any;
  setApprovalForm: (value: any) => void;
  topicFreezeForm: any;
  setTopicFreezeForm: (value: any) => void;
  specFreezeForm: any;
  setSpecFreezeForm: (value: any) => void;
  resultsFreezeForm: any;
  setResultsFreezeForm: (value: any) => void;
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
  focusSection?: "topic_freeze" | null;
};

export function CreateTab(props: Props) {
  const topicFreezeRef = useRef<HTMLFormElement | null>(null);

  useEffect(() => {
    if (props.focusSection === "topic_freeze") {
      topicFreezeRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [props.focusSection]);

  return (
    <div className="content-grid create-grid">
      <Panel title="研究工作流" subtitle="把原本分散的对象创建，整理成更接近实际使用顺序的四段流程。">
        <div className="workflow-strip">
          <WorkflowStep icon={FolderPlus} title="1. 立项" body="先建项目，再创建首批 task，让工作室有可调度内容。" />
          <WorkflowStep icon={Map} title="2. 证据" body="paper card 与 gap map 决定研究问题是否清楚。" />
          <WorkflowStep icon={FlaskConical} title="3. 实验" body="冻结 topic/spec 后再开 run，返工最少。" />
          <WorkflowStep icon={ShieldCheck} title="4. 评审" body="claim、lesson、approval 与 results freeze 收口。" />
        </div>
      </Panel>

      <Panel title="1. 立项与任务" subtitle="对应 create-project 与 create-task。">
        <div className="double-form">
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-project", async () => {
                await props.createProject({
                  project_id: props.projectForm.project_id,
                  name: props.projectForm.name,
                  description: props.projectForm.description,
                  status: props.projectForm.status,
                  dispatch_profile: parseOptionalJson(props.projectForm.dispatch_profile_json),
                });
                props.setNotice(`已创建项目 ${props.projectForm.project_id}`);
              });
            }}
          >
            <FormHint title="创建项目" body="建议先填 project_id、名称和简短描述。dispatch profile 留空即可，除非你确实要覆盖默认路由。" />
            <InputPair label="Project id" value={props.projectForm.project_id} onChange={(value) => props.setProjectForm({ ...props.projectForm, project_id: value })} required />
            <InputPair label="项目名称" value={props.projectForm.name} onChange={(value) => props.setProjectForm({ ...props.projectForm, name: value })} required />
            <TextPair label="项目描述" value={props.projectForm.description} onChange={(value) => props.setProjectForm({ ...props.projectForm, description: value })} required span />
            <InputPair label="状态" value={props.projectForm.status} onChange={(value) => props.setProjectForm({ ...props.projectForm, status: value })} />
            <TextPair label="Dispatch profile JSON" value={props.projectForm.dispatch_profile_json} onChange={(value) => props.setProjectForm({ ...props.projectForm, dispatch_profile_json: value })} span />
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
                  task_id: props.taskForm.task_id,
                  project_id: props.taskForm.project_id,
                  kind: props.taskForm.kind,
                  goal: props.taskForm.goal,
                  owner: props.taskForm.owner,
                  assigned_agent: props.taskForm.assigned_agent || null,
                  parent_task_id: props.taskForm.parent_task_id || null,
                  input_payload: parseRequiredJson(props.taskForm.input_payload_json),
                  dispatch_profile: parseOptionalJson(props.taskForm.dispatch_profile_json),
                });
                props.setNotice(`已创建任务 ${props.taskForm.task_id}`);
              });
            }}
          >
            <FormHint title="创建任务" body="推荐先建 paper_ingest、gap_map_build 或 experiment_spec 这三类起步任务。" />
            <InputPair label="Task id" value={props.taskForm.task_id} onChange={(value) => props.setTaskForm({ ...props.taskForm, task_id: value })} required />
            <InputPair label="Project id" value={props.taskForm.project_id} onChange={(value) => props.setTaskForm({ ...props.taskForm, project_id: value })} required />
            <InputPair label="任务类型" value={props.taskForm.kind} onChange={(value) => props.setTaskForm({ ...props.taskForm, kind: value })} required />
            <InputPair label="负责人" value={props.taskForm.owner} onChange={(value) => props.setTaskForm({ ...props.taskForm, owner: value })} required />
            <TextPair label="目标" value={props.taskForm.goal} onChange={(value) => props.setTaskForm({ ...props.taskForm, goal: value })} required span />
            <InputPair label="指定 agent" value={props.taskForm.assigned_agent} onChange={(value) => props.setTaskForm({ ...props.taskForm, assigned_agent: value })} />
            <InputPair label="父任务 id" value={props.taskForm.parent_task_id} onChange={(value) => props.setTaskForm({ ...props.taskForm, parent_task_id: value })} />
            <TextPair label="输入负载 JSON" value={props.taskForm.input_payload_json} onChange={(value) => props.setTaskForm({ ...props.taskForm, input_payload_json: value })} required span />
            <TextPair label="Dispatch profile JSON" value={props.taskForm.dispatch_profile_json} onChange={(value) => props.setTaskForm({ ...props.taskForm, dispatch_profile_json: value })} span />
            <button className="button" type="submit">
              创建任务
            </button>
          </form>
        </div>
      </Panel>

      <Panel title="2. 证据整理" subtitle="先把资料层建起来，综合台和实验台才会顺。">
        <div className="double-form">
          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-paper-card", async () => {
                await props.createPaperCard({
                  paper_id: props.paperCardForm.paper_id,
                  title: props.paperCardForm.title,
                  problem: props.paperCardForm.problem,
                  setting: props.paperCardForm.setting,
                  task_type: props.paperCardForm.task_type,
                  strongest_result: props.paperCardForm.strongest_result,
                  method_summary: props.paperCardForm.method_summary,
                  evidence_refs: parseEvidenceRefs(props.paperCardForm.evidence_refs),
                });
                props.setNotice(`已创建 paper card ${props.paperCardForm.paper_id}`);
              });
            }}
          >
            <FormHint title="Paper card" body="适合快速固化论文问题、方法和 strongest result。写不全也没关系，先让证据可查。" />
            <InputPair label="Paper id" value={props.paperCardForm.paper_id} onChange={(value) => props.setPaperCardForm({ ...props.paperCardForm, paper_id: value })} required />
            <InputPair label="标题" value={props.paperCardForm.title} onChange={(value) => props.setPaperCardForm({ ...props.paperCardForm, title: value })} required />
            <InputPair label="任务类型" value={props.paperCardForm.task_type} onChange={(value) => props.setPaperCardForm({ ...props.paperCardForm, task_type: value })} required />
            <InputPair label="场景" value={props.paperCardForm.setting} onChange={(value) => props.setPaperCardForm({ ...props.paperCardForm, setting: value })} required />
            <TextPair label="问题定义" value={props.paperCardForm.problem} onChange={(value) => props.setPaperCardForm({ ...props.paperCardForm, problem: value })} required span />
            <TextPair label="方法摘要" value={props.paperCardForm.method_summary} onChange={(value) => props.setPaperCardForm({ ...props.paperCardForm, method_summary: value })} span />
            <TextPair label="最强结果" value={props.paperCardForm.strongest_result} onChange={(value) => props.setPaperCardForm({ ...props.paperCardForm, strongest_result: value })} span />
            <InputPair label="证据引用" value={props.paperCardForm.evidence_refs} onChange={(value) => props.setPaperCardForm({ ...props.paperCardForm, evidence_refs: value })} span />
            <button className="button" type="submit">
              创建 paper card
            </button>
          </form>

          <form
            className="form-grid"
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("create-gap-map", async () => {
                await props.createGapMap({
                  topic: props.gapMapForm.topic,
                  clusters: [
                    {
                      name: props.gapMapForm.cluster_name,
                      gaps: [
                        {
                          gap_id: props.gapMapForm.gap_id,
                          description: props.gapMapForm.description,
                          supporting_papers: parseLines(props.gapMapForm.supporting_papers),
                          attack_surface: props.gapMapForm.attack_surface,
                          difficulty: props.gapMapForm.difficulty,
                          novelty_type: props.gapMapForm.novelty_type,
                        },
                      ],
                    },
                  ],
                });
                props.setNotice(`已创建 gap map ${props.gapMapForm.topic}`);
              });
            }}
          >
            <FormHint title="Gap map" body="一个主题先写一个 cluster 就够了，后续可继续扩展，不必等结构完美再录入。" />
            <InputPair label="主题" value={props.gapMapForm.topic} onChange={(value) => props.setGapMapForm({ ...props.gapMapForm, topic: value })} required />
            <InputPair label="聚类名" value={props.gapMapForm.cluster_name} onChange={(value) => props.setGapMapForm({ ...props.gapMapForm, cluster_name: value })} required />
            <InputPair label="Gap id" value={props.gapMapForm.gap_id} onChange={(value) => props.setGapMapForm({ ...props.gapMapForm, gap_id: value })} required />
            <InputPair label="难度" value={props.gapMapForm.difficulty} onChange={(value) => props.setGapMapForm({ ...props.gapMapForm, difficulty: value })} />
            <InputPair label="新颖性类型" value={props.gapMapForm.novelty_type} onChange={(value) => props.setGapMapForm({ ...props.gapMapForm, novelty_type: value })} />
            <InputPair label="攻击面" value={props.gapMapForm.attack_surface} onChange={(value) => props.setGapMapForm({ ...props.gapMapForm, attack_surface: value })} />
            <TextPair label="描述" value={props.gapMapForm.description} onChange={(value) => props.setGapMapForm({ ...props.gapMapForm, description: value })} required span />
            <TextPair label="支持论文" value={props.gapMapForm.supporting_papers} onChange={(value) => props.setGapMapForm({ ...props.gapMapForm, supporting_papers: value })} span />
            <button className="button" type="submit">
              创建 gap map
            </button>
          </form>
        </div>
      </Panel>

      <Panel title="3. 实验与冻结" subtitle="从 hypothesis 到 run，再到 freeze，建议按这个顺序推进。">
        <div className="triple-form">
          <form
            ref={topicFreezeRef}
            className={props.focusSection === "topic_freeze" ? "form-grid focus-ring" : "form-grid"}
            onSubmit={(event) => {
              event.preventDefault();
              void props.runAction("save-topic-freeze", async () => {
                await props.saveTopicFreeze({
                  topic_id: props.topicFreezeForm.topic_id,
                  research_question: props.topicFreezeForm.research_question,
                  selected_gap_ids: parseLines(props.topicFreezeForm.selected_gap_ids),
                  novelty_type: parseLines(props.topicFreezeForm.novelty_type),
                  owner: props.topicFreezeForm.owner,
                  status: props.topicFreezeForm.status,
                });
                props.setNotice(`已保存 topic freeze ${props.topicFreezeForm.topic_id}`);
              });
            }}
          >
            <FormHint title="主题冻结" body="决定研究问题、锁定 gap，后续 task 会更清楚。" />
            <InputPair label="Topic id" value={props.topicFreezeForm.topic_id} onChange={(value) => props.setTopicFreezeForm({ ...props.topicFreezeForm, topic_id: value })} required />
            <TextPair label="研究问题" value={props.topicFreezeForm.research_question} onChange={(value) => props.setTopicFreezeForm({ ...props.topicFreezeForm, research_question: value })} required span />
            <TextPair label="选中 gap ids" value={props.topicFreezeForm.selected_gap_ids} onChange={(value) => props.setTopicFreezeForm({ ...props.topicFreezeForm, selected_gap_ids: value })} span />
            <TextPair label="新颖性类型" value={props.topicFreezeForm.novelty_type} onChange={(value) => props.setTopicFreezeForm({ ...props.topicFreezeForm, novelty_type: value })} span />
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
                  spec_id: props.specFreezeForm.spec_id,
                  topic_id: props.specFreezeForm.topic_id,
                  hypothesis: parseLines(props.specFreezeForm.hypothesis),
                  must_beat_baselines: parseLines(props.specFreezeForm.must_beat_baselines),
                  datasets: parseLines(props.specFreezeForm.datasets),
                  metrics: parseLines(props.specFreezeForm.metrics),
                  fairness_constraints: parseLines(props.specFreezeForm.fairness_constraints),
                  ablations: parseLines(props.specFreezeForm.ablations),
                  success_criteria: parseLines(props.specFreezeForm.success_criteria),
                  failure_criteria: parseLines(props.specFreezeForm.failure_criteria),
                  approved_by: props.specFreezeForm.approved_by,
                  status: props.specFreezeForm.status,
                });
                props.setNotice(`已保存 spec freeze ${props.specFreezeForm.spec_id}`);
              });
            }}
          >
            <FormHint title="规格冻结" body="实验假设、基线、数据集和成功标准都应该在这里定下来。" />
            <InputPair label="Spec id" value={props.specFreezeForm.spec_id} onChange={(value) => props.setSpecFreezeForm({ ...props.specFreezeForm, spec_id: value })} required />
            <InputPair label="Topic id" value={props.specFreezeForm.topic_id} onChange={(value) => props.setSpecFreezeForm({ ...props.specFreezeForm, topic_id: value })} required />
            <TextPair label="假设" value={props.specFreezeForm.hypothesis} onChange={(value) => props.setSpecFreezeForm({ ...props.specFreezeForm, hypothesis: value })} span />
            <TextPair label="必须超过的基线" value={props.specFreezeForm.must_beat_baselines} onChange={(value) => props.setSpecFreezeForm({ ...props.specFreezeForm, must_beat_baselines: value })} span />
            <TextPair label="数据集" value={props.specFreezeForm.datasets} onChange={(value) => props.setSpecFreezeForm({ ...props.specFreezeForm, datasets: value })} span />
            <TextPair label="指标" value={props.specFreezeForm.metrics} onChange={(value) => props.setSpecFreezeForm({ ...props.specFreezeForm, metrics: value })} span />
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
                  ...props.runForm,
                  seed: Number(props.runForm.seed),
                });
                props.setNotice(`已创建 run ${props.runForm.run_id}`);
              });
            }}
          >
            <FormHint title="创建 run" body="如果 spec 已冻结，这里只要填 run id、commit、dataset snapshot 就能直接发车。" />
            <InputPair label="Run id" value={props.runForm.run_id} onChange={(value) => props.setRunForm({ ...props.runForm, run_id: value })} required />
            <InputPair label="Spec id" value={props.runForm.spec_id} onChange={(value) => props.setRunForm({ ...props.runForm, spec_id: value })} required />
            <InputPair label="Git commit" value={props.runForm.git_commit} onChange={(value) => props.setRunForm({ ...props.runForm, git_commit: value })} required />
            <InputPair label="配置哈希" value={props.runForm.config_hash} onChange={(value) => props.setRunForm({ ...props.runForm, config_hash: value })} required />
            <InputPair label="数据快照" value={props.runForm.dataset_snapshot} onChange={(value) => props.setRunForm({ ...props.runForm, dataset_snapshot: value })} required />
            <InputPair label="Seed" value={props.runForm.seed} onChange={(value) => props.setRunForm({ ...props.runForm, seed: value })} required />
            <InputPair label="GPU" value={props.runForm.gpu} onChange={(value) => props.setRunForm({ ...props.runForm, gpu: value })} required />
            <button className="button" type="submit">
              创建 run
            </button>
          </form>
        </div>
      </Panel>

      <Panel title="4. 结论、审批与归档" subtitle="把 claim、results freeze、lesson 和审批放到同一段收口。">
        <div className="double-form">
          <div className="stack-md">
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void props.runAction("create-claim", async () => {
                  await props.createClaim(props.claimForm);
                  props.setNotice(`已创建 claim ${props.claimForm.claim_id}`);
                });
              }}
            >
              <FormHint title="Claim" body="适合在 run 结果初步稳定后登记，后面可直接发起验证。" />
              <InputPair label="Claim id" value={props.claimForm.claim_id} onChange={(value) => props.setClaimForm({ ...props.claimForm, claim_id: value })} required />
              <InputPair label="Claim 类型" value={props.claimForm.claim_type} onChange={(value) => props.setClaimForm({ ...props.claimForm, claim_type: value })} required />
              <InputPair label="风险级别" value={props.claimForm.risk_level} onChange={(value) => props.setClaimForm({ ...props.claimForm, risk_level: value })} />
              <label className="checkbox-row span-2">
                <input type="checkbox" checked={props.claimForm.approved_by_human} onChange={(event) => props.setClaimForm({ ...props.claimForm, approved_by_human: event.target.checked })} />
                已人工批准
              </label>
              <TextPair label="Claim 文本" value={props.claimForm.text} onChange={(value) => props.setClaimForm({ ...props.claimForm, text: value })} required span />
              <button className="button" type="submit">
                创建 claim
              </button>
            </form>

            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void props.runAction("save-results-freeze", async () => {
                  await props.saveResultsFreeze({
                    results_id: props.resultsFreezeForm.results_id,
                    spec_id: props.resultsFreezeForm.spec_id,
                    main_claims: parseLines(props.resultsFreezeForm.main_claims),
                    tables: parseLines(props.resultsFreezeForm.tables),
                    figures: parseLines(props.resultsFreezeForm.figures),
                    approved_by: props.resultsFreezeForm.approved_by,
                    status: props.resultsFreezeForm.status,
                  });
                  props.setNotice(`已保存 results freeze ${props.resultsFreezeForm.results_id}`);
                });
              }}
            >
              <FormHint title="结果冻结" body="适合在主要表格和图已经稳定时执行，方便写作台和审批台接手。" />
              <InputPair label="Results id" value={props.resultsFreezeForm.results_id} onChange={(value) => props.setResultsFreezeForm({ ...props.resultsFreezeForm, results_id: value })} required />
              <InputPair label="Spec id" value={props.resultsFreezeForm.spec_id} onChange={(value) => props.setResultsFreezeForm({ ...props.resultsFreezeForm, spec_id: value })} required />
              <TextPair label="主 claims" value={props.resultsFreezeForm.main_claims} onChange={(value) => props.setResultsFreezeForm({ ...props.resultsFreezeForm, main_claims: value })} span />
              <TextPair label="表格" value={props.resultsFreezeForm.tables} onChange={(value) => props.setResultsFreezeForm({ ...props.resultsFreezeForm, tables: value })} span />
              <TextPair label="图" value={props.resultsFreezeForm.figures} onChange={(value) => props.setResultsFreezeForm({ ...props.resultsFreezeForm, figures: value })} span />
              <button className="button" type="submit">
                保存 results freeze
              </button>
            </form>
          </div>

          <div className="stack-md">
            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void props.runAction("create-lesson", async () => {
                  await props.createLesson({
                    ...props.lessonForm,
                    task_kind: props.lessonForm.task_kind || null,
                    agent_name: props.lessonForm.agent_name || null,
                    provider_name: props.lessonForm.provider_name || null,
                    model_name: props.lessonForm.model_name || null,
                    source_task_id: props.lessonForm.source_task_id || null,
                    source_run_id: props.lessonForm.source_run_id || null,
                    source_claim_id: props.lessonForm.source_claim_id || null,
                    context_tags: parseLines(props.lessonForm.context_tags),
                    evidence_refs: parseLines(props.lessonForm.evidence_refs),
                    artifact_ids: parseLines(props.lessonForm.artifact_ids),
                  });
                  props.setNotice(`已创建 lesson ${props.lessonForm.lesson_id}`);
                });
              }}
            >
              <FormHint title="Lesson" body="把失败原因、经验修正和建议动作记下来，档案室才有价值。" />
              <InputPair label="Lesson id" value={props.lessonForm.lesson_id} onChange={(value) => props.setLessonForm({ ...props.lessonForm, lesson_id: value })} required />
              <InputPair label="类型" value={props.lessonForm.lesson_kind} onChange={(value) => props.setLessonForm({ ...props.lessonForm, lesson_kind: value })} required />
              <InputPair label="标题" value={props.lessonForm.title} onChange={(value) => props.setLessonForm({ ...props.lessonForm, title: value })} required />
              <InputPair label="任务类型" value={props.lessonForm.task_kind} onChange={(value) => props.setLessonForm({ ...props.lessonForm, task_kind: value })} />
              <TextPair label="摘要" value={props.lessonForm.summary} onChange={(value) => props.setLessonForm({ ...props.lessonForm, summary: value })} required span />
              <TextPair label="理由" value={props.lessonForm.rationale} onChange={(value) => props.setLessonForm({ ...props.lessonForm, rationale: value })} span />
              <TextPair label="建议动作" value={props.lessonForm.recommended_action} onChange={(value) => props.setLessonForm({ ...props.lessonForm, recommended_action: value })} span />
              <InputPair label="Agent name" value={props.lessonForm.agent_name} onChange={(value) => props.setLessonForm({ ...props.lessonForm, agent_name: value })} />
              <TextPair label="上下文标签" value={props.lessonForm.context_tags} onChange={(value) => props.setLessonForm({ ...props.lessonForm, context_tags: value })} span />
              <button className="button" type="submit">
                创建 lesson
              </button>
            </form>

            <form
              className="form-grid"
              onSubmit={(event) => {
                event.preventDefault();
                void props.runAction("create-approval", async () => {
                  await props.createApproval(props.approvalForm);
                  props.setNotice(`已记录审批 ${props.approvalForm.approval_id}`);
                });
              }}
            >
              <FormHint title="审批" body="适合在 results freeze 或高风险 claim 产生后补人工决定。" />
              <InputPair label="Approval id" value={props.approvalForm.approval_id} onChange={(value) => props.setApprovalForm({ ...props.approvalForm, approval_id: value })} required />
              <InputPair label="Project id" value={props.approvalForm.project_id} onChange={(value) => props.setApprovalForm({ ...props.approvalForm, project_id: value })} required />
              <InputPair label="目标类型" value={props.approvalForm.target_type} onChange={(value) => props.setApprovalForm({ ...props.approvalForm, target_type: value })} required />
              <InputPair label="目标 id" value={props.approvalForm.target_id} onChange={(value) => props.setApprovalForm({ ...props.approvalForm, target_id: value })} required />
              <InputPair label="批准人" value={props.approvalForm.approved_by} onChange={(value) => props.setApprovalForm({ ...props.approvalForm, approved_by: value })} required />
              <InputPair label="决定" value={props.approvalForm.decision} onChange={(value) => props.setApprovalForm({ ...props.approvalForm, decision: value })} required />
              <TextPair label="备注" value={props.approvalForm.comment} onChange={(value) => props.setApprovalForm({ ...props.approvalForm, comment: value })} span />
              <button className="button" type="submit">
                记录审批
              </button>
            </form>
          </div>
        </div>
      </Panel>
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
