import { useMemo, useState, type CSSProperties } from "react";
import { AlertTriangle, CheckCircle2, Clock3, Sparkles, Users2 } from "lucide-react";
import type { ProjectDashboard, Task } from "../api";
import { roleLanes } from "../utils";
import { EmptyState, KeyValue, StatusPill } from "./ui";

type Props = {
  projectTasks: Task[];
  projectDashboard: ProjectDashboard | null;
};

type StationState = "idle" | "running" | "blocked" | "review" | "done";

type StationLayout = {
  id: string;
  x: string;
  y: string;
  short: string;
  accent: string;
  shared?: boolean;
  sign?: string;
};

const stationLayout: StationLayout[] = [
  { id: "librarian", x: "10%", y: "15%", short: "收录台", accent: "#6e89ff", sign: "资料入口" },
  { id: "synthesizer", x: "68%", y: "18%", short: "综合台", accent: "#69d5aa", sign: "Gap 墙" },
  { id: "builder", x: "17%", y: "63%", short: "实验台", accent: "#f2b14d", shared: true, sign: "Builder" },
  { id: "review", x: "78%", y: "63%", short: "复核台", accent: "#ff8d74", sign: "Review" },
  { id: "publish", x: "84%", y: "33%", short: "写作台", accent: "#9ec8ff", shared: true, sign: "稿件角" },
  { id: "archive", x: "48%", y: "83%", short: "档案角", accent: "#ccb48d", sign: "归档" },
];

