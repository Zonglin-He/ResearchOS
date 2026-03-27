import { useMemo, useState } from "react";
import { FileCheck2, Hand, PlayCircle, Route, ShieldAlert, Sparkles, Square, Undo2 } from "lucide-react";
import type {
  Approval,
  AuditReport,
  BranchComparison,
  Claim,
  FlowSnapshot,
  ProjectDashboard,
  ProviderHealthSnapshot,
  RoutingInspection,
  RunEvent,
  RunManifest,
  Task,
} from "../api";
import { EmptyState, KeyValue, Panel, StatusPill } from "./ui";

type Props = {
  projectTasks: Task[];
  projectRuns: RunManifest[];
  claims: Claim[];
  approvals: Approval[];
  providers: ProviderHealthSnapshot[];
  projectDashboard: ProjectDashboard | null;
  flowSnapshot: FlowSnapshot | null;
  recentEvents: RunEvent[];
  branchComparison: BranchComparison | null;
  routingPreview: RoutingInspection | null;
  selectedRunAudit: AuditReport | null;
  runAction: (key: string, callback: () => Promise<unknown>, refresh?: boolean) => Promise<void>;
  isBusy: (key: string) => boolean;
  setRoutingPreview: (inspection: RoutingInspection | null) => void;
  setSelectedRunAudit: (report: AuditReport | null) => void;
  loadTaskRouting: (taskId: string) => Promise<RoutingInspection>;
  loadRunAudit: (runId: string) => Promise<AuditReport>;
  dispatchTask: (taskId: string) => Promise<unknown>;
  retryTask: (taskId: string) => Promise<unknown>;
  resumeTask: (taskId: string) => Promise<unknown>;
  cancelTask: (taskId: string) => Promise<unknown>;
  transitionFlow: (action: string, payload: unknown) => Promise<unknown>;
  disableProvider: (provider: string) => Promise<unknown>;
  enableProvider: (provider: string) => Promise<unknown>;
  clearCooldown: (provider: string) => Promise<unknown>;
  probeProvider: (provider: string) => Promise<unknown>;
  verifyClaim: (claimId: string) => Promise<unknown>;
  verifyRun: (runId: string) => Promise<unknown>;
  createApproval: (payload: unknown) => Promise<unknown>;
  openHumanSelect: (task: Task) => void;
};

type ApprovalDraft = {
  approvedBy: string;
  comment: string;
  conditionText: string;
};

