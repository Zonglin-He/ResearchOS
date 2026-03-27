from __future__ import annotations

import asyncio
import json

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.api.deps import get_project_service, get_task_service
from app.api.schemas import (
    AdoptDirectionRequest,
    AdoptDirectionResponse,
    ArtifactAnnotationCreate,
    ArtifactAnnotationRead,
    ArtifactDetailRead,
    ArtifactInspectionRead,
    ArtifactRead,
    AutopilotRead,
    AutopilotResponse,
    BranchComparisonRead,
    ArtifactProvenanceRead,
    AuditSubjectRefRead,
    AuditEntryRead,
    AuditReportRead,
    AuditSummaryRead,
    ApprovalCreate,
    ApprovalRead,
    ClaimCreate,
    ClaimSupportRefRead,
    ClaimRead,
    DiscussionAdoptCreate,
    DiscussionHistoryRead,
    DiscussionImportCreate,
    DiscussionPromotionRead,
    DiscussionPromoteApprovalCreate,
    DiscussionPromoteTaskCreate,
    DiscussionSessionCreate,
    DiscussionSessionRead,
    DiscussDirectionRequest,
    DiscussDirectionResponse,
    EvidenceRefModel,
    FlowActionRequest,
    FlowSnapshotRead,
    GapCreate,
    GapClusterCreate,
    GapMapCreate,
    GapMapCreateResponse,
    GapMapRead,
    GapMapSummaryRead,
    KnowledgeBucketSummaryRead,
    KnowledgeRecordRead,
    KnowledgeSummaryRead,
    LessonCreate,
    LessonRead,
    PaperCardCreate,
    PaperCardCreateResponse,
    PaperCardRead,
    PaperCardSummaryRead,
    ProjectCreate,
    ProjectDashboardRead,
    ProjectRead,
    ResearchStartRequest,
    ResearchStartResponse,
    ResultsFreezeRead,
    ResultsFreezeSave,
    ResultsFreezeSaveResponse,
    RoutingInspectionRead,
    RunEventRead,
    RunEvidenceRefRead,
    RunManifestCreate,
    RunManifestRead,
    ResolvedDispatchModel,
    SpecFreezeRead,
    SpecFreezeSave,
    StorageBoundaryRead,
    SpecFreezeSaveResponse,
    TaskCreate,
    TaskRead,
    TaskStatusUpdate,
    TopicFreezeRead,
    TopicFreezeSave,
    TopicFreezeSaveResponse,
    VerificationRead,
    VerificationLinkRead,
    ProvenanceEvidenceRefRead,
    VerificationSummaryRead,
    ProviderHealthSnapshotModel,
)
from app.bootstrap import build_runtime_services
from app.core.config import load_config
from app.routing import dispatch_profile_from_dict
from app.schemas.approval import Approval
from app.schemas.artifact_annotation import ArtifactAnnotation, ArtifactAnnotationStatus
from app.schemas.audit import AuditEntry
from app.schemas.claim import Claim
from app.schemas.freeze import ResultsFreeze, SpecFreeze, TopicFreeze
from app.schemas.gap_map import Gap, GapCluster, GapMap
from app.schemas.lesson import LessonKind, LessonRecord
from app.schemas.paper_card import EvidenceRef, PaperCard
from app.schemas.provenance import (
    ArtifactProvenance,
    AuditSubjectRef,
    ClaimSupportRef,
    ProvenanceEvidenceRef,
    RunEvidenceRef,
    VerificationLink,
)
from app.schemas.project import Project
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task, TaskStatus
from app.schemas.verification import (
    VerificationCheckType,
    VerificationRecord,
    VerificationStatus,
)
from app.services.audit_service import AuditService
from app.services.lessons_service import LessonsService
from app.services.project_service import ProjectService
from app.services.registry_store import to_record
from app.services.task_service import TaskService
from app.services.verification_service import VerificationService
from app.workflows.research_flow import FlowEvent, available_flow_actions
from app.worker.tasks import dispatch_task as dispatch_task_job


