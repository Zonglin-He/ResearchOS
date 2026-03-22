import { useEffect, useMemo, useRef } from "react";
import type {
  Artifact,
  ArtifactDetail,
  AuditSummary,
  GapMap,
  GapMapDetail,
  KnowledgeSummary,
  Lesson,
  PaperCard,
  PaperCardDetail,
  ResultsFreeze,
  Task,
  VerificationSummary,
} from "../api";
import { renderCountMap } from "../utils";
import { EmptyState, KeyValue, Panel, StatCard, StatusPill } from "./ui";

type FreezeLike = Record<string, unknown> | null;

type Props = {
  projectTasks: Task[];
  projectArtifacts: Artifact[];
  artifactDetail: ArtifactDetail | null;
  paperCardDetail: PaperCardDetail | null;
  gapMapDetail: GapMapDetail | null;
  verificationSummary: VerificationSummary;
  auditSummary: AuditSummary;
  paperCards: PaperCard[];
  gapMaps: GapMap[];
  lessons: Lesson[];
  knowledgeSummary: KnowledgeSummary;
  topicFreeze: FreezeLike;
  specFreeze: FreezeLike;
  resultsFreeze: ResultsFreeze | null;
  runAction: (key: string, callback: () => Promise<unknown>, refresh?: boolean) => Promise<void>;
  loadArtifact: (artifactId: string) => Promise<ArtifactDetail>;
  loadPaperCard: (paperId: string) => Promise<PaperCardDetail>;
  loadGapMap: (topic: string) => Promise<GapMapDetail>;
  setArtifactDetail: (detail: ArtifactDetail | null) => void;
  setPaperCardDetail: (detail: PaperCardDetail | null) => void;
  setGapMapDetail: (detail: GapMapDetail | null) => void;
  openHumanSelect: (task: Task) => void;
  openTopicFreeze: () => void;
};

type TaskOutput = {
  taskId: string;
  kind: string;
  status: string;
  summary: string;
  detail: string;
  onClick: () => void;
};

type FlowStep = {
  id: string;
  label: string;
  detail: string;
  status: string;
  onClick: () => void;
};

type RecordItem = {
  id: string;
  label: string;
  meta?: string;
  onClick?: () => void;
  active?: boolean;
};

