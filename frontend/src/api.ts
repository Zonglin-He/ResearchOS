export const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined) ?? "/api";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const rawBody = await response.text();
    let detail = rawBody;
    try {
      const parsed = JSON.parse(rawBody) as { detail?: string };
      if (typeof parsed.detail === "string" && parsed.detail.trim()) {
        detail = parsed.detail;
      }
    } catch {
      // Ignore JSON parsing errors and fall back to the raw body.
    }
    throw new Error(detail || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export function getJson<T>(path: string): Promise<T> {
  return request<T>(path);
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
}

export type Project = {
  project_id: string;
  name: string;
  description: string;
  status: string;
  stage: string;
  dispatch_profile: DispatchProfile | null;
  created_at: string;
};

export type Task = {
  task_id: string;
  project_id: string;
  kind: string;
  goal: string;
  input_payload: Record<string, unknown>;
  owner: string;
  assigned_agent: string | null;
  parent_task_id: string | null;
  depends_on: string[];
  join_key: string | null;
  fanout_group: string | null;
  max_retries: number;
  dispatch_profile: DispatchProfile | null;
  status: string;
  experiment_proposal_id: string | null;
  last_run_routing: ResolvedDispatch | null;
  retry_count: number;
  last_error: string | null;
  next_retry_at: string | null;
  checkpoint_path: string | null;
  created_at: string;
};

export type DispatchProfile = {
  provider: ProviderSpec | null;
  model_profile: ModelProfile | null;
  max_steps: number | null;
  metadata: Record<string, unknown>;
};

export type ProviderSpec = {
  provider_name: string;
  model: string | null;
};

export type ModelProfile = {
  profile_name: string;
  provider_name: string | null;
  model: string | null;
  max_steps: number | null;
  metadata: Record<string, unknown>;
};

export type ResolvedDispatch = {
  provider_name: string;
  provider_family: string | null;
  model: string | null;
  model_profile_name: string | null;
  max_steps: number | null;
  role_name: string | null;
  capability_class: string | null;
  candidate_models: Record<string, string[]>;
  fallback_chain: string[];
  decision_reason: string | null;
  fallback_reason: string | null;
  sources: Record<string, string>;
  metadata: Record<string, unknown>;
};

export type ProjectDashboard = {
  project_id: string;
  project_name: string;
  project_status: string;
  total_tasks: number;
  queued_tasks: number;
  running_tasks: number;
  waiting_approval_tasks: number;
  succeeded_tasks: number;
  failed_tasks: number;
  cancelled_tasks: number;
  artifact_count: number;
  paper_card_count: number;
  gap_map_count: number;
  run_count: number;
  latest_task_ids: string[];
  topic_freeze_present: boolean;
  spec_freeze_present: boolean;
  results_freeze_present: boolean;
  recommended_next_task_kind: string | null;
  recommendation_reason: string;
  expected_artifact: string;
  likely_next_task_kind: string | null;
  flow_snapshot: Record<string, unknown>;
  available_flow_actions: string[];
};

export type RoutingInspection = {
  scope: string;
  subject_id: string | null;
  resolved_dispatch: ResolvedDispatch;
  provider_health: ProviderHealthSnapshot[];
};

export type ProviderHealthSnapshot = {
  provider_family: string;
  state: string;
  cli_installed: boolean;
  manually_disabled: boolean;
  failure_class: string | null;
  detail: string;
  cooldown_seconds_remaining: number;
};

export type Claim = {
  claim_id: string;
  text: string;
  claim_type: string;
  risk_level: string;
  approved_by_human: boolean;
  supported_by_runs: string[];
  supported_by_tables: string[];
};

export type RunManifest = {
  run_id: string;
  spec_id: string;
  git_commit: string;
  config_hash: string;
  dataset_snapshot: string;
  seed: number;
  gpu: string;
  experiment_proposal_id: string | null;
  experiment_branch: string | null;
  start_time: string;
  end_time: string | null;
  status: string;
  metrics: Record<string, unknown>;
  artifacts: string[];
  dispatch_routing: ResolvedDispatch | null;
};

export type Artifact = {
  artifact_id: string;
  run_id: string;
  kind: string;
  path: string;
  hash: string;
  metadata: Record<string, unknown>;
};

export type Verification = {
  verification_id: string;
  subject_type: string;
  subject_id: string;
  check_type: string;
  status: string;
  rationale: string;
  evidence_refs: string[];
  artifact_ids: string[];
  missing_fields: string[];
  created_at: string;
};

export type VerificationSummary = {
  total_checks: number;
  status_counts: Record<string, number>;
  check_type_counts: Record<string, number>;
  subject_type_counts: Record<string, number>;
};

export type AuditEntry = {
  entry_id: string;
  subject_type: string;
  subject_id: string;
  category: string;
  status: string;
  rationale: string;
  evidence_refs: string[];
  artifact_ids: string[];
  related_run_ids: string[];
  related_claim_ids: string[];
  created_at: string;
};

export type AuditReport = {
  report_type: string;
  status: string;
  findings: string[];
  recommendations: string[];
  entries: AuditEntry[];
};

export type AuditSummary = {
  total_reports: number;
  total_entries: number;
  report_status_counts: Record<string, number>;
  entry_status_counts: Record<string, number>;
  findings: string[];
  recommendations: string[];
};

export type Approval = {
  approval_id: string;
  project_id: string;
  target_type: string;
  target_id: string;
  approved_by: string;
  decision: string;
  comment: string;
  condition_text: string;
  context_summary: string;
  recommended_action: string;
  due_at: string | null;
  created_at: string;
};

export type Lesson = {
  lesson_id: string;
  lesson_kind: string;
  title: string;
  summary: string;
  rationale: string;
  recommended_action: string;
  task_kind: string | null;
  agent_name: string | null;
  tool_name: string | null;
  provider_name: string | null;
  model_name: string | null;
  failure_type: string | null;
  repository_ref: string | null;
  dataset_ref: string | null;
  context_tags: string[];
  evidence_refs: string[];
  artifact_ids: string[];
  source_task_id: string | null;
  source_run_id: string | null;
  source_claim_id: string | null;
  expires_at: string | null;
  hit_count: number;
  last_hit_at: string | null;
  is_valid: boolean;
  created_at: string;
};

export type PaperCard = {
  paper_id: string;
  title: string;
  task_type: string;
};

export type GapMap = {
  topic: string;
  clusters: number;
};

export type PaperCardDetail = {
  paper_id: string;
  title: string;
  problem: string;
  setting: string;
  task_type: string;
  core_assumption: string[];
  method_summary: string;
  key_modules: string[];
  datasets: string[];
  metrics: string[];
  strongest_result: string;
  claimed_contributions: string[];
  hidden_dependencies: string[];
  likely_failure_modes: string[];
  repro_risks: string[];
  idea_seeds: string[];
  evidence_refs: Array<{
    section: string;
    page: number;
  }>;
};

export type GapMapDetail = {
  topic: string;
  clusters: Array<{
    name: string;
    gaps: Array<{
      gap_id: string;
      description: string;
      supporting_papers: string[];
      evidence_summary: string;
      attack_surface: string;
      difficulty: string;
      novelty_type: string;
      feasibility: string;
      novelty_score: number;
      debate_weaknesses: string[];
    }>;
  }>;
};

export type TopicFreeze = {
  topic_id: string;
  selected_gap_ids: string[];
  research_question: string;
  novelty_type: string[];
  owner: string;
  status: string;
};

export type SpecFreeze = {
  spec_id: string;
  topic_id: string;
  hypothesis: string[];
  must_beat_baselines: string[];
  datasets: string[];
  metrics: string[];
  fairness_constraints: string[];
  ablations: string[];
  success_criteria: string[];
  failure_criteria: string[];
  target_venue: string;
  human_constraints: string[];
  approved_by: string;
  status: string;
};

export type KnowledgeBucketSummary = {
  bucket: string;
  count: number;
  latest_title: string;
};

export type KnowledgeSummary = {
  buckets: KnowledgeBucketSummary[];
};

export type KnowledgeRecord = {
  record_id: string;
  project_id: string;
  title: string;
  summary: string;
  context_tags: string[];
  payload: Record<string, unknown>;
  created_at: string;
};

export type ResultsFreeze = {
  results_id: string;
  spec_id: string;
  main_claims: string[];
  tables: string[];
  figures: string[];
  approved_by: string;
  status: string;
};

export type AutopilotResult = {
  dispatched_task_ids: string[];
  stop_reason: string;
  human_select_task_id: string | null;
};

export type GuideStartResponse = {
  project_id: string;
  project_name: string;
  intake_task_id: string;
  autopilot: AutopilotResult;
  next_step: string;
};

export type GuideAdoptDirectionResponse = {
  topic_id: string;
  build_task_id: string;
  autopilot: AutopilotResult;
  next_step: string;
};

export type ProjectAutopilotResponse = {
  project_id: string;
  autopilot: AutopilotResult;
};

export type GuideDiscussDirectionResponse = {
  thread_id: string;
  assistant_message: string;
  gap_id: string;
  topic: string;
  strengths: string[];
  risks: string[];
  next_checks: string[];
  cited_papers: string[];
  research_question_suggestion: string;
  assistant_role: string;
  provider_name: string;
  model_name: string;
  reasoning_effort: string;
  skill_name: string;
};

export type GuideDiscussionMessage = {
  message_id?: number | null;
  role: "user" | "assistant";
  content: string;
  created_at?: string | null;
  metadata?: Record<string, unknown>;
};

export type DiscussionHistory = {
  thread_id: string;
  messages: GuideDiscussionMessage[];
};

export type DiscussionEntityRef = {
  entity_type: string;
  entity_id: string;
  label: string;
};

export type DiscussionCoverageCheck = {
  ref: string;
  ref_type: string;
  status: string;
  note: string;
  linked_entity_id: string | null;
};

export type DiscussionCoverage = {
  checks: DiscussionCoverageCheck[];
  summary: string;
};

export type DiscussionDistillation = {
  summary: string;
  findings: string[];
  decisions: string[];
  literature_notes: string[];
  open_questions: string[];
  risks: string[];
  counterarguments: string[];
  suggested_next_actions: string[];
  cited_dois: string[];
  referenced_claim_ids: string[];
};

export type DiscussionImportRecord = {
  source_mode: string;
  provider_label: string;
  verbatim_text: string;
  transcript_title: string;
  cited_dois: string[];
  referenced_claim_ids: string[];
  imported_at: string;
};

export type DiscussionContextBundle = {
  bundle_id: string;
  project_id: string;
  stage: string;
  branch_kind: string;
  target_kind: string;
  target_id: string;
  target_label: string;
  research_goal: string;
  focus_question: string;
  operator_prompt: string;
  current_state: Record<string, unknown>;
  controversies: string[];
  questions_to_answer: string[];
  attached_entities: DiscussionEntityRef[];
  handoff_packet: string;
  created_at: string;
};

export type DiscussionSession = {
  session_id: string;
  project_id: string;
  title: string;
  source_type: string;
  source_label: string;
  status: string;
  stage: string;
  branch_kind: string;
  target_kind: string;
  target_id: string;
  target_label: string;
  focus_question: string;
  operator_prompt: string;
  attached_entities: DiscussionEntityRef[];
  context_bundle: DiscussionContextBundle | null;
  latest_import: DiscussionImportRecord | null;
  machine_distilled: DiscussionDistillation | null;
  adopted_decision: DiscussionDistillation | null;
  coverage_report: DiscussionCoverage | null;
  promoted_record_ids: Record<string, string[]>;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type RunEvent = {
  event_id: number;
  project_id: string;
  task_id: string | null;
  run_id: string | null;
  event_type: string;
  message: string;
  payload: Record<string, unknown>;
  created_at: string;
};

export type FlowSnapshot = {
  stage: string;
  status: string;
  decision: string;
  checkpoint_required: boolean;
  active_task_id: string | null;
  rollback_stage: string | null;
  note: string;
  updated_at: string;
  available_actions: string[];
  history: Array<Record<string, unknown>>;
};

export type BranchRunSummary = {
  run_id: string;
  status: string;
  branch_name: string | null;
  primary_metric: string | null;
  primary_value: number | null;
  metrics: Record<string, number>;
  source_task_id: string | null;
};

export type BranchComparison = {
  project_id: string;
  metric_keys: string[];
  branches: BranchRunSummary[];
};

export type ArtifactDetail = Artifact & {
  resolved_path: string;
  workspace_relative_path: string | null;
  exists_on_disk: boolean;
  related_verifications: Verification[];
  related_audit_entries: AuditEntry[];
  evidence_refs: string[];
  annotations: Array<{
    annotation_id: string;
    operator: string;
    status: string;
    review_tags: string[];
    note: string;
    created_at: string;
  }>;
  provenance: {
    claim_support_refs: Array<{
      claim_id: string;
      support_kind: string;
      support_value: string;
    }>;
  };
};