def create_app(db_path: str = "data/researchos.db", workspace_root: str | None = None) -> FastAPI:
    config = load_config()
    config.db_path = db_path
    if workspace_root is not None:
        config.workspace_root = workspace_root
    services = build_runtime_services(config)
    app = FastAPI(title="ResearchOS", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.state.project_service = services.project_service
    app.state.task_service = services.task_service
    app.state.claim_service = services.claim_service
    app.state.run_service = services.run_service
    app.state.freeze_service = services.freeze_service
    app.state.paper_card_service = services.paper_card_service
    app.state.gap_map_service = services.gap_map_service
    app.state.approval_service = services.approval_service
    app.state.artifact_service = services.artifact_service
    app.state.artifact_annotation_service = services.artifact_annotation_service
    app.state.discussion_service = services.discussion_service
    app.state.lessons_service = services.lessons_service
    app.state.verification_service = services.verification_service
    app.state.audit_service = services.audit_service
    app.state.provenance_service = services.provenance_service
    app.state.operator_inspection_service = services.operator_inspection_service
    app.state.kb_service = services.kb_service
    app.state.provider_health_service = services.provider_health_service
    app.state.provider_registry = services.provider_registry
    app.state.orchestrator = services.orchestrator
    app.state.research_guide_service = services.research_guide_service
    app.state.activity_service = services.activity_service
    app.state.checkpoint_service = services.checkpoint_service

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/guide/start", response_model=ResearchStartResponse)
    async def guide_start_research(payload: ResearchStartRequest) -> ResearchStartResponse:
        try:
            result = await app.state.research_guide_service.start_research(
                research_goal=payload.research_goal,
                project_name=payload.project_name,
                project_id=payload.project_id,
                owner=payload.owner,
                keywords=payload.keywords,
                max_papers=payload.max_papers,
                expected_min_papers=payload.expected_min_papers,
                auto_dispatch=payload.auto_dispatch,
            )
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return ResearchStartResponse(
            project_id=result.project.project_id,
            project_name=result.project.name,
            intake_task_id=result.intake_task.task_id,
            autopilot=AutopilotRead(
                dispatched_task_ids=list(result.autopilot.dispatched_task_ids),
                stop_reason=result.autopilot.stop_reason,
                human_select_task_id=result.autopilot.human_select_task_id,
            ),
            next_step=_guide_next_step(result.autopilot.stop_reason),
        )

    @app.post("/guide/adopt-direction", response_model=AdoptDirectionResponse)
    async def guide_adopt_direction(payload: AdoptDirectionRequest) -> AdoptDirectionResponse:
        try:
            result = await app.state.research_guide_service.adopt_direction(
                project_id=payload.project_id,
                human_select_task_id=payload.human_select_task_id,
                gap_id=payload.gap_id,
                research_question=payload.research_question,
                operator_note=payload.operator_note,
                novelty_type=payload.novelty_type,
                owner=payload.owner,
                auto_dispatch=payload.auto_dispatch,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return AdoptDirectionResponse(
            topic_id=result.topic_freeze.topic_id,
            build_task_id=result.build_task.task_id,
            autopilot=AutopilotRead(
                dispatched_task_ids=list(result.autopilot.dispatched_task_ids),
                stop_reason=result.autopilot.stop_reason,
                human_select_task_id=result.autopilot.human_select_task_id,
            ),
            next_step=_guide_next_step(result.autopilot.stop_reason),
        )

    @app.post("/guide/discuss-direction", response_model=DiscussDirectionResponse)
    async def guide_discuss_direction(payload: DiscussDirectionRequest) -> DiscussDirectionResponse:
        try:
            result = await app.state.research_guide_service.discuss_direction(
                project_id=payload.project_id,
                human_select_task_id=payload.human_select_task_id,
                gap_id=payload.gap_id,
                user_message=payload.user_message,
                history=[message.model_dump() for message in payload.history],
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        except RuntimeError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error
        return DiscussDirectionResponse(
            thread_id=result.thread_id,
            assistant_message=result.assistant_message,
            gap_id=result.gap_id,
            topic=result.topic,
            strengths=list(result.strengths),
            risks=list(result.risks),
            next_checks=list(result.next_checks),
            cited_papers=list(result.cited_papers),
            research_question_suggestion=result.research_question_suggestion,
            assistant_role=result.assistant_role,
            provider_name=result.provider_name,
            model_name=result.model_name,
            reasoning_effort=result.reasoning_effort,
            skill_name=result.skill_name,
        )

    @app.get(
        "/projects/{project_id}/guide/discussions/{human_select_task_id}/{gap_id}",
        response_model=DiscussionHistoryRead,
    )
    def guide_discussion_history(
        project_id: str,
        human_select_task_id: str,
        gap_id: str,
    ) -> DiscussionHistoryRead:
        messages = app.state.research_guide_service.list_discussion_messages(
            project_id=project_id,
            human_select_task_id=human_select_task_id,
            gap_id=gap_id,
        )
        return DiscussionHistoryRead(
            thread_id=app.state.activity_service.discussion_thread_id(
                human_select_task_id=human_select_task_id,
                gap_id=gap_id,
            ),
            messages=[
                {
                    "message_id": message.message_id,
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at.isoformat(),
                    "metadata": message.metadata,
                }
                for message in messages
            ],
        )

    @app.post("/discussions", response_model=DiscussionSessionRead)
    def create_discussion_session(payload: DiscussionSessionCreate) -> DiscussionSessionRead:
        try:
            session = app.state.discussion_service.create_session(
                session_id=payload.session_id,
                project_id=payload.project_id,
                title=payload.title,
                source_type=payload.source_type,
                source_label=payload.source_label,
                branch_kind=payload.branch_kind,
                target_kind=payload.target_kind,
                target_id=payload.target_id,
                target_label=payload.target_label,
                focus_question=payload.focus_question,
                operator_prompt=payload.operator_prompt,
                questions_to_answer=payload.questions_to_answer,
                attached_entities=[
                    {
                        "entity_type": item.entity_type,
                        "entity_id": item.entity_id,
                        "label": item.label,
                    }
                    for item in payload.attached_entities
                ],
                metadata=payload.metadata,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _to_discussion_session_read(session)

    @app.get("/discussions", response_model=list[DiscussionSessionRead])
    def list_discussion_sessions(project_id: str | None = Query(default=None)) -> list[DiscussionSessionRead]:
        return [
            _to_discussion_session_read(session)
            for session in app.state.discussion_service.list_sessions(project_id=project_id)
        ]

    @app.get("/discussions/{session_id}", response_model=DiscussionSessionRead)
    def get_discussion_session(session_id: str) -> DiscussionSessionRead:
        session = app.state.discussion_service.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Discussion session not found")
        return _to_discussion_session_read(session)

    @app.post("/discussions/{session_id}/import", response_model=DiscussionSessionRead)
    def import_discussion_result(session_id: str, payload: DiscussionImportCreate) -> DiscussionSessionRead:
        try:
            session = app.state.discussion_service.import_result(
                session_id,
                source_mode=payload.source_mode,
                provider_label=payload.provider_label,
                verbatim_text=payload.verbatim_text,
                transcript_title=payload.transcript_title,
                cited_dois=payload.cited_dois,
                referenced_claim_ids=payload.referenced_claim_ids,
                findings=payload.findings,
                decisions=payload.decisions,
                literature_notes=payload.literature_notes,
                open_questions=payload.open_questions,
                risks=payload.risks,
                counterarguments=payload.counterarguments,
                suggested_next_actions=payload.suggested_next_actions,
                summary=payload.summary,
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _to_discussion_session_read(session)

    @app.post("/discussions/{session_id}/adopt", response_model=DiscussionSessionRead)
    def adopt_discussion_session(session_id: str, payload: DiscussionAdoptCreate) -> DiscussionSessionRead:
        try:
            session = app.state.discussion_service.adopt_session(
                session_id,
                approved_by=payload.approved_by,
                adopted_summary=payload.adopted_summary,
                route_to_kb=payload.route_to_kb,
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return _to_discussion_session_read(session)

    @app.post("/discussions/{session_id}/promote/kb", response_model=DiscussionPromotionRead)
    def promote_discussion_to_kb(session_id: str) -> DiscussionPromotionRead:
        try:
            record_ids = app.state.discussion_service.promote_to_kb(session_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return DiscussionPromotionRead(promotion_type="kb", record_ids=record_ids)

    @app.post("/discussions/{session_id}/promote/approval", response_model=DiscussionPromotionRead)
    def promote_discussion_to_approval(
        session_id: str,
        payload: DiscussionPromoteApprovalCreate,
    ) -> DiscussionPromotionRead:
        try:
            approval_id = app.state.discussion_service.promote_to_approval(
                session_id,
                approved_by=payload.approved_by,
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return DiscussionPromotionRead(promotion_type="approval", record_ids=[approval_id])

    @app.post("/discussions/{session_id}/promote/task", response_model=DiscussionPromotionRead)
    def promote_discussion_to_task(
        session_id: str,
        payload: DiscussionPromoteTaskCreate,
    ) -> DiscussionPromotionRead:
        try:
            task_id = app.state.discussion_service.promote_to_task(
                session_id,
                owner=payload.owner,
                task_kind=payload.task_kind,
                task_goal=payload.task_goal,
            )
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return DiscussionPromotionRead(promotion_type="task", record_ids=[task_id])

    @app.post("/projects/{project_id}/autopilot", response_model=AutopilotResponse)
    async def autopilot_project(project_id: str) -> AutopilotResponse:
        try:
            result = await app.state.research_guide_service.autopilot_project(project_id)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        return AutopilotResponse(
            project_id=project_id,
            autopilot=AutopilotRead(
                dispatched_task_ids=list(result.dispatched_task_ids),
                stop_reason=result.stop_reason,
                human_select_task_id=result.human_select_task_id,
            ),
        )

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
                stage=payload.stage,
                dispatch_profile=dispatch_profile_from_dict(
                    payload.dispatch_profile.model_dump() if payload.dispatch_profile is not None else None
                ),
            )
        )
        return _to_project_read(project)

    @app.get("/projects", response_model=list[ProjectRead])
    def list_projects(
        project_service: ProjectService = Depends(get_project_service),
    ) -> list[ProjectRead]:
        return [_to_project_read(project) for project in project_service.list_projects()]

    @app.get("/projects/{project_id}", response_model=ProjectRead)
    def get_project(
        project_id: str,
        project_service: ProjectService = Depends(get_project_service),
    ) -> ProjectRead:
        project = project_service.get_project(project_id)
        if project is None:
            raise HTTPException(status_code=404, detail="Project not found")
        return _to_project_read(project)

    @app.get("/projects/{project_id}/dashboard", response_model=ProjectDashboardRead)
    def get_project_dashboard(project_id: str) -> ProjectDashboardRead:
        try:
            dashboard = app.state.operator_inspection_service.build_project_dashboard(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _to_project_dashboard_read(dashboard)

    @app.get("/projects/{project_id}/flow", response_model=FlowSnapshotRead)
    def get_project_flow(project_id: str) -> FlowSnapshotRead:
        try:
            snapshot = app.state.operator_inspection_service.inspect_project_flow(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _to_flow_snapshot_read(snapshot)

    @app.post("/projects/{project_id}/flow/{action}", response_model=FlowSnapshotRead)
    def update_project_flow(
        project_id: str,
        action: str,
        payload: FlowActionRequest,
    ) -> FlowSnapshotRead:
        try:
            event = FlowEvent(action)
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"Unsupported flow action: {action}") from error
        try:
            stage = Stage(payload.stage) if payload.stage else None
        except ValueError as error:
            raise HTTPException(status_code=400, detail=f"Unsupported stage: {payload.stage}") from error
        try:
            project = app.state.project_service.transition_flow(
                project_id,
                event=event,
                stage=stage,
                task_id=payload.task_id,
                note=payload.note,
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        snapshot = app.state.project_service.get_flow_snapshot(project.project_id)
        return _to_flow_snapshot_read(snapshot)

    @app.get("/projects/{project_id}/branches/compare", response_model=BranchComparisonRead)
    def compare_project_branches(project_id: str) -> BranchComparisonRead:
        try:
            comparison = app.state.operator_inspection_service.compare_project_branches(project_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _to_branch_comparison_read(comparison)

    @app.get("/kb/summary", response_model=KnowledgeSummaryRead)
    def kb_summary() -> KnowledgeSummaryRead:
        buckets = []
        for bucket in ("decisions", "findings", "literature", "open_questions"):
            records = app.state.kb_service.list_bucket(bucket)
            buckets.append(
                KnowledgeBucketSummaryRead(
                    bucket=bucket,
                    count=len(records),
                    latest_title=records[-1].title if records else "",
                )
            )
        return KnowledgeSummaryRead(buckets=buckets)

    @app.get("/kb/{bucket}", response_model=list[KnowledgeRecordRead])
    def kb_bucket(bucket: str, limit: int = Query(default=20, ge=1, le=100)) -> list[KnowledgeRecordRead]:
        try:
            records = app.state.kb_service.list_bucket(bucket)[-limit:]
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return [
            KnowledgeRecordRead(
                record_id=record.record_id,
                project_id=record.project_id,
                title=record.title,
                summary=record.summary,
                context_tags=record.context_tags,
                payload=record.payload,
                created_at=record.created_at,
            )
            for record in reversed(records)
        ]

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
                depends_on=payload.depends_on,
                join_key=payload.join_key,
                fanout_group=payload.fanout_group,
                max_retries=payload.max_retries,
                dispatch_profile=dispatch_profile_from_dict(
                    payload.dispatch_profile.model_dump() if payload.dispatch_profile is not None else None
                ),
            )
        )
        return _to_task_read(task)

    @app.get("/projects/{project_id}/events", response_model=list[RunEventRead])
    def list_project_events(
        project_id: str,
        after_id: int = Query(default=0, ge=0),
        limit: int = Query(default=100, ge=1, le=500),
    ) -> list[RunEventRead]:
        return [
            RunEventRead(
                event_id=event.event_id or 0,
                project_id=event.project_id,
                task_id=event.task_id,
                run_id=event.run_id,
                event_type=event.event_type,
                message=event.message,
                payload=event.payload,
                created_at=event.created_at,
            )
            for event in app.state.activity_service.list_events(project_id, after_id=after_id, limit=limit)
        ]

    @app.get("/projects/{project_id}/events/stream")
    async def stream_project_events(
        project_id: str,
        after_id: int = Query(default=0, ge=0),
    ) -> StreamingResponse:
        async def event_stream():
            cursor = after_id
            while True:
                events = app.state.activity_service.list_events(project_id, after_id=cursor, limit=100)
                if events:
                    for event in events:
                        cursor = max(cursor, event.event_id or cursor)
                        payload = RunEventRead(
                            event_id=event.event_id or 0,
                            project_id=event.project_id,
                            task_id=event.task_id,
                            run_id=event.run_id,
                            event_type=event.event_type,
                            message=event.message,
                            payload=event.payload,
                            created_at=event.created_at,
                        )
                        yield f"id: {payload.event_id}\ndata: {payload.model_dump_json()}\n\n"
                else:
                    yield ": keep-alive\n\n"
                await asyncio.sleep(1.0)

        return StreamingResponse(event_stream(), media_type="text/event-stream")

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

    @app.post("/tasks/{task_id}/resume", response_model=TaskRead)
    def resume_task(
        task_id: str,
        task_service: TaskService = Depends(get_task_service),
    ) -> TaskRead:
        task = task_service.get_task(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")
        checkpoint = app.state.checkpoint_service.load(task_id)
        if checkpoint is None or not task.checkpoint_path:
            raise HTTPException(status_code=400, detail=f"No checkpoint available for task {task_id}")
        try:
            task = task_service.retry_task(task_id)
        except (KeyError, ValueError) as error:
            raise HTTPException(status_code=400, detail=str(error)) from error
        task.input_payload["resume_requested"] = True
        task = task_service.save_task(task)
        try:
            app.state.project_service.transition_flow(
                task.project_id,
                event=FlowEvent.RESUME,
                stage=app.state.project_service.get_flow_snapshot(task.project_id).stage,
                task_id=task.task_id,
                note="checkpoint resume requested",
            )
        except KeyError:
            pass
        return _to_task_read(task)

    @app.post("/tasks/{task_id}/cancel", response_model=TaskRead)
    def cancel_task(
        task_id: str,
        task_service: TaskService = Depends(get_task_service),
    ) -> TaskRead:
        try:
            task = task_service.cancel_task(task_id)
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
        except RuntimeError as error:
            try:
                app.state.task_service.update_status(task_id, TaskStatus.FAILED)
            except Exception:
                pass
            detail = str(error).strip() or "Provider invocation failed during task dispatch."
            raise HTTPException(status_code=502, detail=detail) from error
        return _to_task_read(dispatch.task)

    @app.post("/tasks/{task_id}/enqueue")
    def enqueue_task(task_id: str) -> dict[str, str]:
        result = dispatch_task_job.delay(task_id)
        return {"celery_task_id": result.id, "task_id": task_id}

    @app.get("/routing/system", response_model=RoutingInspectionRead)
    def inspect_system_routing() -> RoutingInspectionRead:
        return _to_routing_inspection_read(app.state.operator_inspection_service.inspect_system_routing())

    @app.get("/routing/tasks/{task_id}", response_model=RoutingInspectionRead)
    def inspect_task_routing(task_id: str) -> RoutingInspectionRead:
        try:
            inspection = app.state.operator_inspection_service.inspect_task_routing(task_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _to_routing_inspection_read(inspection)

    @app.get("/providers/health", response_model=list[ProviderHealthSnapshotModel])
    def list_provider_health() -> list[ProviderHealthSnapshotModel]:
        return [
            ProviderHealthSnapshotModel.model_validate(to_record(snapshot))
            for snapshot in app.state.operator_inspection_service.list_provider_health()
        ]

    @app.post("/providers/{provider_name}/disable", response_model=ProviderHealthSnapshotModel)
    def disable_provider(provider_name: str) -> ProviderHealthSnapshotModel:
        snapshot = app.state.operator_inspection_service.disable_provider_family(provider_name)
        return ProviderHealthSnapshotModel.model_validate(to_record(snapshot))

    @app.post("/providers/{provider_name}/enable", response_model=ProviderHealthSnapshotModel)
    def enable_provider(provider_name: str) -> ProviderHealthSnapshotModel:
        snapshot = app.state.operator_inspection_service.enable_provider_family(provider_name)
        return ProviderHealthSnapshotModel.model_validate(to_record(snapshot))

    @app.post("/providers/{provider_name}/clear-cooldown", response_model=ProviderHealthSnapshotModel)
    def clear_provider_cooldown(provider_name: str) -> ProviderHealthSnapshotModel:
        snapshot = app.state.operator_inspection_service.clear_provider_cooldown(provider_name)
        return ProviderHealthSnapshotModel.model_validate(to_record(snapshot))

    @app.post("/providers/{provider_name}/probe", response_model=ProviderHealthSnapshotModel)
    async def probe_provider(provider_name: str) -> ProviderHealthSnapshotModel:
        snapshot = await app.state.operator_inspection_service.probe_provider_family(provider_name)
        return ProviderHealthSnapshotModel.model_validate(to_record(snapshot))

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
                status=payload.status,
                metrics=payload.metrics,
                artifacts=payload.artifacts,
                source_type=payload.source_type,
                source_label=payload.source_label,
                source_metadata=payload.source_metadata,
                notes=payload.notes,
            )
        )
        return _to_run_read(run)

    @app.get("/runs", response_model=list[RunManifestRead])
    def list_runs() -> list[RunManifestRead]:
        return [_to_run_read(run) for run in app.state.run_service.list_runs()]

    @app.get("/artifacts", response_model=list[ArtifactRead])
    def list_artifacts(run_id: str | None = None) -> list[ArtifactRead]:
        artifacts = app.state.artifact_service.list_artifacts()
        if run_id is not None:
            artifacts = [artifact for artifact in artifacts if artifact.run_id == run_id]
        return [
            ArtifactRead(
                artifact_id=artifact.artifact_id,
                run_id=artifact.run_id,
                kind=artifact.kind,
                path=artifact.path,
                hash=artifact.hash,
                metadata=artifact.metadata,
            )
            for artifact in artifacts
        ]

    @app.get("/artifacts/{artifact_id}/annotations", response_model=list[ArtifactAnnotationRead])
    def list_artifact_annotations(artifact_id: str) -> list[ArtifactAnnotationRead]:
        artifact = app.state.artifact_service.get_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        return [
            _to_artifact_annotation_read(annotation)
            for annotation in app.state.artifact_annotation_service.list_annotations(artifact_id)
        ]

    @app.post("/artifacts/{artifact_id}/annotations", response_model=ArtifactAnnotationRead)
    def create_artifact_annotation(
        artifact_id: str,
        payload: ArtifactAnnotationCreate,
    ) -> ArtifactAnnotationRead:
        artifact = app.state.artifact_service.get_artifact(artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found")
        annotation = app.state.artifact_annotation_service.record_annotation(
            ArtifactAnnotation(
                annotation_id=payload.annotation_id,
                artifact_id=artifact_id,
                operator=payload.operator,
                status=ArtifactAnnotationStatus(payload.status),
                review_tags=payload.review_tags,
                note=payload.note,
            )
        )
        return _to_artifact_annotation_read(annotation)

    @app.get("/artifacts/{artifact_id}", response_model=ArtifactDetailRead)
    def get_artifact(artifact_id: str) -> ArtifactDetailRead:
        try:
            artifact, provenance, annotations = app.state.provenance_service.build_artifact_provenance(
                artifact_id
            )
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _to_artifact_detail_read(
            artifact=artifact,
            provenance=provenance,
            annotations=annotations,
            verification_service=app.state.verification_service,
            audit_service=app.state.audit_service,
        )

    @app.get("/artifacts/{artifact_id}/inspect", response_model=ArtifactInspectionRead)
    def inspect_artifact(artifact_id: str) -> ArtifactInspectionRead:
        try:
            inspection = app.state.operator_inspection_service.inspect_artifact(artifact_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _to_artifact_inspection_read(inspection)

    @app.post("/lessons", response_model=LessonRead)
    def create_lesson(payload: LessonCreate) -> LessonRead:
        lesson = app.state.lessons_service.record_lesson(
            LessonRecord(
                lesson_id=payload.lesson_id,
                lesson_kind=payload.lesson_kind,
                title=payload.title,
                summary=payload.summary,
                rationale=payload.rationale,
                recommended_action=payload.recommended_action,
                task_kind=payload.task_kind,
                agent_name=payload.agent_name,
                tool_name=payload.tool_name,
                provider_name=payload.provider_name,
                model_name=payload.model_name,
                failure_type=payload.failure_type,
                repository_ref=payload.repository_ref,
                dataset_ref=payload.dataset_ref,
                context_tags=payload.context_tags,
                evidence_refs=payload.evidence_refs,
                artifact_ids=payload.artifact_ids,
                source_task_id=payload.source_task_id,
                source_run_id=payload.source_run_id,
                source_claim_id=payload.source_claim_id,
            )
        )
        return _to_lesson_read(lesson)

    @app.get("/lessons", response_model=list[LessonRead])
    def list_lessons(
        task_kind: str | None = None,
        agent_name: str | None = None,
        tool_name: str | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        failure_type: str | None = None,
        repository_ref: str | None = None,
        dataset_ref: str | None = None,
        lesson_kind: LessonKind | None = None,
    ) -> list[LessonRead]:
        lessons = app.state.lessons_service.list_lessons(
            task_kind=task_kind,
            agent_name=agent_name,
            tool_name=tool_name,
            provider_name=provider_name,
            model_name=model_name,
            failure_type=failure_type,
            repository_ref=repository_ref,
            dataset_ref=dataset_ref,
            lesson_kind=lesson_kind,
        )
        return [_to_lesson_read(lesson) for lesson in lessons]

    @app.post("/verifications/runs/{run_id}", response_model=VerificationRead)
    def verify_run(run_id: str) -> VerificationRead:
        try:
            record = app.state.verification_service.verify_run_manifest(run_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _to_verification_read(record)

    @app.post("/verifications/claims/{claim_id}", response_model=VerificationRead)
    def verify_claim(claim_id: str) -> VerificationRead:
        try:
            record = app.state.verification_service.verify_claim_evidence(claim_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return _to_verification_read(record)

    @app.post("/verifications/freezes/results", response_model=VerificationRead)
    def verify_results_freeze() -> VerificationRead:
        return _to_verification_read(app.state.verification_service.verify_results_freeze())

    @app.get("/verifications", response_model=list[VerificationRead])
    def list_verifications(
        subject_type: str | None = None,
        subject_id: str | None = None,
        check_type: VerificationCheckType | None = None,
        status: VerificationStatus | None = None,
    ) -> list[VerificationRead]:
        records = app.state.verification_service.list_checks(
            subject_type=subject_type,
            subject_id=subject_id,
            check_type=check_type,
            status=status,
        )
        return [_to_verification_read(record) for record in records]

    @app.get("/verifications/summary", response_model=VerificationSummaryRead)
    def get_verification_summary() -> VerificationSummaryRead:
        summary = app.state.provenance_service.build_verification_summary()
        return VerificationSummaryRead(
            total_checks=summary.total_checks,
            status_counts=summary.status_counts,
            check_type_counts=summary.check_type_counts,
            subject_type_counts=summary.subject_type_counts,
        )

    @app.get("/audit/claims", response_model=AuditReportRead)
    def get_claim_audit_report() -> AuditReportRead:
        return _to_audit_report_read(app.state.audit_service.build_claim_alignment_report())

    @app.get("/audit/summary", response_model=AuditSummaryRead)
    def get_audit_summary() -> AuditSummaryRead:
        summary = app.state.provenance_service.build_audit_summary()
        return AuditSummaryRead(
            total_reports=summary.total_reports,
            total_entries=summary.total_entries,
            report_status_counts=summary.report_status_counts,
            entry_status_counts=summary.entry_status_counts,
            findings=summary.findings,
            recommendations=summary.recommendations,
        )

    @app.get("/audit/runs/{run_id}", response_model=AuditReportRead)
    def get_run_audit_report(run_id: str) -> AuditReportRead:
        report = app.state.audit_service.build_run_verification_report(
            run_id,
            app.state.verification_service,
        )
        return _to_audit_report_read(report)

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
                condition_text=payload.condition_text,
                context_summary=payload.context_summary,
                recommended_action=payload.recommended_action,
                due_at=payload.due_at,
            )
        )
        return ApprovalRead.model_validate(approval, from_attributes=True)

    @app.get("/approvals/pending", response_model=list[ApprovalRead])
    def list_pending_approvals() -> list[ApprovalRead]:
        return [
            ApprovalRead.model_validate(approval, from_attributes=True)
            for approval in app.state.approval_service.list_pending()
        ]

    @app.post("/paper-cards", response_model=PaperCardCreateResponse)
    def create_paper_card(payload: PaperCardCreate) -> PaperCardCreateResponse:
        card = app.state.paper_card_service.register_card(
            PaperCard(
                paper_id=payload.paper_id,
                title=payload.title,
                problem=payload.problem,
                setting=payload.setting,
                task_type=payload.task_type,
                core_assumption=payload.core_assumption,
                method_summary=payload.method_summary,
                key_modules=payload.key_modules,
                datasets=payload.datasets,
                metrics=payload.metrics,
                strongest_result=payload.strongest_result,
                claimed_contributions=payload.claimed_contributions,
                hidden_dependencies=payload.hidden_dependencies,
                likely_failure_modes=payload.likely_failure_modes,
                repro_risks=payload.repro_risks,
                idea_seeds=payload.idea_seeds,
                evidence_refs=[
                    EvidenceRef(section=ref.section, page=ref.page)
                    for ref in payload.evidence_refs
                ],
            )
        )
        return PaperCardCreateResponse(paper_id=card.paper_id)

    @app.get("/paper-cards", response_model=list[PaperCardSummaryRead])
    def list_paper_cards() -> list[PaperCardSummaryRead]:
        return [
            PaperCardSummaryRead(
                paper_id=card.paper_id,
                title=card.title,
                task_type=card.task_type,
            )
            for card in app.state.paper_card_service.list_cards()
        ]

    @app.get("/paper-cards/{paper_id:path}", response_model=PaperCardRead)
    def get_paper_card(paper_id: str) -> PaperCardRead:
        card = app.state.paper_card_service.get_card(paper_id)
        if card is None:
            raise HTTPException(status_code=404, detail="Paper card not found")
        return PaperCardRead.model_validate(card, from_attributes=True)

    @app.post("/gap-maps", response_model=GapMapCreateResponse)
    def create_gap_map(payload: GapMapCreate) -> GapMapCreateResponse:
        gap_map = app.state.gap_map_service.register_gap_map(
            GapMap(
                topic=payload.topic,
                clusters=[
                    GapCluster(
                        name=cluster.name,
                        gaps=[
                            Gap(
                                gap_id=gap.gap_id,
                                description=gap.description,
                                supporting_papers=gap.supporting_papers,
                                evidence_summary=gap.evidence_summary,
                                attack_surface=gap.attack_surface,
                                difficulty=gap.difficulty,
                                novelty_type=gap.novelty_type,
                                feasibility=gap.feasibility,
                                novelty_score=gap.novelty_score,
                                debate_weaknesses=gap.debate_weaknesses,
                            )
                            for gap in cluster.gaps
                        ],
                    )
                    for cluster in payload.clusters
                ],
            )
        )
        return GapMapCreateResponse(topic=gap_map.topic)

    @app.get("/gap-maps", response_model=list[GapMapSummaryRead])
    def list_gap_maps() -> list[GapMapSummaryRead]:
        return [
            GapMapSummaryRead(topic=gap_map.topic, clusters=len(gap_map.clusters))
            for gap_map in app.state.gap_map_service.list_gap_maps()
        ]

    @app.get("/gap-maps/{topic:path}", response_model=GapMapRead)
    def get_gap_map(topic: str) -> GapMapRead:
        gap_map = app.state.gap_map_service.get_gap_map(topic)
        if gap_map is None:
            raise HTTPException(status_code=404, detail="Gap map not found")
        return GapMapRead.model_validate(gap_map, from_attributes=True)

    @app.post("/freezes/topic", response_model=TopicFreezeSaveResponse)
    def save_topic_freeze(payload: TopicFreezeSave) -> TopicFreezeSaveResponse:
        freeze = app.state.freeze_service.save_topic_freeze(
            TopicFreeze(
                topic_id=payload.topic_id,
                selected_gap_ids=payload.selected_gap_ids,
                research_question=payload.research_question,
                novelty_type=payload.novelty_type,
                owner=payload.owner,
                status=payload.status,
            )
        )
        return TopicFreezeSaveResponse(topic_id=freeze.topic_id)

    @app.get("/freezes/topic", response_model=TopicFreezeRead | None)
    def load_topic_freeze() -> TopicFreezeRead | None:
        freeze = app.state.freeze_service.load_topic_freeze()
        if freeze is None:
            return None
        return TopicFreezeRead(
            topic_id=freeze.topic_id,
            selected_gap_ids=freeze.selected_gap_ids,
            research_question=freeze.research_question,
            novelty_type=freeze.novelty_type,
            owner=freeze.owner,
            status=freeze.status,
        )

    @app.post("/freezes/spec", response_model=SpecFreezeSaveResponse)
    def save_spec_freeze(payload: SpecFreezeSave) -> SpecFreezeSaveResponse:
        freeze = app.state.freeze_service.save_spec_freeze(
            SpecFreeze(
                spec_id=payload.spec_id,
                topic_id=payload.topic_id,
                hypothesis=payload.hypothesis,
                must_beat_baselines=payload.must_beat_baselines,
                datasets=payload.datasets,
                metrics=payload.metrics,
                fairness_constraints=payload.fairness_constraints,
                ablations=payload.ablations,
                success_criteria=payload.success_criteria,
                failure_criteria=payload.failure_criteria,
                target_venue=payload.target_venue,
                human_constraints=payload.human_constraints,
                approved_by=payload.approved_by,
                status=payload.status,
            )
        )
        return SpecFreezeSaveResponse(spec_id=freeze.spec_id)

    @app.get("/freezes/spec", response_model=SpecFreezeRead | None)
    def load_spec_freeze() -> SpecFreezeRead | None:
        freeze = app.state.freeze_service.load_spec_freeze()
        if freeze is None:
            return None
        return SpecFreezeRead(
            spec_id=freeze.spec_id,
            topic_id=freeze.topic_id,
            hypothesis=freeze.hypothesis,
            must_beat_baselines=freeze.must_beat_baselines,
            datasets=freeze.datasets,
            metrics=freeze.metrics,
            fairness_constraints=freeze.fairness_constraints,
            ablations=freeze.ablations,
            success_criteria=freeze.success_criteria,
            failure_criteria=freeze.failure_criteria,
            target_venue=freeze.target_venue,
            human_constraints=freeze.human_constraints,
            approved_by=freeze.approved_by,
            status=freeze.status,
        )

    @app.post("/freezes/results", response_model=ResultsFreezeSaveResponse)
    def save_results_freeze(payload: ResultsFreezeSave) -> ResultsFreezeSaveResponse:
        freeze = app.state.freeze_service.save_results_freeze(
            ResultsFreeze(
                results_id=payload.results_id,
                spec_id=payload.spec_id,
                main_claims=payload.main_claims,
                tables=payload.tables,
                figures=payload.figures,
                supporting_run_ids=payload.supporting_run_ids,
                external_sources=payload.external_sources,
                notes=payload.notes,
                approved_by=payload.approved_by,
                status=payload.status,
            )
        )
        return ResultsFreezeSaveResponse(results_id=freeze.results_id)

    @app.get("/freezes/results", response_model=ResultsFreezeRead | None)
    def load_results_freeze() -> ResultsFreezeRead | None:
        freeze = app.state.freeze_service.load_results_freeze()
        if freeze is None:
            return None
        return ResultsFreezeRead(
            results_id=freeze.results_id,
            spec_id=freeze.spec_id,
            main_claims=freeze.main_claims,
            tables=freeze.tables,
            figures=freeze.figures,
            supporting_run_ids=freeze.supporting_run_ids,
            external_sources=freeze.external_sources,
            notes=freeze.notes,
            approved_by=freeze.approved_by,
            status=freeze.status,
        )

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
        depends_on=task.depends_on,
        join_key=task.join_key,
        fanout_group=task.fanout_group,
        max_retries=task.max_retries,
        dispatch_profile=to_record(task.dispatch_profile),
        status=task.status.value,
        experiment_proposal_id=task.experiment_proposal_id,
        last_run_routing=to_record(task.last_run_routing),
        retry_count=task.retry_count,
        last_error=task.last_error,
        next_retry_at=task.next_retry_at,
        checkpoint_path=task.checkpoint_path,
        created_at=task.created_at,
    )


def _to_project_read(project: Project) -> ProjectRead:
    return ProjectRead(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        status=project.status,
        stage=project.stage,
        dispatch_profile=to_record(project.dispatch_profile),
        created_at=project.created_at,
    )


def _to_storage_boundary_read(boundary) -> StorageBoundaryRead:
    return StorageBoundaryRead(
        database_backend=boundary.database_backend,
        database_location=boundary.database_location,
        registry_dir=boundary.registry_dir,
        artifacts_dir=boundary.artifacts_dir,
        freezes_dir=boundary.freezes_dir,
        state_dir=boundary.state_dir,
    )


def _to_project_dashboard_read(dashboard) -> ProjectDashboardRead:
    return ProjectDashboardRead(
        project_id=dashboard.project_id,
        project_name=dashboard.project_name,
        project_status=dashboard.project_status,
        total_tasks=dashboard.total_tasks,
        queued_tasks=dashboard.queued_tasks,
        running_tasks=dashboard.running_tasks,
        waiting_approval_tasks=dashboard.waiting_approval_tasks,
        succeeded_tasks=dashboard.succeeded_tasks,
        failed_tasks=dashboard.failed_tasks,
        cancelled_tasks=dashboard.cancelled_tasks,
        artifact_count=dashboard.artifact_count,
        paper_card_count=dashboard.paper_card_count,
        gap_map_count=dashboard.gap_map_count,
        run_count=dashboard.run_count,
        latest_task_ids=list(dashboard.latest_task_ids),
        topic_freeze_present=dashboard.topic_freeze_present,
        spec_freeze_present=dashboard.spec_freeze_present,
        results_freeze_present=dashboard.results_freeze_present,
        recommended_next_task_kind=dashboard.recommended_next_task_kind,
        recommendation_reason=dashboard.recommendation_reason,
        expected_artifact=dashboard.expected_artifact,
        likely_next_task_kind=dashboard.likely_next_task_kind,
        flow_snapshot={}
        if dashboard.flow_snapshot is None
        else dashboard.flow_snapshot.to_metadata(),
        available_flow_actions=list(dashboard.available_flow_actions),
        storage_boundary=None
        if dashboard.storage_boundary is None
        else _to_storage_boundary_read(dashboard.storage_boundary),
    )


def _to_routing_inspection_read(inspection) -> RoutingInspectionRead:
    return RoutingInspectionRead(
        scope=inspection.scope,
        subject_id=inspection.subject_id,
        resolved_dispatch=ResolvedDispatchModel.model_validate(
            to_record(inspection.resolved_dispatch)
        ),
        provider_health=[
            ProviderHealthSnapshotModel.model_validate(to_record(snapshot))
            for snapshot in inspection.provider_health
        ],
        storage_boundary=None
        if inspection.storage_boundary is None
        else _to_storage_boundary_read(inspection.storage_boundary),
    )


def _to_run_read(run: RunManifest) -> RunManifestRead:
    return RunManifestRead(
        run_id=run.run_id,
        spec_id=run.spec_id,
        git_commit=run.git_commit,
        config_hash=run.config_hash,
        dataset_snapshot=run.dataset_snapshot,
        seed=run.seed,
        gpu=run.gpu,
        experiment_proposal_id=run.experiment_proposal_id,
        experiment_branch=run.experiment_branch,
        start_time=run.start_time,
        end_time=run.end_time,
        status=run.status,
        metrics=run.metrics,
        artifacts=run.artifacts,
        source_type=run.source_type,
        source_label=run.source_label,
        source_metadata=run.source_metadata,
        notes=run.notes,
        dispatch_routing=to_record(run.dispatch_routing),
    )


def _to_lesson_read(lesson: LessonRecord) -> LessonRead:
    return LessonRead(
        lesson_id=lesson.lesson_id,
        lesson_kind=lesson.lesson_kind.value,
        title=lesson.title,
        summary=lesson.summary,
        rationale=lesson.rationale,
        recommended_action=lesson.recommended_action,
        task_kind=lesson.task_kind,
        agent_name=lesson.agent_name,
        tool_name=lesson.tool_name,
        provider_name=lesson.provider_name,
        model_name=lesson.model_name,
        failure_type=lesson.failure_type,
        repository_ref=lesson.repository_ref,
        dataset_ref=lesson.dataset_ref,
        context_tags=lesson.context_tags,
        evidence_refs=lesson.evidence_refs,
        artifact_ids=lesson.artifact_ids,
        source_task_id=lesson.source_task_id,
        source_run_id=lesson.source_run_id,
        source_claim_id=lesson.source_claim_id,
        expires_at=lesson.expires_at,
        hit_count=lesson.hit_count,
        last_hit_at=lesson.last_hit_at,
        is_valid=lesson.is_valid,
        created_at=lesson.created_at,
    )


def _to_verification_read(record) -> VerificationRead:
    return VerificationRead(
        verification_id=record.verification_id,
        subject_type=record.subject_type,
        subject_id=record.subject_id,
        check_type=record.check_type.value,
        status=record.status.value,
        rationale=record.rationale,
        evidence_refs=record.evidence_refs,
        artifact_ids=record.artifact_ids,
        missing_fields=record.missing_fields,
        created_at=record.created_at,
    )


def _to_audit_report_read(report) -> AuditReportRead:
    return AuditReportRead(
        report_type=report.report_type,
        status=report.status,
        findings=report.findings,
        recommendations=report.recommendations,
        entries=[
            AuditEntryRead(
                entry_id=entry.entry_id,
                subject_type=entry.subject_type,
                subject_id=entry.subject_id,
                category=entry.category,
                status=entry.status,
                rationale=entry.rationale,
                evidence_refs=entry.evidence_refs,
                artifact_ids=entry.artifact_ids,
                related_run_ids=entry.related_run_ids,
                related_claim_ids=entry.related_claim_ids,
                created_at=entry.created_at,
            )
            for entry in report.entries
        ],
    )


def _to_artifact_detail_read(
    *,
    artifact,
    provenance: ArtifactProvenance,
    annotations: list[ArtifactAnnotation],
    verification_service: VerificationService,
    audit_service: AuditService,
) -> ArtifactDetailRead:
    verification_records = {
        record.verification_id: record
        for record in verification_service.list_checks_for_artifact(
            artifact.artifact_id,
            run_id=artifact.run_id,
        )
    }
    audit_entries = {
        entry.entry_id: entry
        for entry in audit_service.list_artifact_entries(
            artifact.artifact_id,
            run_id=artifact.run_id,
            verification_service=verification_service,
        )
    }
    return ArtifactDetailRead(
        artifact_id=artifact.artifact_id,
        run_id=artifact.run_id,
        kind=artifact.kind,
        path=artifact.path,
        hash=artifact.hash,
        metadata=artifact.metadata,
        resolved_path=provenance.resolved_path,
        workspace_relative_path=provenance.workspace_relative_path,
        exists_on_disk=provenance.exists_on_disk,
        related_verifications=[
            _to_verification_read_from_link(link, verification_records)
            for link in provenance.verification_links
        ],
        related_audit_entries=[
            _to_audit_entry_read_from_ref(ref, artifact.run_id, audit_entries)
            for ref in provenance.audit_subject_refs
        ],
        evidence_refs=_collect_provenance_evidence_refs(provenance),
        provenance=_to_artifact_provenance_read(provenance),
        annotations=[_to_artifact_annotation_read(annotation) for annotation in annotations],
    )


def _to_artifact_provenance_read(provenance: ArtifactProvenance) -> ArtifactProvenanceRead:
    return ArtifactProvenanceRead(
        artifact_id=provenance.artifact_id,
        run_id=provenance.run_id,
        resolved_path=provenance.resolved_path,
        workspace_relative_path=provenance.workspace_relative_path,
        exists_on_disk=provenance.exists_on_disk,
        run_evidence=None
        if provenance.run_evidence is None
        else _to_run_evidence_ref_read(provenance.run_evidence),
        verification_links=[
            _to_verification_link_read(link) for link in provenance.verification_links
        ],
        audit_subject_refs=[
            _to_audit_subject_ref_read(ref) for ref in provenance.audit_subject_refs
        ],
        claim_support_refs=[
            _to_claim_support_ref_read(ref) for ref in provenance.claim_support_refs
        ],
        freeze_subject_refs=[
            _to_audit_subject_ref_read(ref) for ref in provenance.freeze_subject_refs
        ],
    )


def _to_artifact_annotation_read(annotation: ArtifactAnnotation) -> ArtifactAnnotationRead:
    return ArtifactAnnotationRead(
        annotation_id=annotation.annotation_id,
        artifact_id=annotation.artifact_id,
        operator=annotation.operator,
        status=annotation.status.value,
        review_tags=annotation.review_tags,
        note=annotation.note,
        created_at=annotation.created_at,
    )


def _to_artifact_inspection_read(inspection) -> ArtifactInspectionRead:
    return ArtifactInspectionRead(
        artifact_id=inspection.artifact_id,
        run_id=inspection.run_id,
        kind=inspection.kind,
        path=inspection.path,
        exists_on_disk=inspection.exists_on_disk,
        verification_count=inspection.verification_count,
        audit_entry_count=inspection.audit_entry_count,
        annotation_count=inspection.annotation_count,
        evidence_refs=list(inspection.evidence_refs),
        claim_supports=list(inspection.claim_supports),
        related_freeze_ids=list(inspection.related_freeze_ids),
        metadata=inspection.metadata,
        resolved_path=inspection.resolved_path,
        workspace_relative_path=inspection.workspace_relative_path,
    )


def _to_flow_snapshot_read(snapshot) -> FlowSnapshotRead:
    payload = snapshot.to_metadata()
    return FlowSnapshotRead(
        stage=snapshot.stage.value,
        status=snapshot.status.value,
        decision=snapshot.decision,
        checkpoint_required=snapshot.checkpoint_required,
        active_task_id=snapshot.active_task_id,
        rollback_stage=None if snapshot.rollback_stage is None else snapshot.rollback_stage.value,
        note=snapshot.note,
        updated_at=snapshot.updated_at,
        available_actions=list(available_flow_actions(snapshot)),
        history=list(payload.get("history", [])),
    )


def _to_branch_comparison_read(comparison) -> BranchComparisonRead:
    return BranchComparisonRead(
        project_id=comparison.project_id,
        metric_keys=list(comparison.metric_keys),
        branches=[
            {
                "run_id": branch.run_id,
                "status": branch.status,
                "branch_name": branch.branch_name,
                "primary_metric": branch.primary_metric,
                "primary_value": branch.primary_value,
                "metrics": branch.metrics,
                "source_task_id": branch.source_task_id,
            }
            for branch in comparison.branches
        ],
    )


def _to_verification_read_from_link(
    link: VerificationLink,
    records_by_id: dict[str, VerificationRecord],
) -> VerificationRead:
    record = records_by_id.get(link.verification_id)
    if record is None:
        raise KeyError(f"Verification record not found: {link.verification_id}")
    return VerificationRead(
        verification_id=link.verification_id,
        subject_type=link.subject_type,
        subject_id=link.subject_id,
        check_type=link.check_type,
        status=link.status,
        rationale=link.rationale,
        evidence_refs=[ref.raw_ref for ref in link.evidence_refs],
        artifact_ids=link.artifact_ids,
        missing_fields=link.missing_fields,
        created_at=record.created_at,
    )


def _to_audit_entry_read_from_ref(
    ref: AuditSubjectRef,
    run_id: str,
    entries_by_id: dict[str, AuditEntry],
) -> AuditEntryRead:
    if ref.entry_id is None:
        raise KeyError(f"Audit entry missing id for subject {ref.subject_type}:{ref.subject_id}")
    entry = entries_by_id.get(ref.entry_id)
    if entry is None:
        raise KeyError(f"Audit entry not found: {ref.entry_id}")
    return AuditEntryRead(
        entry_id=ref.entry_id,
        subject_type=ref.subject_type,
        subject_id=ref.subject_id,
        category=ref.category,
        status=ref.status,
        rationale=ref.rationale,
        evidence_refs=[evidence.raw_ref for evidence in ref.evidence_refs],
        artifact_ids=ref.artifact_ids,
        related_run_ids=[run_id] if ref.subject_type == "run" else [],
        related_claim_ids=[ref.subject_id] if ref.subject_type == "claim" else [],
        created_at=entry.created_at,
    )


def _to_verification_link_read(link: VerificationLink) -> VerificationLinkRead:
    return VerificationLinkRead(
        verification_id=link.verification_id,
        subject_type=link.subject_type,
        subject_id=link.subject_id,
        check_type=link.check_type,
        status=link.status,
        rationale=link.rationale,
        evidence_refs=[_to_provenance_evidence_ref_read(ref) for ref in link.evidence_refs],
        artifact_ids=link.artifact_ids,
        missing_fields=link.missing_fields,
    )


def _to_audit_subject_ref_read(ref: AuditSubjectRef) -> AuditSubjectRefRead:
    return AuditSubjectRefRead(
        subject_type=ref.subject_type,
        subject_id=ref.subject_id,
        category=ref.category,
        status=ref.status,
        rationale=ref.rationale,
        entry_id=ref.entry_id,
        evidence_refs=[
            _to_provenance_evidence_ref_read(evidence) for evidence in ref.evidence_refs
        ],
        artifact_ids=ref.artifact_ids,
    )


def _to_claim_support_ref_read(ref: ClaimSupportRef) -> ClaimSupportRefRead:
    return ClaimSupportRefRead(
        claim_id=ref.claim_id,
        support_kind=ref.support_kind,
        support_value=ref.support_value,
    )


def _to_run_evidence_ref_read(ref: RunEvidenceRef) -> RunEvidenceRefRead:
    return RunEvidenceRefRead(
        run_id=ref.run_id,
        spec_id=ref.spec_id,
        status=ref.status,
        artifact_ids=ref.artifact_ids,
    )


def _to_provenance_evidence_ref_read(ref: ProvenanceEvidenceRef) -> ProvenanceEvidenceRefRead:
    return ProvenanceEvidenceRefRead(
        ref_type=ref.ref_type,
        ref_id=ref.ref_id,
        raw_ref=ref.raw_ref,
    )


def _collect_provenance_evidence_refs(provenance: ArtifactProvenance) -> list[str]:
    return sorted(
        {
            ref.raw_ref
            for link in provenance.verification_links
            for ref in link.evidence_refs
        }
        | {
            ref.raw_ref
            for entry in provenance.audit_subject_refs
            for ref in entry.evidence_refs
        }
    )


def _to_discussion_session_read(session) -> DiscussionSessionRead:
    return DiscussionSessionRead(
        session_id=session.session_id,
        project_id=session.project_id,
        title=session.title,
        source_type=session.source_type,
        source_label=session.source_label,
        status=session.status,
        stage=session.stage,
        branch_kind=session.branch_kind,
        target_kind=session.target_kind,
        target_id=session.target_id,
        target_label=session.target_label,
        focus_question=session.focus_question,
        operator_prompt=session.operator_prompt,
        attached_entities=[
            {
                "entity_type": ref.entity_type,
                "entity_id": ref.entity_id,
                "label": ref.label,
            }
            for ref in session.attached_entities
        ],
        context_bundle=None
        if session.context_bundle is None
        else {
            "bundle_id": session.context_bundle.bundle_id,
            "project_id": session.context_bundle.project_id,
            "stage": session.context_bundle.stage,
            "branch_kind": session.context_bundle.branch_kind,
            "target_kind": session.context_bundle.target_kind,
            "target_id": session.context_bundle.target_id,
            "target_label": session.context_bundle.target_label,
            "research_goal": session.context_bundle.research_goal,
            "focus_question": session.context_bundle.focus_question,
            "operator_prompt": session.context_bundle.operator_prompt,
            "current_state": session.context_bundle.current_state,
            "controversies": session.context_bundle.controversies,
            "questions_to_answer": session.context_bundle.questions_to_answer,
            "attached_entities": [
                {
                    "entity_type": ref.entity_type,
                    "entity_id": ref.entity_id,
                    "label": ref.label,
                }
                for ref in session.context_bundle.attached_entities
            ],
            "handoff_packet": session.context_bundle.handoff_packet,
            "created_at": session.context_bundle.created_at,
        },
        latest_import=None
        if session.latest_import is None
        else {
            "source_mode": session.latest_import.source_mode,
            "provider_label": session.latest_import.provider_label,
            "verbatim_text": session.latest_import.verbatim_text,
            "transcript_title": session.latest_import.transcript_title,
            "cited_dois": session.latest_import.cited_dois,
            "referenced_claim_ids": session.latest_import.referenced_claim_ids,
            "imported_at": session.latest_import.imported_at,
        },
        machine_distilled=None
        if session.machine_distilled is None
        else {
            "summary": session.machine_distilled.summary,
            "findings": session.machine_distilled.findings,
            "decisions": session.machine_distilled.decisions,
            "literature_notes": session.machine_distilled.literature_notes,
            "open_questions": session.machine_distilled.open_questions,
            "risks": session.machine_distilled.risks,
            "counterarguments": session.machine_distilled.counterarguments,
            "suggested_next_actions": session.machine_distilled.suggested_next_actions,
            "cited_dois": session.machine_distilled.cited_dois,
            "referenced_claim_ids": session.machine_distilled.referenced_claim_ids,
        },
        adopted_decision=None
        if session.adopted_decision is None
        else {
            "summary": session.adopted_decision.summary,
            "findings": session.adopted_decision.findings,
            "decisions": session.adopted_decision.decisions,
            "literature_notes": session.adopted_decision.literature_notes,
            "open_questions": session.adopted_decision.open_questions,
            "risks": session.adopted_decision.risks,
            "counterarguments": session.adopted_decision.counterarguments,
            "suggested_next_actions": session.adopted_decision.suggested_next_actions,
            "cited_dois": session.adopted_decision.cited_dois,
            "referenced_claim_ids": session.adopted_decision.referenced_claim_ids,
        },
        coverage_report=None
        if session.coverage_report is None
        else {
            "checks": [
                {
                    "ref": check.ref,
                    "ref_type": check.ref_type,
                    "status": check.status,
                    "note": check.note,
                    "linked_entity_id": check.linked_entity_id,
                }
                for check in session.coverage_report.checks
            ],
            "summary": session.coverage_report.summary,
        },
        promoted_record_ids=session.promoted_record_ids,
        metadata=session.metadata,
        created_at=session.created_at,
        updated_at=session.updated_at,
    )


def _guide_next_step(stop_reason: str) -> str:
    if stop_reason == "human_select_ready":
        return "请查看候选 idea，选择一个方向继续自动推进。"
    if stop_reason == "blocked":
        return "自动流程被阻塞，请检查当前任务的错误或缺少的输入。"
    if stop_reason == "waiting_approval":
        return "当前流程进入待审批状态，需要人工确认。"
    if stop_reason == "failed":
        return "自动流程失败，请检查任务控制台中的失败任务。"
    if stop_reason == "running":
        return "自动流程仍在运行中，稍后刷新查看最新结果。"
    if stop_reason == "idle":
        return "当前没有可自动推进的任务。"
    if stop_reason == "dispatch_limit_reached":
        return "本轮已完成一批自动推进，可再次点击继续。"
    return "自动流程已启动。"
