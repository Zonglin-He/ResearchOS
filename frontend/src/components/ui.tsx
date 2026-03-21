import type { ReactNode } from "react";

export function Panel(props: {
  title?: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`panel ${props.className ?? ""}`.trim()}>
      {(props.title || props.action) && (
        <div className="panel-head">
          <div>
            {props.title ? <h3>{props.title}</h3> : null}
            {props.subtitle ? <p>{props.subtitle}</p> : null}
          </div>
          {props.action ? <div>{props.action}</div> : null}
        </div>
      )}
      {props.children}
    </section>
  );
}

export function StatCard(props: { label: string; value: string | number; meta?: string }) {
  return (
    <div className="stat-card">
      <span>{props.label}</span>
      <strong>{props.value}</strong>
      {props.meta ? <small>{props.meta}</small> : null}
    </div>
  );
}

export function StatusPill(props: { value: string }) {
  return <span className={`status-pill status-${toStatusClass(props.value)}`}>{translateStatus(props.value)}</span>;
}

export function EmptyState(props: { title: string; body: string }) {
  return (
    <div className="empty-state">
      <strong>{props.title}</strong>
      <p>{props.body}</p>
    </div>
  );
}

export function KeyValue(props: { label: string; value: ReactNode }) {
  return (
    <div className="kv-row">
      <span>{props.label}</span>
      <div>{props.value}</div>
    </div>
  );
}

function toStatusClass(value: string): string {
  const normalized = value.toLowerCase().replace(/[\s_]+/g, "-");

  if (
    normalized.includes("succeeded") ||
    normalized.includes("done") ||
    normalized.includes("approved") ||
    normalized.includes("supported") ||
    normalized.includes("available")
  ) {
    return "good";
  }
  if (
    normalized.includes("failed") ||
    normalized.includes("blocked") ||
    normalized.includes("cancelled") ||
    normalized.includes("contradicted") ||
    normalized.includes("unhealthy")
  ) {
    return "bad";
  }
  if (
    normalized.includes("running") ||
    normalized.includes("review") ||
    normalized.includes("waiting") ||
    normalized.includes("queued") ||
    normalized.includes("rate") ||
    normalized.includes("degraded") ||
    normalized.includes("exhausted")
  ) {
    return "warn";
  }
  return "neutral";
}

function translateStatus(value: string): string {
  const normalized = value.toLowerCase().replace(/[\s_]+/g, "-");
  const map: Record<string, string> = {
    idle: "空闲",
    running: "运行中",
    blocked: "阻塞",
    review: "复核中",
    done: "完成",
    queued: "排队中",
    "waiting-approval": "待审批",
    succeeded: "已完成",
    failed: "失败",
    cancelled: "已取消",
    approved: "已批准",
    supported: "已支持",
    available: "可用",
    unhealthy: "异常",
    degraded: "降级",
    exhausted: "额度耗尽",
    contradicted: "被否定",
    "needs-review": "需复核",
    active: "启用",
    missing: "缺失",
  };

  return map[normalized] ?? value;
}