export function OperationsTab(props: Props) {
  const [approvalDrafts, setApprovalDrafts] = useState<Record<string, ApprovalDraft>>({});

  const blockedCount = props.projectTasks.filter((task) =>
    ["blocked", "failed", "waiting_approval"].includes(task.status),
  ).length;
  const queuedCount = props.projectTasks.filter((task) => task.status === "queued").length;
  const runningCount = props.projectTasks.filter((task) => task.status === "running").length;
  const pendingApprovals = useMemo(
    () => props.approvals.filter((approval) => approval.decision === "pending"),
    [props.approvals],
  );

  function getDraft(approval: Approval): ApprovalDraft {
    return (
      approvalDrafts[approval.approval_id] ?? {
        approvedBy: approval.approved_by || "operator",
        comment: approval.comment || "",
        conditionText: approval.condition_text || "",
      }
    );
  }

  function updateDraft(approvalId: string, patch: Partial<ApprovalDraft>) {
    setApprovalDrafts((current) => ({
      ...current,
      [approvalId]: {
        ...(current[approvalId] ?? { approvedBy: "operator", comment: "", conditionText: "" }),
        ...patch,
      },
    }));
  }

  async function submitApproval(approval: Approval, decision: "approved" | "rejected" | "approved_with_conditions") {
    const draft = getDraft(approval);
    await props.runAction(`approval-${approval.approval_id}-${decision}`, () =>
      props.createApproval({
        approval_id: approval.approval_id,
        project_id: approval.project_id,
        target_type: approval.target_type,
        target_id: approval.target_id,
        approved_by: draft.approvedBy || "operator",
        decision,
        comment: draft.comment,
        condition_text: decision === "approved_with_conditions" ? draft.conditionText : "",
        context_summary: approval.context_summary,
        recommended_action: approval.recommended_action,
        due_at: approval.due_at,
      }),
    );
  }

  return (
    <div className="content-grid operations-grid">
      <Panel title="Control Guide" subtitle="Read flow status first, then unblock tasks, approvals, and providers.">
        <div className="ops-guide-grid">
          <GuideCard title="Queued" body={`${queuedCount} task(s) ready to dispatch.`} tone="blue" />
          <GuideCard title="Blocked" body={`${blockedCount} task(s) need operator attention.`} tone="orange" />
          <GuideCard title="Running" body={`${runningCount} task(s) are still executing.`} tone="green" />
        </div>
      </Panel>

      <Panel title="Flow Snapshot" subtitle="Project-level typed state machine with pause, resume, retry, pivot, and refine controls.">
        {props.flowSnapshot ? (
          <div className="stack-md">
            <div className="inspect-card">
              <KeyValue label="Stage" value={props.flowSnapshot.stage} />
              <KeyValue label="Status" value={props.flowSnapshot.status} />
              <KeyValue label="Decision" value={props.flowSnapshot.decision} />
              <KeyValue label="Checkpoint" value={props.flowSnapshot.checkpoint_required ? "required" : "optional"} />
              <KeyValue label="Active Task" value={props.flowSnapshot.active_task_id ?? "<none>"} />
              <KeyValue label="Rollback" value={props.flowSnapshot.rollback_stage ?? "<none>"} />
              <KeyValue label="Recommended Task" value={props.projectDashboard?.recommended_next_task_kind ?? "<none>"} />
            </div>
            <div className="button-row">
              {props.flowSnapshot.available_actions.map((action) => (
                <button
                  key={action}
                  className="button tiny secondary"
                  type="button"
                  onClick={() =>
                    void props.runAction(`flow-${action}`, () =>
                      props.transitionFlow(action, {
                        task_id: props.flowSnapshot?.active_task_id,
                        stage: props.flowSnapshot?.stage,
                        note: `operator flow action: ${action}`,
                      }),
                    )
                  }
                  disabled={props.isBusy(`flow-${action}`)}
                >
                  {action}
                </button>
              ))}
            </div>
            {props.flowSnapshot.history.length ? (
              <div className="inspect-card">
                <div className="inspect-title">
                  <Sparkles size={16} />
                  <strong>Recent transitions</strong>
                </div>
                <ul className="plain-list">
                  {props.flowSnapshot.history
                    .slice(-5)
                    .reverse()
                    .map((entry, index) => (
                      <li key={`${String(entry.created_at ?? index)}-${index}`}>
                        {String(entry.event ?? "event")} | {String(entry.stage ?? "stage")} | {String(entry.status ?? "status")}
                      </li>
                    ))}
                </ul>
              </div>
            ) : null}
          </div>
        ) : (
          <EmptyState title="No flow snapshot yet" body="The backend will expose the current research flow state here once the project is initialized." />
        )}
      </Panel>

      <Panel title="Pending Approvals" subtitle="Approve, reject, or approve with conditions without leaving the operator console.">
        {pendingApprovals.length ? (
          <div className="approval-stack">
            {pendingApprovals.map((approval) => {
              const draft = getDraft(approval);
              return (
                <article key={approval.approval_id} className="approval-card">
                  <div className="approval-card-head">
                    <div>
                      <strong>{approval.target_type}</strong>
                      <small>
                        {approval.approval_id} | {approval.target_id}
                      </small>
                    </div>
                    <StatusPill value="waiting_approval" />
                  </div>
                  <div className="approval-meta">
                    <span>Owner: {approval.approved_by || "operator"}</span>
                    <span>Due: {approval.due_at ? approval.due_at.replace("T", " ").slice(0, 16) : "not set"}</span>
                  </div>
                  <div className="approval-context">
                    <strong>Context</strong>
                    <p>{approval.context_summary || "No context summary."}</p>
                  </div>
                  <div className="approval-context">
                    <strong>Recommended action</strong>
                    <p>{approval.recommended_action || "No recommendation."}</p>
                  </div>
                  <label>
                    Reviewer
                    <input
                      value={draft.approvedBy}
                      onChange={(event) => updateDraft(approval.approval_id, { approvedBy: event.target.value })}
                    />
                  </label>
                  <label>
                    Comment
                    <textarea
                      value={draft.comment}
                      onChange={(event) => updateDraft(approval.approval_id, { comment: event.target.value })}
                    />
                  </label>
                  <label>
                    Conditions
                    <textarea
                      value={draft.conditionText}
                      onChange={(event) => updateDraft(approval.approval_id, { conditionText: event.target.value })}
                    />
                  </label>
                  <div className="approval-decision-row">
                    <button
                      className="button tiny"
                      type="button"
                      onClick={() => void submitApproval(approval, "approved")}
                      disabled={props.isBusy(`approval-${approval.approval_id}-approved`)}
                    >
                      Approve
                    </button>
                    <button
                      className="button tiny secondary"
                      type="button"
                      onClick={() => void submitApproval(approval, "approved_with_conditions")}
                      disabled={!draft.conditionText.trim() || props.isBusy(`approval-${approval.approval_id}-approved_with_conditions`)}
                    >
                      Approve with conditions
                    </button>
                    <button
                      className="button tiny ghost"
                      type="button"
                      onClick={() => void submitApproval(approval, "rejected")}
                      disabled={props.isBusy(`approval-${approval.approval_id}-rejected`)}
                    >
                      Reject
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState title="No pending approvals" body="Approval requests will appear here when the flow enters a human gate." />
        )}
      </Panel>

      <Panel title="Task Control" subtitle="Dispatch, retry, resume from checkpoint, cancel, or inspect routing for each task.">
        {props.projectTasks.length ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Task</th>
                  <th>Kind</th>
                  <th>Status</th>
                  <th>Owner</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {props.projectTasks
                  .slice()
                  .sort((left, right) => right.created_at.localeCompare(left.created_at))
                  .map((task) => (
                    <tr key={task.task_id}>
                      <td>
                        <strong>{task.task_id}</strong>
                        <small>{task.goal}</small>
                      </td>
                      <td>{task.kind}</td>
                      <td>
                        <StatusPill value={task.status} />
                      </td>
                      <td>{task.owner}</td>
                      <td>
                        <div className="button-row">
                          {task.kind === "human_select" ? (
                            <button className="button tiny" type="button" onClick={() => props.openHumanSelect(task)}>
                              <Hand size={14} />
                              Human select
                            </button>
                          ) : (
                            <button
                              className="button tiny"
                              type="button"
                              onClick={() =>
                                void props.runAction(`dispatch-${task.task_id}`, () => props.dispatchTask(task.task_id))
                              }
                              disabled={props.isBusy(`dispatch-${task.task_id}`)}
                            >
                              <PlayCircle size={14} />
                              Dispatch
                            </button>
                          )}
                          <button
                            className="button tiny secondary"
                            type="button"
                            onClick={() => void props.runAction(`retry-${task.task_id}`, () => props.retryTask(task.task_id))}
                            disabled={props.isBusy(`retry-${task.task_id}`)}
                          >
                            <Undo2 size={14} />
                            Retry
                          </button>
                          <button
                            className="button tiny secondary"
                            type="button"
                            onClick={() => void props.runAction(`resume-${task.task_id}`, () => props.resumeTask(task.task_id))}
                            disabled={!task.checkpoint_path || props.isBusy(`resume-${task.task_id}`)}
                          >
                            <PlayCircle size={14} />
                            Resume
                          </button>
                          <button
                            className="button tiny ghost"
                            type="button"
                            onClick={() => void props.runAction(`cancel-${task.task_id}`, () => props.cancelTask(task.task_id))}
                            disabled={props.isBusy(`cancel-${task.task_id}`)}
                          >
                            <Square size={14} />
                            Cancel
                          </button>
                          <button
                            className="button tiny ghost"
                            type="button"
                            onClick={() =>
                              void props.runAction(
                                `routing-${task.task_id}`,
                                async () => props.setRoutingPreview(await props.loadTaskRouting(task.task_id)),
                                false,
                              )
                            }
                            disabled={props.isBusy(`routing-${task.task_id}`)}
                          >
                            <Route size={14} />
                            Routing
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No tasks" body="Create or guide a project first so the control plane has something to operate on." />
        )}
      </Panel>

      <Panel title="Recent Events" subtitle="Realtime run events, checkpoint saves, and operator-visible state changes.">
        {props.recentEvents.length ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Type</th>
                  <th>Task</th>
                  <th>Message</th>
                </tr>
              </thead>
              <tbody>
                {props.recentEvents
                  .slice()
                  .sort((left, right) => right.created_at.localeCompare(left.created_at))
                  .slice(0, 10)
                  .map((event) => (
                    <tr key={event.event_id}>
                      <td>{event.created_at.replace("T", " ").slice(0, 19)}</td>
                      <td>{event.event_type}</td>
                      <td>{event.task_id ?? "-"}</td>
                      <td>{event.message}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No recent events" body="Task dispatches and checkpoints will populate the event feed." />
        )}
      </Panel>

      <Panel title="Branch Compare" subtitle="Compare experimental branches by primary metric and supporting run metrics.">
        {props.branchComparison?.branches.length ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Branch</th>
                  <th>Run</th>
                  <th>Status</th>
                  <th>Primary</th>
                  <th>Metrics</th>
                </tr>
              </thead>
              <tbody>
                {props.branchComparison.branches.map((branch) => (
                  <tr key={branch.run_id}>
                    <td>{branch.branch_name ?? "-"}</td>
                    <td>
                      <strong>{branch.run_id}</strong>
                      <small>{branch.source_task_id ?? ""}</small>
                    </td>
                    <td>{branch.status}</td>
                    <td>
                      {branch.primary_metric ? `${branch.primary_metric}: ${String(branch.primary_value ?? "")}` : "-"}
                    </td>
                    <td>
                      {Object.entries(branch.metrics)
                        .slice(0, 4)
                        .map(([key, value]) => `${key}=${value}`)
                        .join(" | ") || "-"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No branch comparison yet" body="Run multiple branches and their metrics will appear here." />
        )}
      </Panel>

      <Panel title="Provider Control" subtitle="Probe, disable, enable, or clear cooldowns across provider families.">
        <div className="provider-list">
          {props.providers.map((provider) => (
            <div key={provider.provider_family} className="provider-row control">
              <div>
                <strong>{provider.provider_family}</strong>
                <small>
                  cli={String(provider.cli_installed)} | cooldown={provider.cooldown_seconds_remaining}s
                </small>
                <p>{provider.detail || "healthy"}</p>
              </div>
              <div className="provider-actions">
                <StatusPill value={provider.state} />
                <button
                  className="button tiny"
                  type="button"
                  onClick={() =>
                    void props.runAction(`probe-${provider.provider_family}`, () =>
                      props.probeProvider(provider.provider_family),
                    )
                  }
                >
                  Probe
                </button>
                <button
                  className="button tiny secondary"
                  type="button"
                  onClick={() =>
                    void props.runAction(`disable-${provider.provider_family}`, () =>
                      props.disableProvider(provider.provider_family),
                    )
                  }
                >
                  Disable
                </button>
                <button
                  className="button tiny secondary"
                  type="button"
                  onClick={() =>
                    void props.runAction(`enable-${provider.provider_family}`, () =>
                      props.enableProvider(provider.provider_family),
                    )
                  }
                >
                  Enable
                </button>
                <button
                  className="button tiny ghost"
                  type="button"
                  onClick={() =>
                    void props.runAction(`cooldown-${provider.provider_family}`, () =>
                      props.clearCooldown(provider.provider_family),
                    )
                  }
                >
                  Clear cooldown
                </button>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="Verification Entry" subtitle="Trigger claim verification and run audit directly from the operator console.">
        <div className="double-form">
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Claim</th>
                  <th>Type</th>
                  <th>Risk</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {props.claims.slice(0, 8).map((claim) => (
                  <tr key={claim.claim_id}>
                    <td>
                      <strong>{claim.claim_id}</strong>
                      <small>{claim.text}</small>
                    </td>
                    <td>{claim.claim_type}</td>
                    <td>{claim.risk_level}</td>
                    <td>
                      <button
                        className="button tiny"
                        type="button"
                        onClick={() =>
                          void props.runAction(`verify-claim-${claim.claim_id}`, () => props.verifyClaim(claim.claim_id))
                        }
                      >
                        <FileCheck2 size={14} />
                        Verify
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Run</th>
                  <th>Status</th>
                  <th>GPU</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {props.projectRuns.slice(0, 8).map((run) => (
                  <tr key={run.run_id}>
                    <td>
                      <strong>{run.run_id}</strong>
                      <small>{run.spec_id}</small>
                    </td>
                    <td>
                      <StatusPill value={run.status} />
                    </td>
                    <td>{run.gpu}</td>
                    <td>
                      <div className="button-row">
                        <button
                          className="button tiny"
                          type="button"
                          onClick={() => void props.runAction(`verify-run-${run.run_id}`, () => props.verifyRun(run.run_id))}
                        >
                          <FileCheck2 size={14} />
                          Verify
                        </button>
                        <button
                          className="button tiny secondary"
                          type="button"
                          onClick={() =>
                            void props.runAction(
                              `audit-run-${run.run_id}`,
                              async () => props.setSelectedRunAudit(await props.loadRunAudit(run.run_id)),
                              false,
                            )
                          }
                        >
                          <ShieldAlert size={14} />
                          Audit
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </Panel>

      <Panel title="Inspection Results" subtitle="Read routing decisions and audit findings in one place.">
        <div className="stack-md">
          {props.routingPreview ? (
            <div className="inspect-card">
              <div className="inspect-title">
                <Route size={16} />
                <strong>Routing preview: {props.routingPreview.subject_id ?? "system"}</strong>
              </div>
              <KeyValue label="Provider" value={props.routingPreview.resolved_dispatch.provider_name} />
              <KeyValue label="Model" value={props.routingPreview.resolved_dispatch.model ?? "<default>"} />
              <KeyValue label="Fallback" value={props.routingPreview.resolved_dispatch.fallback_reason ?? "none"} />
              <KeyValue label="Decision" value={props.routingPreview.resolved_dispatch.decision_reason ?? "system_default"} />
            </div>
          ) : null}

          {props.selectedRunAudit ? (
            <div className="inspect-card">
              <div className="inspect-title">
                <ShieldAlert size={16} />
                <strong>Run audit: {props.selectedRunAudit.status}</strong>
              </div>
              <p>{props.selectedRunAudit.findings.join(" | ") || "No findings."}</p>
              <ul className="plain-list">
                {props.selectedRunAudit.entries.slice(0, 5).map((entry) => (
                  <li key={entry.entry_id}>
                    {entry.category}: {entry.rationale}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}

          {!props.routingPreview && !props.selectedRunAudit ? (
            <EmptyState title="No inspection results" body="Inspect routing or audit a run to populate this area." />
          ) : (
            <div className="inspect-card inspect-tip">
              <div className="inspect-title">
                <Sparkles size={16} />
                <strong>Operator hint</strong>
              </div>
              <p>Read routing first, then audit findings, then branch comparison. That gives the shortest path to a justified intervention.</p>
            </div>
          )}
        </div>
      </Panel>
    </div>
  );
}

function GuideCard(props: { title: string; body: string; tone: "blue" | "orange" | "green" }) {
  return (
    <div className={`guide-card guide-${props.tone}`}>
      <strong>{props.title}</strong>
      <p>{props.body}</p>
    </div>
  );
}