export function PixelStudio(props: Props) {
  const [selectedId, setSelectedId] = useState<string>("builder");

  const stationData = useMemo(() => {
    return stationLayout.map((layout) => {
      const lane = roleLanes.find((item) => item.id === layout.id)!;
      const tasks = props.projectTasks.filter((task) => lane.taskKinds.includes(task.kind));
      const state = deriveState(tasks);
      return {
        ...layout,
        lane,
        tasks,
        state,
      };
    });
  }, [props.projectTasks]);

  const selected = stationData.find((item) => item.id === selectedId) ?? stationData[0];

  return (
    <div className="pixel-studio-shell">
      <div className="pixel-scene-panel">
        <div className="pixel-scene-head">
          <div>
            <div className="pixel-label">工位总览</div>
            <h2>ResearchOS 研究楼层</h2>
            <p>点击工位查看任务、状态和下一步。运行中的角色会在楼层里做自己的专属动作。</p>
          </div>
          <div className="pixel-chip-row">
            <span className={props.projectDashboard?.topic_freeze_present ? "freeze active" : "freeze"}>主题冻结</span>
            <span className={props.projectDashboard?.spec_freeze_present ? "freeze active" : "freeze"}>规格冻结</span>
            <span className={props.projectDashboard?.results_freeze_present ? "freeze active" : "freeze"}>结果冻结</span>
          </div>
        </div>

        <div className="pixel-scene">
          <div className="pixel-scene-sky" />
          <div className="pixel-mountain pixel-mountain-left" />
          <div className="pixel-mountain pixel-mountain-right" />
          <div className="pixel-window pixel-window-left" />
          <div className="pixel-window pixel-window-right" />
          <div className="pixel-rug pixel-rug-main" />
          <div className="pixel-rug pixel-rug-side" />
          <div className="pixel-rug pixel-rug-entry" />
          <div className="pixel-round-table" />
          <div className="pixel-water" />
          <div className="pixel-sign pixel-main-sign">ResearchOS</div>
          <div className="pixel-software-shelf">
            <span>代码</span>
            <span>文档</span>
          </div>
          <div className="pixel-bookshelf" />
          <div className="pixel-cabinet" />
          <div className="pixel-bulletin-board">
            <span>今日研究</span>
          </div>
          <div className="pixel-lamp" />
          <div className="pixel-crate" />

          <div className="pixel-plant pixel-plant-left" />
          <div className="pixel-plant pixel-plant-right" />
          <div className="pixel-plant pixel-plant-bottom" />
          <div className="pixel-flower pixel-flower-a" />
          <div className="pixel-flower pixel-flower-b" />

          <div className="pixel-path pixel-path-a" />
          <div className="pixel-path pixel-path-b" />
          <div className="pixel-path pixel-path-c" />
          <div className="pixel-path pixel-path-d" />
          <div className="pixel-footsteps pixel-footsteps-a" />
          <div className="pixel-footsteps pixel-footsteps-b" />
          <div className="pixel-footsteps pixel-footsteps-c" />

          {stationData.map((station) => (
            <div key={station.id} className="pixel-station-wrap" style={{ left: station.x, top: station.y } as CSSProperties}>
              {station.sign ? <div className="pixel-sign pixel-station-sign">{station.sign}</div> : null}

              <button
                className={`pixel-station pixel-${station.state} ${selected.id === station.id ? "selected" : ""}`}
                onClick={() => setSelectedId(station.id)}
              >
                <div className="pixel-station-frame">
                  <div className="pixel-desk-tag">{station.short}</div>
                  <div className="pixel-monitor" />
                  <div className={`pixel-role-prop pixel-role-prop-${station.id}`} />
                  <div className={`pixel-work-effect pixel-work-effect-${station.id} pixel-work-effect-${station.state}`} />
                  <div className={`pixel-worker pixel-worker-${station.id} pixel-worker-${station.state}`}>
                    <div className="pixel-head" />
                    <div className="pixel-body" style={{ background: station.accent }} />
                  </div>
                  <div className="pixel-sparkle pixel-sparkle-a" />
                  <div className="pixel-sparkle pixel-sparkle-b" />
                  <div className="pixel-station-name">{station.lane.label}</div>
                  <div className="pixel-state-badge">
                    <StatusPill value={station.state} />
                  </div>
                  {station.shared ? <div className="pixel-shared-badge">共享工位</div> : null}
                </div>
              </button>
            </div>
          ))}

          {selected.shared ? (
            <div className="pixel-agent-overlay">
              <div className="pixel-agent-overlay-head">
                <Users2 size={16} />
                <strong>共享智能体层</strong>
              </div>
              <p>{selected.lane.sharedCrew?.join(" / ") || "多个角色"} 共用这片区域，适合高频切换实验与写作。</p>
            </div>
          ) : null}
        </div>
      </div>

      <div className="pixel-inspector-panel pixel-inspector-pixel">
        <div className="pixel-inspector-head">
          <div>
            <div className="pixel-label">工位面板</div>
            <h3>{selected.lane.label}</h3>
          </div>
          <StatusPill value={selected.state} />
        </div>

        <div className="pixel-inspector-screen">
          <div className="pixel-inspector-grid">
            <KeyValue label="职责说明" value={selected.lane.mission} />
            <KeyValue label="主要输出" value={selected.lane.output} />
            <KeyValue label="任务类型" value={selected.lane.taskKinds.join(" / ")} />
            <KeyValue label="场景提示" value={selected.lane.workspaceNote} />
            <KeyValue label="家具道具" value={selected.lane.propHint} />
            <KeyValue label="共享工位" value={selected.shared ? "是，多类 agent 共用这片工位与上下文。" : "否，当前是独立工位。"} />
            <KeyValue label="当前任务数" value={selected.tasks.length ? `${selected.tasks.length} 个` : "当前没有任务。"} />
          </div>

          <div className="pixel-mini-stats">
            <div>
              <Clock3 size={15} />
              <strong>{countByStatus(selected.tasks, "running")}</strong>
              <span>运行中</span>
            </div>
            <div>
              <AlertTriangle size={15} />
              <strong>{countByStatuses(selected.tasks, ["blocked", "failed", "waiting_approval"])}</strong>
              <span>阻塞/待批</span>
            </div>
            <div>
              <CheckCircle2 size={15} />
              <strong>{countByStatus(selected.tasks, "succeeded")}</strong>
              <span>已完成</span>
            </div>
          </div>

          {selected.tasks.length ? (
            <div className="pixel-task-list">
              {selected.tasks.slice(0, 5).map((task) => (
                <div key={task.task_id} className="pixel-task-card">
                  <div className="pixel-task-title">
                    <strong>{task.task_id}</strong>
                    <StatusPill value={task.status} />
                  </div>
                  <p>{task.goal}</p>
                  <small>{task.kind}</small>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="当前工位空闲" body="可以从自动研究向导继续推进，或者切到其他项目查看不同角色的工作状态。" />
          )}

          {selected.shared ? (
            <div className="pixel-shared-panel">
              <div className="pixel-next-head">
                <Users2 size={16} />
                <strong>共享工位说明</strong>
              </div>
              <p>{selected.lane.sharedCrew?.join(" / ")} 会共用这里的上下文和资源。</p>
            </div>
          ) : null}

          {props.projectDashboard ? (
            <div className="pixel-next-card">
              <div className="pixel-next-head">
                <Sparkles size={16} />
                <strong>建议下一步</strong>
              </div>
              <p>{selected.lane.nextHint}</p>
              <small>
                系统推荐任务: {props.projectDashboard.recommended_next_task_kind ?? "-"}
                {props.projectDashboard.recommendation_reason ? ` | ${props.projectDashboard.recommendation_reason}` : ""}
              </small>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function deriveState(tasks: Task[]): StationState {
  if (tasks.some((task) => task.status === "blocked" || task.status === "failed")) {
    return "blocked";
  }
  if (tasks.some((task) => task.status === "waiting_approval")) {
    return "review";
  }
  if (tasks.some((task) => task.status === "running")) {
    return "running";
  }
  if (tasks.some((task) => task.status === "succeeded")) {
    return "done";
  }
  return "idle";
}

function countByStatus(tasks: Task[], status: string) {
  return tasks.filter((task) => task.status === status).length;
}

function countByStatuses(tasks: Task[], statuses: string[]) {
  return tasks.filter((task) => statuses.includes(task.status)).length;
}
