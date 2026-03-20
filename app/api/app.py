from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException

from app.api.deps import get_project_service, get_task_service
from app.api.schemas import (
    AuditEntryRead,
    AuditReportRead,
    ApprovalCreate,
    ApprovalRead,
    ClaimCreate,
    ClaimRead,
    EvidenceRefModel,
    GapCreate,
    GapClusterCreate,
    GapMapCreate,
    GapMapCreateResponse,
    GapMapRead,
    GapMapSummaryRead,
    LessonCreate,
    LessonRead,
    PaperCardCreate,
    PaperCardCreateResponse,
    PaperCardRead,
    PaperCardSummaryRead,
    ProjectCreate,
    ProjectRead,
    ResultsFreezeRead,
    ResultsFreezeSave,
    ResultsFreezeSaveResponse,
    RunManifestCreate,
    RunManifestRead,
    SpecFreezeRead,
    SpecFreezeSave,
    SpecFreezeSaveResponse,
    TaskCreate,
    TaskRead,
    TaskStatusUpdate,
    TopicFreezeRead,
    TopicFreezeSave,
    TopicFreezeSaveResponse,
    VerificationRead,
)
from app.bootstrap import build_runtime_services
from app.core.config import load_config
from app.routing import dispatch_profile_from_dict
from app.schemas.approval import Approval
from app.schemas.claim import Claim
from app.schemas.freeze import ResultsFreeze, SpecFreeze, TopicFreeze
from app.schemas.gap_map import Gap, GapCluster, GapMap
from app.schemas.lesson import LessonKind, LessonRecord
from app.schemas.paper_card import EvidenceRef, PaperCard
from app.schemas.project import Project
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task, TaskStatus
from app.schemas.verification import VerificationCheckType, VerificationStatus
from app.services.audit_service import AuditService
from app.services.lessons_service import LessonsService
from app.services.project_service import ProjectService
from app.services.registry_store import to_record
from app.services.task_service import TaskService
from app.services.verification_service import VerificationService
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
    app.state.lessons_service = services.lessons_service
    app.state.verification_service = services.verification_service
    app.state.audit_service = services.audit_service
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
                dispatch_profile=dispatch_profile_from_dict(
                    payload.dispatch_profile.model_dump() if payload.dispatch_profile is not None else None
                ),
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
        return _to_run_read(run)

    @app.get("/runs", response_model=list[RunManifestRead])
    def list_runs() -> list[RunManifestRead]:
        return [_to_run_read(run) for run in app.state.run_service.list_runs()]

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

    @app.get("/audit/claims", response_model=AuditReportRead)
    def get_claim_audit_report() -> AuditReportRead:
        return _to_audit_report_read(app.state.audit_service.build_claim_alignment_report())

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
                                attack_surface=gap.attack_surface,
                                difficulty=gap.difficulty,
                                novelty_type=gap.novelty_type,
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
        dispatch_profile=to_record(task.dispatch_profile),
        status=task.status.value,
        last_run_routing=to_record(task.last_run_routing),
        created_at=task.created_at,
    )


def _to_project_read(project: Project) -> ProjectRead:
    return ProjectRead(
        project_id=project.project_id,
        name=project.name,
        description=project.description,
        status=project.status,
        dispatch_profile=to_record(project.dispatch_profile),
        created_at=project.created_at,
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
        start_time=run.start_time,
        end_time=run.end_time,
        status=run.status,
        metrics=run.metrics,
        artifacts=run.artifacts,
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
