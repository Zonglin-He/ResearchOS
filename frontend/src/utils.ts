import {
  Archive,
  BookOpenText,
  FlaskConical,
  LibraryBig,
  PencilLine,
  ShieldAlert,
  type LucideIcon,
} from "lucide-react";

export type RoleLane = {
  id: string;
  label: string;
  mission: string;
  output: string;
  taskKinds: string[];
  icon: LucideIcon;
  workspaceNote: string;
  propHint: string;
  nextHint: string;
  sharedCrew?: string[];
};

export const roleLanes: RoleLane[] = [
  {
    id: "librarian",
    label: "资料馆员",
    mission: "收集论文、整理引用，并把原始材料沉淀成可以复用的证据对象。",
    output: "paper_card",
    taskKinds: ["paper_ingest", "source_collect", "evidence_normalize"],
    icon: LibraryBig,
    workspaceNote: "入口工位，最适合快速吞入新文献与结构化摘要。",
    propHint: "书车、索引柜、扫描台",
    nextHint: "先把 paper card 补齐，再交给综合台做 gap map。",
  },
  {
    id: "synthesizer",
    label: "综合台",
    mission: "把多篇证据串起来，找出空白、冲突和新的攻击面。",
    output: "gap_map",
    taskKinds: ["gap_map_build", "topic_scan", "synthesis"],
    icon: BookOpenText,
    workspaceNote: "适合做主题聚类、研究问题压缩和选题收束。",
    propHint: "白板、便利贴墙、地图桌",
    nextHint: "确认 gap 之后，就可以冻结 topic 或直接排 builder 的实验任务。",
  },
  {
    id: "builder",
    label: "实验台",
    mission: "起草实验规格、创建 run、推进 builder 类任务，产出可验证结果。",
    output: "experiment_spec / run_manifest",
    taskKinds: ["experiment_spec", "run_execute", "builder", "benchmark"],
    icon: FlaskConical,
    workspaceNote: "和写作台共用资源，适合高频切换 spec、run、结果检查。",
    propHint: "仪器柜、线缆、试管、共享主机",
    nextHint: "先补 spec freeze，再发 run，能减少返工。",
    sharedCrew: ["Builder", "Publisher"],
  },
  {
    id: "review",
    label: "复核台",
    mission: "验证 claim、审计 run，把阻塞点在发布前暴露出来。",
    output: "verification_report / audit_report",
    taskKinds: ["review", "verification", "audit", "claim_check"],
    icon: ShieldAlert,
    workspaceNote: "适合处理 waiting_approval、失败 run 与高风险 claim。",
    propHint: "审计屏、章戳、风险灯",
    nextHint: "优先处理 blocked 和 waiting_approval 的任务，流转速度提升最明显。",
  },
  {
    id: "publish",
    label: "写作台",
    mission: "把冻结后的研究证据转成可读稿件、结果摘要和对外输出。",
    output: "paper_draft",
    taskKinds: ["draft_write", "publish_prepare", "results_package", "publisher"],
    icon: PencilLine,
    workspaceNote: "和实验台共用 agent 池，常在出图、写表、整理结论间来回切换。",
    propHint: "打字机、稿纸架、展示灯箱",
    nextHint: "results freeze 确认后再写最终稿，避免文字和表格版本错位。",
    sharedCrew: ["Publisher", "Builder"],
  },
  {
    id: "archive",
    label: "档案室",
    mission: "沉淀 lesson、bundle 和可追溯记录，让后续项目可直接复用。",
    output: "archive_entry",
    taskKinds: ["lesson_record", "archive_bundle", "freeze_archive", "archivist"],
    icon: Archive,
    workspaceNote: "项目尾声最关键的工位，决定经验能否复用。",
    propHint: "档案柜、封条、标本盒",
    nextHint: "实验结论稳定后立刻登记 lesson，别等记忆衰减。",
  },
];

export function parseRequiredJson(raw: string) {
  const parsed = JSON.parse(raw);
  if (parsed === null || Array.isArray(parsed) || typeof parsed !== "object") {
    throw new Error("这里需要传入 JSON 对象。");
  }
  return parsed as Record<string, unknown>;
}

export function parseOptionalJson(raw: string) {
  const normalized = raw.trim();
  if (!normalized) {
    return null;
  }
  return parseRequiredJson(normalized);
}

export function parseLines(raw: string) {
  return raw
    .split(/\r?\n|,/)
    .map((item) => item.trim())
    .filter(Boolean);
}

export function parseEvidenceRefs(raw: string) {
  return parseLines(raw);
}

export function normalizeError(error: unknown) {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

export function renderCountMap(map: Record<string, number>) {
  const entries = Object.entries(map);
  if (!entries.length) {
    return "暂无";
  }
  return entries
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, count]) => `${key}: ${count}`)
    .join(" | ");
}
