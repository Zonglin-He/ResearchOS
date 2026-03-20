from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from app.api.deps import get_project_service, get_task_service
from app.api.models import (
    ApprovalCreate,
    ApprovalRead,
    ClaimCreate,
    ClaimRead,
    ProjectCreate,
    ProjectRead,
    RunManifestCreate,
    RunManifestRead,
    TaskCreate,
    TaskRead,
    TaskStatusUpdate,
)
from app.bootstrap import build_runtime_services
from app.core.config import load_config
from app.schemas.approval import Approval
from app.schemas.claim import Claim
from app.schemas.freeze import ResultsFreeze, SpecFreeze, TopicFreeze
from app.schemas.gap_map import Gap, GapCluster, GapMap
from app.schemas.paper_card import EvidenceRef, PaperCard
from app.schemas.project import Project
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task, TaskStatus
from app.services.project_service import ProjectService
from app.services.task_service import TaskService
from app.worker.tasks import dispatch_task as dispatch_task_job


def create_app(db_path: str = "data/researchos.db") -> FastAPI:
    config = load_config()
    config.db_path = db_path
    services = build_runtime_services(config)
    app = FastAPI(title="ResearchOS", version="0.1.0")
    app.state.project_service = services.project_service
    app.state.task_service = services.task_service
    app.state.claim_service = services.claim_service
    app.state.run_service = services.run_service
    app.state.freeze_service = services.freeze_service
    app.state.paper_card_service = services.paper_card_service
    app.state.gap_map_service = services.gap_map_service
    app.state.approval_service = services.approval_service
    app.state.orchestrator = services.orchestrator

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/projects", response_model=ProjectRead)
    def create_project(
        payload: ProjectCreate,
        project_service: ProjectService = Depends(get_project_service),
    ) -> ProjectRead:
        project = project_service.create_project(
            Project(
                project_id=payload.project_id,
                name=payload.name,
                description=payload.description,
                status=payload.status,
            )
        )
        return ProjectRead.model_validate(project, from_attributes=True)

    @app.get("/projects", response_model=list[ProjectRead])
    def list_projects(
        project_service: ProjectService = Depends(get_project_service),
    ) -> list[ProjectRead]:
        return [
            ProjectRead.model_validate(project, from_attributes=True)
            for project in project_service.list_projects()
        ]

    @app.get("/projects/{project_id}", response_model=ProjectRead)
    def get_project(
        project_id: str,
        project_service: ProjectService = Depends(get_project_service),
    ) -> ProjectRead:
        project = project_service.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return ProjectRead.model_validate(project, from_attributes=True)

    @app.post("/tasks", response_model=TaskRead)
    def create_task(
        payload: TaskCreate,
        task_service: TaskService = Depends(get_task_service),
    ) -> TaskRead:
        task = task_service.create_task(
            Task(
                task_id=payload.task_id,
                project_id=payload.project_id,
                kind=payload.kind,
                goal=payload.goal,
                input_payload=payload.input_payload,
                owner=payload.owner,
                assigned_agent=payload.assigned_agent,
                parent_task_id=payload.parent_task_id,
            )
        )
        return _to_task_read(task)

    @app.get("/tasks", response_model=list[TaskRead])
    def list_tasks(
        task_service: TaskService = Depends(get_task_service),
    ) -> list[TaskRead]:
        return [_to_task_read(task) for task in task_service.list_tasks()]

    @app.get("/tasks/{task_id}", response_model=TaskRead)
    def get_task(
        task_id: str,
        task_service: TaskService = Depends(get_task_service),
    ) -> TaskRead:
        task = task_service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="Task not found")
        return _to_task_read(task)

    @app.post("/tasks/{task_id}/status", response_model=TaskRead)
    def update_task_status(
        task_id: str,
        payload: TaskStatusUpdate,
        task_service: TaskService = Depends(get_task_service),
    ) -> TaskRead:
        try:
            task = task_service.update_status(task_id, TaskStatus(payload.status))
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _to_task_read(task)

    @app.post("/tasks/{task_id}/retry", response_model=TaskRead)
    def retry_task(
        task_id: str,
        task_service: TaskService = Depends(get_task_service),
    ) -> TaskRead:
        try:
            task = task_service.retry_task(task_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _to_task_read(task)

    @app.post("/tasks/{task_id}/dispatch", response_model=TaskRead)
    async def dispatch_task(task_id: str) -> TaskRead:
        try:
            dispatch = await app.state.orchestrator.dispatch(task_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _to_task_read(dispatch.task)

    @app.post("/tasks/{task_id}/enqueue")
    def enqueue_task(task_id: str) -> dict[str, str]:
        result = dispatch_task_job.delay(task_id)
        return {"celery_task_id": result.id, "task_id": task_id}

    @app.post("/claims", response_model=ClaimRead)
    def create_claim(payload: ClaimCreate) -> ClaimRead:
        claim = app.state.claim_service.register_claim(
            Claim(
                claim_id=payload.claim_id,
                text=payload.text,
                claim_type=payload.claim_type,
                risk_level=payload.risk_level,
                approved_by_human=payload.approved_by_human,
            )
        )
        return ClaimRead.model_validate(claim, from_attributes=True)

    @app.get("/claims", response_model=list[ClaimRead])
    def list_claims() -> list[ClaimRead]:
        return [
            ClaimRead.model_validate(claim, from_attributes=True)
            for claim in app.state.claim_service.list_claims()
        ]

    @app.post("/runs", response_model=RunManifestRead)
    def create_run(payload: RunManifestCreate) -> RunManifestRead:
        run = app.state.run_service.register_run(
            RunManifest(
                run_id=payload.run_id,
                spec_id=payload.spec_id,
                git_commit=payload.git_commit,
                config_hash=payload.config_hash,
                dataset_snapshot=payload.dataset_snapshot,
                seed=payload.seed,
                gpu=payload.gpu,
            )
        )
        return RunManifestRead.model_validate(run, from_attributes=True)

    @app.get("/runs", response_model=list[RunManifestRead])
    def list_runs() -> list[RunManifestRead]:
        return [
            RunManifestRead.model_validate(run, from_attributes=True)
            for run in app.state.run_service.list_runs()
        ]

    @app.post("/approvals", response_model=ApprovalRead)
    def create_approval(payload: ApprovalCreate) -> ApprovalRead:
        approval = app.state.approval_service.record_approval(
            Approval(
                approval_id=payload.approval_id,
                project_id=payload.project_id,
                target_type=payload.target_type,
                target_id=payload.target_id,
                approved_by=payload.approved_by,
                decision=payload.decision,
                comment=payload.comment,
            )
        )
        return ApprovalRead.model_validate(approval, from_attributes=True)

    @app.get("/approvals/pending", response_model=list[ApprovalRead])
    def list_pending_approvals() -> list[ApprovalRead]:
        return [
            ApprovalRead.model_validate(approval, from_attributes=True)
            for approval in app.state.approval_service.list_pending()
        ]

    @app.post("/paper-cards")
    def create_paper_card(payload: dict) -> dict:
        card = app.state.paper_card_service.register_card(
            PaperCard(
                paper_id=payload["paper_id"],
                title=payload["title"],
                problem=payload["problem"],
                setting=payload["setting"],
                task_type=payload["task_type"],
                evidence_refs=[
                    EvidenceRef(section=ref["section"], page=ref["page"])
                    for ref in payload.get("evidence_refs", [])
                ],
            )
        )
        return {"paper_id": card.paper_id}

    @app.get("/paper-cards")
    def list_paper_cards() -> list[dict]:
        return [
            {
                "paper_id": card.paper_id,
                "title": card.title,
                "task_type": card.task_type,
            }
            for card in app.state.paper_card_service.list_cards()
        ]

    @app.post("/gap-maps")
    def create_gap_map(payload: dict) -> dict:
        gap_map = app.state.gap_map_service.register_gap_map(
            GapMap(
                topic=payload["topic"],
                clusters=[
                    GapCluster(
                        name=cluster["name"],
                        gaps=[
                            Gap(
                                gap_id=gap["gap_id"],
                                description=gap["description"],
                            )
                            for gap in cluster.get("gaps", [])
                        ],
                    )
                    for cluster in payload.get("clusters", [])
                ],
            )
        )
        return {"topic": gap_map.topic}

    @app.get("/gap-maps")
    def list_gap_maps() -> list[dict]:
        return [
            {
                "topic": gap_map.topic,
                "clusters": len(gap_map.clusters),
            }
            for gap_map in app.state.gap_map_service.list_gap_maps()
        ]

    @app.post("/freezes/topic")
    def save_topic_freeze(payload: dict) -> dict:
        freeze = app.state.freeze_service.save_topic_freeze(
            TopicFreeze(
                topic_id=payload["topic_id"],
                selected_gap_ids=payload.get("selected_gap_ids", []),
                research_question=payload["research_question"],
                novelty_type=payload.get("novelty_type", []),
                owner=payload.get("owner", ""),
                status=payload.get("status", "approved"),
            )
        )
        return {"topic_id": freeze.topic_id}

    @app.get("/freezes/topic")
    def load_topic_freeze() -> dict | None:
        freeze = app.state.freeze_service.load_topic_freeze()
        if freeze is None:
            return None
        return {
            "topic_id": freeze.topic_id,
            "selected_gap_ids": freeze.selected_gap_ids,
            "research_question": freeze.research_question,
            "novelty_type": freeze.novelty_type,
            "owner": freeze.owner,
            "status": freeze.status,
        }

    @app.post("/freezes/spec")
    def save_spec_freeze(payload: dict) -> dict:
        freeze = app.state.freeze_service.save_spec_freeze(
            SpecFreeze(
                spec_id=payload["spec_id"],
                topic_id=payload["topic_id"],
                hypothesis=payload.get("hypothesis", []),
                must_beat_baselines=payload.get("must_beat_baselines", []),
                datasets=payload.get("datasets", []),
                metrics=payload.get("metrics", []),
                fairness_constraints=payload.get("fairness_constraints", []),
                ablations=payload.get("ablations", []),
                success_criteria=payload.get("success_criteria", []),
                failure_criteria=payload.get("failure_criteria", []),
                approved_by=payload.get("approved_by", ""),
                status=payload.get("status", "approved"),
            )
        )
        return {"spec_id": freeze.spec_id}

    @app.get("/freezes/spec")
    def load_spec_freeze() -> dict | None:
        freeze = app.state.freeze_service.load_spec_freeze()
        if freeze is None:
            return None
        return {
            "spec_id": freeze.spec_id,
            "topic_id": freeze.topic_id,
            "hypothesis": freeze.hypothesis,
            "must_beat_baselines": freeze.must_beat_baselines,
            "datasets": freeze.datasets,
            "metrics": freeze.metrics,
            "fairness_constraints": freeze.fairness_constraints,
            "ablations": freeze.ablations,
            "success_criteria": freeze.success_criteria,
            "failure_criteria": freeze.failure_criteria,
            "approved_by": freeze.approved_by,
            "status": freeze.status,
        }

    @app.post("/freezes/results")
    def save_results_freeze(payload: dict) -> dict:
        freeze = app.state.freeze_service.save_results_freeze(
            ResultsFreeze(
                results_id=payload["results_id"],
                spec_id=payload["spec_id"],
                main_claims=payload.get("main_claims", []),
                tables=payload.get("tables", []),
                figures=payload.get("figures", []),
                approved_by=payload.get("approved_by", ""),
                status=payload.get("status", "approved"),
            )
        )
        return {"results_id": freeze.results_id}

    @app.get("/freezes/results")
    def load_results_freeze() -> dict | None:
        freeze = app.state.freeze_service.load_results_freeze()
        if freeze is None:
            return None
        return {
            "results_id": freeze.results_id,
            "spec_id": freeze.spec_id,
            "main_claims": freeze.main_claims,
            "tables": freeze.tables,
            "figures": freeze.figures,
            "approved_by": freeze.approved_by,
            "status": freeze.status,
        }

    return app


def _to_task_read(task: Task) -> TaskRead:
    return TaskRead(
        task_id=task.task_id,
        project_id=task.project_id,
        kind=task.kind,
        goal=task.goal,
        input_payload=task.input_payload,
        owner=task.owner,
        assigned_agent=task.assigned_agent,
        parent_task_id=task.parent_task_id,
        status=task.status.value,
        created_at=task.created_at,
    )
