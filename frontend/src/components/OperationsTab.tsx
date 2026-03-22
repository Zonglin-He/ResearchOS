import { useMemo, useState } from "react";
import { FileCheck2, Hand, PlayCircle, Route, ShieldAlert, Sparkles, Square, Undo2 } from "lucide-react";
import type {
  Approval,
  AuditReport,
  Claim,
  ProviderHealthSnapshot,
  RoutingInspection,
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
  cancelTask: (taskId: string) => Promise<unknown>;
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
      <Panel title="操作导航" subtitle="先处理排队和阻塞任务，再看路由、审批和 provider 状态。">
        <div className="ops-guide-grid">
          <GuideCard title="先调度" body={`当前有 ${queuedCount} 个排队任务。`} tone="blue" />
          <GuideCard title="先排障" body={`当前有 ${blockedCount} 个阻塞、失败或待审批任务。`} tone="orange" />
          <GuideCard title="看运行" body={`当前有 ${runningCount} 个运行中任务。`} tone="green" />
        </div>
      </Panel>

      <Panel title="待审批" subtitle="支持通过、拒绝和带条件通过，不再回到高级表单里补。">
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
                        {approval.approval_id} · {approval.target_id}
                      </small>
                    </div>
                    <StatusPill value="waiting_approval" />
                  </div>
                  <div className="approval-meta">
                    <span>提交人：{approval.approved_by || "operator"}</span>
                    <span>截止：{approval.due_at ? approval.due_at.replace("T", " ").slice(0, 16) : "未设置"}</span>
                  </div>
                  <div className="approval-context">
                    <strong>上下文</strong>
                    <p>{approval.context_summary || "当前没有额外上下文摘要。"}</p>
                  </div>
                  <div className="approval-context">
                    <strong>推荐动作</strong>
                    <p>{approval.recommended_action || "当前没有推荐动作。"}</p>
                  </div>
                  <label>
                    审批人
                    <input
                      value={draft.approvedBy}
                      onChange={(event) => updateDraft(approval.approval_id, { approvedBy: event.target.value })}
                    />
                  </label>
                  <label>
                    备注
                    <textarea
                      value={draft.comment}
                      onChange={(event) => updateDraft(approval.approval_id, { comment: event.target.value })}
                      placeholder="可写通过原因、驳回原因或额外说明。"
                    />
                  </label>
                  <label>
                    条件通过附加条件
                    <textarea
                      value={draft.conditionText}
                      onChange={(event) => updateDraft(approval.approval_id, { conditionText: event.target.value })}
                      placeholder="例如：重点对比 FGSM 而非 PGD；限制显存不超过 12GB。"
                    />
                  </label>
                  <div className="approval-decision-row">
                    <button
                      className="button tiny"
                      type="button"
                      onClick={() => void submitApproval(approval, "approved")}
                      disabled={props.isBusy(`approval-${approval.approval_id}-approved`)}
                    >
                      通过
                    </button>
                    <button
                      className="button tiny secondary"
                      type="button"
                      onClick={() => void submitApproval(approval, "approved_with_conditions")}
                      disabled={!draft.conditionText.trim() || props.isBusy(`approval-${approval.approval_id}-approved_with_conditions`)}
                    >
                      带条件通过
                    </button>
                    <button
                      className="button tiny ghost"
                      type="button"
                      onClick={() => void submitApproval(approval, "rejected")}
                      disabled={props.isBusy(`approval-${approval.approval_id}-rejected`)}
                    >
                      拒绝
                    </button>
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <EmptyState title="当前没有待审批项" body="一旦流程进入待审批状态，这里会直接给出上下文和操作按钮。" />
        )}
      </Panel>

      <Panel title="任务控制台" subtitle="按时间倒序显示任务。人工节点不会再显示自动调度按钮。">
        {props.projectTasks.length ? (
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>任务</th>
                  <th>类型</th>
                  <th>状态</th>
                  <th>负责人</th>
                  <th>操作</th>
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
                            <button className="button tiny" onClick={() => props.openHumanSelect(task)}>
                              <Hand size={14} />
                              人工决策
                            </button>
                          ) : (
                            <button
                              className="button tiny"
                              onClick={() =>
                                void props.runAction(`dispatch-${task.task_id}`, () => props.dispatchTask(task.task_id))
                              }
                              disabled={props.isBusy(`dispatch-${task.task_id}`)}
                            >
                              <PlayCircle size={14} />
                              调度
                            </button>
                          )}
                          <button
                            className="button tiny secondary"
                            onClick={() => void props.runAction(`retry-${task.task_id}`, () => props.retryTask(task.task_id))}
                            disabled={props.isBusy(`retry-${task.task_id}`)}
                          >
                            <Undo2 size={14} />
                            重试
                          </button>
                          <button
                            className="button tiny ghost"
                            onClick={() => void props.runAction(`cancel-${task.task_id}`, () => props.cancelTask(task.task_id))}
                            disabled={props.isBusy(`cancel-${task.task_id}`)}
                          >
                            <Square size={14} />
                            取消
                          </button>
                          <button
                            className="button tiny ghost"
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
                            路由
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="当前没有任务" body="先去创建项目或让研究台自动生成任务。" />
        )}
      </Panel>

      <Panel title="Provider 控制" subtitle="启用、停用和清理冷却都放在这里。">
        <div className="provider-list">
          {props.providers.map((provider) => (
            <div key={provider.provider_family} className="provider-row control">
              <div>
                <strong>{provider.provider_family}</strong>
                <small>
                  cli={String(provider.cli_installed)} | cooldown={provider.cooldown_seconds_remaining}s
                </small>
                <p>{provider.detail || "当前状态正常。"}</p>
              </div>
              <div className="provider-actions">
                <StatusPill value={provider.state} />
                <button
                  className="button tiny"
                  onClick={() =>
                    void props.runAction(`probe-${provider.provider_family}`, () =>
                      props.probeProvider(provider.provider_family),
                    )
                  }
                >
                  探测
                </button>
                <button
                  className="button tiny secondary"
                  onClick={() =>
                    void props.runAction(`disable-${provider.provider_family}`, () =>
                      props.disableProvider(provider.provider_family),
                    )
                  }
                >
                  停用
                </button>
                <button
                  className="button tiny secondary"
                  onClick={() =>
                    void props.runAction(`enable-${provider.provider_family}`, () =>
                      props.enableProvider(provider.provider_family),
                    )
                  }
                >
                  启用
                </button>
                <button
                  className="button tiny ghost"
                  onClick={() =>
                    void props.runAction(`cooldown-${provider.provider_family}`, () =>
                      props.clearCooldown(provider.provider_family),
                    )
                  }
                >
                  清空冷却
                </button>
              </div>
            </div>
          ))}
        </div>
      </Panel>

      <Panel title="验证入口" subtitle="Claim 验证和 Run 审计分开列出，方便排查。">
        <div className="double-form">
          <div className="table-card">
            <table>
              <thead>
                <tr>
                  <th>Claim</th>
                  <th>类型</th>
                  <th>风险</th>
                  <th>操作</th>
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
                        onClick={() =>
                          void props.runAction(`verify-claim-${claim.claim_id}`, () => props.verifyClaim(claim.claim_id))
                        }
                      >
                        <FileCheck2 size={14} />
                        验证
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
                  <th>状态</th>
                  <th>GPU</th>
                  <th>操作</th>
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
                          onClick={() => void props.runAction(`verify-run-${run.run_id}`, () => props.verifyRun(run.run_id))}
                        >
                          <FileCheck2 size={14} />
                          验证
                        </button>
                        <button
                          className="button tiny secondary"
                          onClick={() =>
                            void props.runAction(
                              `audit-run-${run.run_id}`,
                              async () => props.setSelectedRunAudit(await props.loadRunAudit(run.run_id)),
                              false,
                            )
                          }
                        >
                          <ShieldAlert size={14} />
                          审计
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

      <Panel title="检查结果" subtitle="这里显示任务路由和 Run 审计结果。">
        <div className="stack-md">
          {props.routingPreview ? (
            <div className="inspect-card">
              <div className="inspect-title">
                <Route size={16} />
                <strong>路由预览：{props.routingPreview.subject_id ?? "system"}</strong>
              </div>
              <KeyValue label="Provider" value={props.routingPreview.resolved_dispatch.provider_name} />
              <KeyValue label="模型" value={props.routingPreview.resolved_dispatch.model ?? "<default>"} />
              <KeyValue label="Fallback" value={props.routingPreview.resolved_dispatch.fallback_reason ?? "无"} />
              <KeyValue label="决策原因" value={props.routingPreview.resolved_dispatch.decision_reason ?? "system_default"} />
            </div>
          ) : null}

          {props.selectedRunAudit ? (
            <div className="inspect-card">
              <div className="inspect-title">
                <ShieldAlert size={16} />
                <strong>Run 审计：{props.selectedRunAudit.status}</strong>
              </div>
              <p>{props.selectedRunAudit.findings.join(" | ") || "没有发现问题。"}</p>
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
            <EmptyState title="还没有检查结果" body="点击任务路由或 Run 审计后，这里会显示详情。" />
          ) : (
            <div className="inspect-card inspect-tip">
              <div className="inspect-title">
                <Sparkles size={16} />
                <strong>使用建议</strong>
              </div>
              <p>先看任务是否路由到了正确 provider，再看审计结果，排查会更快。</p>
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