export function RegistryTab(props: Props) {
  const detailRef = useRef<HTMLDivElement | null>(null);
  const taskOutputs = useMemo(() => buildTaskOutputs(props), [props]);
  const flowSteps = useMemo(() => buildFlowSteps(props), [props]);

  useEffect(() => {
    if (props.paperCardDetail || props.gapMapDetail || props.artifactDetail) {
      detailRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }, [props.paperCardDetail, props.gapMapDetail, props.artifactDetail]);

  const paperItems: RecordItem[] = props.paperCards.map((card) => ({
    id: card.paper_id,
    label: card.title,
    meta: card.paper_id,
    active: props.paperCardDetail?.paper_id === card.paper_id,
    onClick: () => openPaperCard(props, card.paper_id),
  }));
  const gapItems: RecordItem[] = props.gapMaps.map((gap) => ({
    id: gap.topic,
    label: gap.topic,
    meta: `${gap.clusters} 个 cluster`,
    active: props.gapMapDetail?.topic === gap.topic,
    onClick: () => openGapMap(props, gap.topic),
  }));
  const lessonItems: RecordItem[] = props.lessons.map((lesson) => ({
    id: lesson.lesson_id,
    label: lesson.title,
    meta: lesson.lesson_id,
  }));
  const freezeItems: RecordItem[] = [
    props.topicFreeze ? { id: "topic-freeze", label: "topic freeze 已保存", onClick: props.openTopicFreeze } : null,
    props.specFreeze ? { id: "spec-freeze", label: "spec freeze 已保存" } : null,
    props.resultsFreeze ? { id: "results-freeze", label: "results freeze 已保存" } : null,
  ].filter((item): item is RecordItem => Boolean(item));

  return (
    <div className="content-grid registry-grid">
      <Panel title="研究流程条" subtitle="沿着这条链路查看当前证据，也可以直接跳到需要你处理的节点。">
        <div className="chain-flow">
          {flowSteps.map((step, index) => (
            <div key={step.id} className="chain-flow-item">
              <button type="button" className="chain-flow-button" onClick={step.onClick}>
                <span className="chain-flow-index">{index + 1}</span>
                <div className="chain-flow-copy">
                  <strong>{step.label}</strong>
                  <small>{step.detail}</small>
                </div>
                <StatusPill value={step.status} />
              </button>
              {index < flowSteps.length - 1 ? <div className="chain-flow-line" /> : null}
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="本任务产出" subtitle="按任务链查看系统已经落库的结果，以及当前该点哪里。">
        {taskOutputs.length ? (
          <div className="task-output-grid">
            {taskOutputs.map((item) => (
              <button key={item.taskId} type="button" className="task-output-card task-output-button" onClick={item.onClick}>
                <div className="task-output-head">
                  <div>
                    <strong>{item.taskId}</strong>
                    <p>{item.kind}</p>
                  </div>
                  <StatusPill value={item.status} />
                </div>
                <p>{item.summary}</p>
                <small>{item.detail}</small>
              </button>
            ))}
          </div>
        ) : (
          <EmptyState title="还没有任务产出" body="先调度任务，登记结果会在这里按任务链显示。" />
        )}
      </Panel>

      <Panel title="运行产物 Artifact" subtitle="这里只显示 run 产生的文件、checkpoint、报表和附件。">
        {props.projectArtifacts.length ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Artifact</th>
                  <th>类型</th>
                  <th>Run</th>
                  <th>路径</th>
                </tr>
              </thead>
              <tbody>
                {props.projectArtifacts.map((artifact) => (
                  <tr key={artifact.artifact_id} className="clickable-row" onClick={() => openArtifact(props, artifact.artifact_id)}>
                    <td>{artifact.artifact_id}</td>
                    <td>{artifact.kind}</td>
                    <td>{artifact.run_id}</td>
                    <td className="mono">{artifact.path}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="还没有运行产物" body="只有 run 执行后生成的文件才会显示在这里。" />
        )}
      </Panel>

      <Panel title="研究登记结果" subtitle="Paper card、gap map、lesson 和 freeze 单独展示，点一下就能看详情。">
        <div className="record-grid">
          <RecordCard title="Paper card" count={props.paperCards.length} items={paperItems} emptyText="还没有 paper card。" />
          <RecordCard title="Gap map" count={props.gapMaps.length} items={gapItems} emptyText="还没有 gap map。" />
          <RecordCard title="Lesson" count={props.lessons.length} items={lessonItems} emptyText="还没有 lesson。" />
          <RecordCard title="Freeze" count={freezeItems.length} items={freezeItems} emptyText="还没有 freeze。" />
        </div>
      </Panel>

      <Panel title="项目记忆" subtitle="系统会逐步积累方向决策、实验发现、文献索引和未解决问题。">
        <div className="pulse-grid">
          {props.knowledgeSummary.buckets.map((bucket) => (
            <StatCard
              key={bucket.bucket}
              label={bucketLabel(bucket.bucket)}
              value={bucket.count}
              meta={bucket.latest_title || "暂无条目"}
            />
          ))}
        </div>
      </Panel>

      <Panel title="结果详情" subtitle="点击任务产出、登记列表或 Artifact 表格后，这里会显示完整内容。">
        <div ref={detailRef} />
        {props.paperCardDetail ? (
          <div className="stack-md">
            <KeyValue label="Paper id" value={props.paperCardDetail.paper_id} />
            <KeyValue label="标题" value={props.paperCardDetail.title} />
            <KeyValue label="研究问题" value={props.paperCardDetail.problem} />
            <KeyValue label="研究场景" value={props.paperCardDetail.setting} />
            <KeyValue label="任务类型" value={props.paperCardDetail.task_type} />
            <KeyValue label="方法摘要" value={props.paperCardDetail.method_summary || "-"} />
            <KeyValue label="最强结果" value={props.paperCardDetail.strongest_result || "-"} />
            <KeyValue label="数据集" value={props.paperCardDetail.datasets.join(" / ") || "-"} />
            <KeyValue label="指标" value={props.paperCardDetail.metrics.join(" / ") || "-"} />
            <KeyValue label="核心模块" value={props.paperCardDetail.key_modules.join(" / ") || "-"} />
            <KeyValue label="想法种子" value={props.paperCardDetail.idea_seeds.join(" / ") || "-"} />
            <KeyValue
              label="证据引用"
              value={
                props.paperCardDetail.evidence_refs.length
                  ? props.paperCardDetail.evidence_refs.map((ref) => `${ref.section}:${ref.page}`).join(", ")
                  : "-"
              }
            />
          </div>
        ) : props.gapMapDetail ? (
          <div className="stack-md">
            <KeyValue label="主题" value={props.gapMapDetail.topic} />
            <KeyValue label="Cluster 数" value={props.gapMapDetail.clusters.length} />
            {props.gapMapDetail.clusters.map((cluster) => (
              <div key={cluster.name} className="record-card">
                <div className="record-card-head">
                  <strong>{cluster.name}</strong>
                  <span>{cluster.gaps.length}</span>
                </div>
                <ul className="plain-list">
                  {cluster.gaps.map((gap) => (
                    <li key={gap.gap_id}>
                      <strong>{gap.gap_id}</strong>
                      <div>{gap.description}</div>
                      <small>
                        难度 {gap.difficulty || "-"} / 新颖性 {gap.novelty_type || "-"} / 相关论文{" "}
                        {gap.supporting_papers.join(", ") || "-"}
                      </small>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        ) : props.artifactDetail ? (
          <div className="stack-md">
            <KeyValue label="Artifact" value={props.artifactDetail.artifact_id} />
            <KeyValue label="解析后路径" value={<span className="mono">{props.artifactDetail.resolved_path}</span>} />
            <KeyValue label="磁盘存在" value={String(props.artifactDetail.exists_on_disk)} />
            <KeyValue label="证据引用" value={props.artifactDetail.evidence_refs.join(", ") || "-"} />
            <KeyValue
              label="Claim 支持"
              value={
                props.artifactDetail.provenance.claim_support_refs
                  .map((item) => `${item.claim_id}:${item.support_kind}`)
                  .join(", ") || "-"
              }
            />
          </div>
        ) : (
          <EmptyState title="尚未选择结果" body="点一个 paper card、gap map、任务产出或 artifact，这里就会显示详情。" />
        )}
      </Panel>

      <Panel title="验证与审计" subtitle="从登记层快速看整体状态。">
        <div className="pulse-grid">
          <StatCard label="检查数" value={props.verificationSummary.total_checks} />
          <StatCard label="报告数" value={props.auditSummary.total_reports} />
          <StatCard label="条目数" value={props.auditSummary.total_entries} />
          <StatCard label="发现数" value={props.auditSummary.findings.length} />
        </div>
        <div className="stack-md">
          <KeyValue label="验证状态统计" value={renderCountMap(props.verificationSummary.status_counts)} />
          <KeyValue label="审计状态统计" value={renderCountMap(props.auditSummary.entry_status_counts)} />
          <KeyValue label="主要发现" value={props.auditSummary.findings.join(" | ") || "-"} />
        </div>
      </Panel>

      <Panel title="冻结中心" subtitle="主题、规格和结果冻结的当前状态。">
        <div className="freeze-grid">
          <FreezeCard title="主题" freeze={props.topicFreeze} />
          <FreezeCard title="规格" freeze={props.specFreeze} />
          <FreezeCard title="结果" freeze={props.resultsFreeze} />
        </div>
      </Panel>
    </div>
  );
}

function RecordCard(props: { title: string; count: number; items: RecordItem[]; emptyText: string }) {
  return (
    <div className="record-card">
      <div className="record-card-head">
        <strong>{props.title}</strong>
        <span>{props.count}</span>
      </div>
      {props.items.length ? (
        <div className="record-item-list">
          {props.items.slice(0, 8).map((item) =>
            item.onClick ? (
              <button
                key={item.id}
                type="button"
                className={item.active ? "record-item-button active" : "record-item-button"}
                onClick={item.onClick}
              >
                <span>{item.label}</span>
                {item.meta ? <small>{item.meta}</small> : null}
              </button>
            ) : (
              <div key={item.id} className="record-item-static">
                <span>{item.label}</span>
                {item.meta ? <small>{item.meta}</small> : null}
              </div>
            ),
          )}
        </div>
      ) : (
        <p className="muted">{props.emptyText}</p>
      )}
    </div>
  );
}

function FreezeCard(props: { title: string; freeze: FreezeLike }) {
  return (
    <div className="freeze-card">
      <div className="freeze-card-head">
        <strong>{props.title}</strong>
        <StatusPill value={props.freeze ? "active" : "missing"} />
      </div>
      <pre>{props.freeze ? JSON.stringify(props.freeze, null, 2) : "暂无"}</pre>
    </div>
  );
}

function bucketLabel(bucket: string) {
  const labels: Record<string, string> = {
    decisions: "决策",
    findings: "发现",
    literature: "文献",
    open_questions: "未决问题",
  };
  return labels[bucket] ?? bucket;
}

function buildTaskOutputs(props: Props): TaskOutput[] {
  return props.projectTasks
    .slice()
    .sort((left, right) => right.created_at.localeCompare(left.created_at))
    .slice(0, 8)
    .map((task) => {
      if (task.kind === "paper_ingest") {
        const linkedGapTask = props.projectTasks.find(
          (candidate) => candidate.parent_task_id === task.task_id && candidate.kind === "gap_mapping",
        );
        const paperIds = Array.isArray(linkedGapTask?.input_payload.paper_ids)
          ? linkedGapTask?.input_payload.paper_ids.filter((item): item is string => typeof item === "string")
          : [];
        const firstPaperId = paperIds?.[0] ?? props.paperCards[0]?.paper_id;
        return {
          taskId: task.task_id,
          kind: task.kind,
          status: task.status,
          summary: "论文检索与 paper card 整理",
          detail: firstPaperId ? "点击展开对应论文卡片" : "还没有可看的论文卡片",
          onClick: () => {
            if (firstPaperId) {
              openPaperCard(props, firstPaperId);
            }
          },
        };
      }

      if (task.kind === "gap_mapping") {
        const topic =
          typeof task.input_payload.topic === "string" && task.input_payload.topic
            ? task.input_payload.topic
            : props.gapMaps[0]?.topic;
        return {
          taskId: task.task_id,
          kind: task.kind,
          status: task.status,
          summary: "研究 gap 归纳与候选方向排序",
          detail: topic ? "点击展开对应 gap map" : "还没有可看的 gap map",
          onClick: () => {
            if (topic) {
              openGapMap(props, topic);
            }
          },
        };
      }

      if (task.kind === "human_select") {
        return {
          taskId: task.task_id,
          kind: task.kind,
          status: task.status,
          summary: "等待人工选择研究方向",
          detail: props.topicFreeze ? "topic freeze 已保存，可继续自动推进" : "点击跳到主题冻结/继续自动推进",
          onClick: () => props.openHumanSelect(task),
        };
      }

      if (task.kind.includes("build") || task.kind.includes("run") || task.kind.includes("write")) {
        return {
          taskId: task.task_id,
          kind: task.kind,
          status: task.status,
          summary: task.goal,
          detail:
            props.projectArtifacts.length > 0
              ? `当前项目已有 ${props.projectArtifacts.length} 个 artifact`
              : "当前项目还没有 artifact",
          onClick: () => {},
        };
      }

      return {
        taskId: task.task_id,
        kind: task.kind,
        status: task.status,
        summary: task.goal,
        detail: "结果会在完成后登记到对应区域。",
        onClick: () => {},
      };
    });
}

function buildFlowSteps(props: Props): FlowStep[] {
  const humanSelectTask = props.projectTasks.find((task) => task.kind === "human_select");
  const latestPaperId = props.paperCards[props.paperCards.length - 1]?.paper_id;
  const latestGapTopic = props.gapMaps[props.gapMaps.length - 1]?.topic;

  return [
    {
      id: "paper_ingest",
      label: "paper_ingest",
      detail: latestPaperId ? latestPaperId : "点击看最近的论文卡片",
      status: props.projectTasks.find((task) => task.kind === "paper_ingest")?.status ?? "missing",
      onClick: () => {
        if (latestPaperId) {
          openPaperCard(props, latestPaperId);
        }
      },
    },
    {
      id: "gap_mapping",
      label: "gap_mapping",
      detail: latestGapTopic ? latestGapTopic : "点击看最近的 gap map",
      status: props.projectTasks.find((task) => task.kind === "gap_mapping")?.status ?? "missing",
      onClick: () => {
        if (latestGapTopic) {
          openGapMap(props, latestGapTopic);
        }
      },
    },
    {
      id: "human_select",
      label: "human_select",
      detail: humanSelectTask ? "点击进入人工决策" : "当前没有待选方向",
      status: humanSelectTask?.status ?? "missing",
      onClick: () => {
        if (humanSelectTask) {
          props.openHumanSelect(humanSelectTask);
        }
      },
    },
    {
      id: "topic_freeze",
      label: "topic_freeze",
      detail: props.topicFreeze ? "已保存，可继续往下推进" : "点击去填写 topic freeze",
      status: props.topicFreeze ? "approved" : "missing",
      onClick: props.openTopicFreeze,
    },
  ];
}

function openArtifact(props: Props, artifactId: string) {
  void props.runAction(
    `artifact-${artifactId}`,
    async () => {
      props.setPaperCardDetail(null);
      props.setGapMapDetail(null);
      props.setArtifactDetail(await props.loadArtifact(artifactId));
    },
    false,
  );
}

function openPaperCard(props: Props, paperId: string) {
  void props.runAction(
    `paper-card-${paperId}`,
    async () => {
      props.setGapMapDetail(null);
      props.setArtifactDetail(null);
      props.setPaperCardDetail(await props.loadPaperCard(paperId));
    },
    false,
  );
}

function openGapMap(props: Props, topic: string) {
  void props.runAction(
    `gap-map-${topic}`,
    async () => {
      props.setPaperCardDetail(null);
      props.setArtifactDetail(null);
      props.setGapMapDetail(await props.loadGapMap(topic));
    },
    false,
  );
}
