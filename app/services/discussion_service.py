from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.approval import Approval
from app.schemas.discussion import (
    DiscussionContextBundle,
    DiscussionCoverageCheck,
    DiscussionCoverageReport,
    DiscussionDistillation,
    DiscussionEntityRef,
    DiscussionImportRecord,
    DiscussionSession,
)
from app.schemas.freeze import ResultsFreeze, SpecFreeze, TopicFreeze
from app.schemas.paper_card import PaperCard
from app.schemas.project import Project
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task
from app.services.registry_store import read_jsonl, to_record, upsert_jsonl


class DiscussionService:
    _DOI_PATTERN = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+\b", re.IGNORECASE)
    _CLAIM_PATTERN = re.compile(r"\bclaim[-_:A-Za-z0-9]+\b", re.IGNORECASE)

    def __init__(
        self,
        registry_path: str | Path = "registry/discussions.jsonl",
        *,
        project_service,
        task_service,
        paper_card_service,
        gap_map_service,
        freeze_service,
        run_service,
        claim_service,
        kb_service,
        approval_service,
        activity_service=None,
    ) -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()
        self.project_service = project_service
        self.task_service = task_service
        self.paper_card_service = paper_card_service
        self.gap_map_service = gap_map_service
        self.freeze_service = freeze_service
        self.run_service = run_service
        self.claim_service = claim_service
        self.kb_service = kb_service
        self.approval_service = approval_service
        self.activity_service = activity_service

    def create_session(
        self,
        *,
        session_id: str,
        project_id: str,
        title: str,
        source_type: str,
        source_label: str,
        branch_kind: str,
        target_kind: str,
        target_id: str,
        target_label: str,
        focus_question: str,
        operator_prompt: str,
        questions_to_answer: list[str] | None = None,
        attached_entities: list[DiscussionEntityRef] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DiscussionSession:
        project = self._require_project(project_id)
        refs = self._normalize_refs(
            attached_entities or [],
            target_kind=target_kind,
            target_id=target_id,
            target_label=target_label,
        )
        bundle = self._build_context_bundle(
            session_id=session_id,
            project=project,
            branch_kind=branch_kind,
            target_kind=target_kind,
            target_id=target_id,
            target_label=target_label,
            focus_question=focus_question,
            operator_prompt=operator_prompt,
            questions_to_answer=questions_to_answer or [],
            attached_entities=refs,
        )
        now = datetime.now(timezone.utc)
        session = DiscussionSession(
            session_id=session_id,
            project_id=project_id,
            title=title.strip() or f"{branch_kind} discussion",
            source_type=source_type.strip() or "web_handoff",
            source_label=source_label.strip(),
            status="draft",
            stage=project.stage.name if hasattr(project.stage, "name") else str(project.stage),
            branch_kind=branch_kind.strip() or "idea-branch",
            target_kind=target_kind.strip() or "project",
            target_id=target_id.strip(),
            target_label=target_label.strip(),
            focus_question=focus_question.strip(),
            operator_prompt=operator_prompt.strip(),
            attached_entities=refs,
            context_bundle=bundle,
            metadata=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        self._save_session(session)
        self._record_event(
            project_id,
            event_type="discussion.created",
            message=f"Discussion session created: {session.session_id}",
            payload={
                "target_kind": session.target_kind,
                "target_id": session.target_id,
                "branch_kind": session.branch_kind,
                "source_type": session.source_type,
            },
        )
        return session

    def list_sessions(self, *, project_id: str | None = None) -> list[DiscussionSession]:
        rows = read_jsonl(self.registry_path)
        sessions = [self._row_to_session(row) for row in rows]
        if project_id is not None:
            sessions = [session for session in sessions if session.project_id == project_id]
        sessions.sort(key=lambda item: item.updated_at, reverse=True)
        return sessions

    def get_session(self, session_id: str) -> DiscussionSession | None:
        for session in self.list_sessions():
            if session.session_id == session_id:
                return session
        return None

    def import_result(
        self,
        session_id: str,
        *,
        source_mode: str,
        provider_label: str,
        verbatim_text: str,
        transcript_title: str = "",
        cited_dois: list[str] | None = None,
        referenced_claim_ids: list[str] | None = None,
        findings: list[str] | None = None,
        decisions: list[str] | None = None,
        literature_notes: list[str] | None = None,
        open_questions: list[str] | None = None,
        risks: list[str] | None = None,
        counterarguments: list[str] | None = None,
        suggested_next_actions: list[str] | None = None,
        summary: str = "",
    ) -> DiscussionSession:
        session = self._require_session(session_id)
        raw_text = verbatim_text.strip()
        if not raw_text:
            raise ValueError("verbatim_text is required")

        normalized_dois = self._unique_strings([*(cited_dois or []), *self._extract_dois(raw_text)])
        normalized_claim_ids = self._unique_strings(
            [*(referenced_claim_ids or []), *self._extract_claim_ids(raw_text)]
        )
        distillation = DiscussionDistillation(
            summary=summary.strip() or self._first_paragraph(raw_text),
            findings=self._resolve_or_extract(findings, raw_text, keywords=("finding", "observation", "evidence", "发现", "观察")),
            decisions=self._resolve_or_extract(decisions, raw_text, keywords=("decision", "recommend", "should", "结论", "建议", "决定")),
            literature_notes=self._resolve_or_extract(literature_notes, raw_text, keywords=("paper", "doi", "literature", "论文", "文献")),
            open_questions=self._resolve_or_extract(open_questions, raw_text, keywords=("question", "unknown", "unclear", "待确认", "疑问", "?")),
            risks=self._resolve_or_extract(risks, raw_text, keywords=("risk", "concern", "weakness", "limitation", "风险", "问题", "局限")),
            counterarguments=self._resolve_or_extract(counterarguments, raw_text, keywords=("counter", "however", "but", "反驳", "反方", "但是")),
            suggested_next_actions=self._resolve_or_extract(
                suggested_next_actions,
                raw_text,
                keywords=("next", "action", "follow", "recommend", "下一步", "行动", "建议"),
            ),
            cited_dois=normalized_dois,
            referenced_claim_ids=normalized_claim_ids,
        )
        if not distillation.decisions and distillation.summary:
            distillation.decisions = [distillation.summary]
        if not distillation.suggested_next_actions:
            distillation.suggested_next_actions = self._default_next_actions(session)
        coverage = self._build_coverage_report(
            cited_dois=normalized_dois,
            referenced_claim_ids=normalized_claim_ids,
        )
        session.latest_import = DiscussionImportRecord(
            source_mode=source_mode.strip() or "web",
            provider_label=provider_label.strip(),
            verbatim_text=raw_text,
            transcript_title=transcript_title.strip(),
            cited_dois=normalized_dois,
            referenced_claim_ids=normalized_claim_ids,
        )
        session.machine_distilled = distillation
        session.coverage_report = coverage
        session.status = "imported"
        session.updated_at = datetime.now(timezone.utc)
        self._save_session(session)
        self._record_event(
            session.project_id,
            event_type="discussion.imported",
            message=f"Discussion result imported: {session.session_id}",
            payload={
                "source_mode": session.latest_import.source_mode,
                "provider_label": session.latest_import.provider_label,
                "coverage_summary": coverage.summary,
            },
        )
        return session

    def adopt_session(
        self,
        session_id: str,
        *,
        approved_by: str,
        adopted_summary: str = "",
        route_to_kb: bool = True,
    ) -> DiscussionSession:
        session = self._require_session(session_id)
        distilled = session.machine_distilled or DiscussionDistillation(summary=adopted_summary.strip())
        session.adopted_decision = replace(
            distilled,
            summary=adopted_summary.strip() or distilled.summary,
        )
        session.status = "adopted"
        session.updated_at = datetime.now(timezone.utc)
        if route_to_kb:
            kb_ids = self.promote_to_kb(session_id)
            session = self._require_session(session_id)
            session.promoted_record_ids["kb"] = kb_ids
            session.adopted_decision = replace(
                distilled,
                summary=adopted_summary.strip() or distilled.summary,
            )
            session.status = "adopted"
            session.updated_at = datetime.now(timezone.utc)
        session.metadata["adopted_by"] = approved_by.strip() or "operator"
        self._save_session(session)
        self._record_event(
            session.project_id,
            event_type="discussion.adopted",
            message=f"Discussion adopted into project memory: {session.session_id}",
            payload={"approved_by": session.metadata["adopted_by"]},
        )
        return session

    def promote_to_kb(self, session_id: str) -> list[str]:
        session = self._require_session(session_id)
        if session.promoted_record_ids.get("kb"):
            return session.promoted_record_ids["kb"]
        distilled = session.machine_distilled or session.adopted_decision
        if distilled is None:
            raise ValueError("discussion session has no distilled result to promote")
        project = self._require_project(session.project_id)
        context_tags = self._build_context_tags(session)
        created_ids: list[str] = []

        for index, item in enumerate(distilled.findings):
            record_id = f"discussion:{session.session_id}:finding:{index + 1}"
            self.kb_service.record_finding(
                self._kb_record(project.project_id, record_id, f"{session.title} finding", item, context_tags)
            )
            created_ids.append(record_id)
        for index, item in enumerate(distilled.decisions):
            record_id = f"discussion:{session.session_id}:decision:{index + 1}"
            self.kb_service.record_decision(
                self._kb_record(project.project_id, record_id, f"{session.title} decision", item, context_tags)
            )
            created_ids.append(record_id)
        literature_entries = list(distilled.literature_notes)
        for doi in distilled.cited_dois:
            label = f"Referenced DOI {doi}"
            if label not in literature_entries:
                literature_entries.append(label)
        for index, item in enumerate(literature_entries):
            record_id = f"discussion:{session.session_id}:literature:{index + 1}"
            self.kb_service.record_literature(
                self._kb_record(project.project_id, record_id, f"{session.title} literature", item, context_tags)
            )
            created_ids.append(record_id)
        for index, item in enumerate(distilled.open_questions):
            record_id = f"discussion:{session.session_id}:question:{index + 1}"
            self.kb_service.record_open_question(
                self._kb_record(project.project_id, record_id, f"{session.title} open question", item, context_tags)
            )
            created_ids.append(record_id)

        session.promoted_record_ids["kb"] = created_ids
        session.updated_at = datetime.now(timezone.utc)
        self._save_session(session)
        return created_ids

    def promote_to_approval(
        self,
        session_id: str,
        *,
        approved_by: str,
    ) -> str:
        session = self._require_session(session_id)
        existing = session.promoted_record_ids.get("approval", [])
        if existing:
            return existing[0]
        distilled = session.machine_distilled or session.adopted_decision
        if distilled is None:
            raise ValueError("discussion session has no distilled result to promote")
        approval_id = f"discussion-{session.session_id}-approval"
        approval = self.approval_service.record_approval(
            Approval(
                approval_id=approval_id,
                project_id=session.project_id,
                target_type=session.target_kind,
                target_id=session.target_id,
                approved_by=approved_by.strip() or "operator",
                decision="pending",
                comment="Generated from imported discussion session.",
                context_summary=distilled.summary,
                recommended_action=distilled.suggested_next_actions[0]
                if distilled.suggested_next_actions
                else distilled.summary,
            )
        )
        session.promoted_record_ids["approval"] = [approval.approval_id]
        session.updated_at = datetime.now(timezone.utc)
        self._save_session(session)
        return approval.approval_id

    def promote_to_task(
        self,
        session_id: str,
        *,
        owner: str,
        task_kind: str = "",
        task_goal: str = "",
    ) -> str:
        session = self._require_session(session_id)
        existing = session.promoted_record_ids.get("task", [])
        if existing:
            return existing[0]
        distilled = session.machine_distilled or session.adopted_decision
        if distilled is None:
            raise ValueError("discussion session has no distilled result to promote")
        resolved_kind = task_kind.strip() or self._infer_task_kind(session)
        resolved_goal = task_goal.strip() or (
            distilled.suggested_next_actions[0]
            if distilled.suggested_next_actions
            else f"Follow up discussion session {session.session_id}"
        )
        task_id = self._unique_task_id(f"{session.project_id}-{session.branch_kind}-{resolved_kind}")
        task = self.task_service.create_task(
            Task(
                task_id=task_id,
                project_id=session.project_id,
                kind=resolved_kind,
                goal=resolved_goal,
                input_payload={
                    "discussion_session_id": session.session_id,
                    "discussion_branch_kind": session.branch_kind,
                    "discussion_target_kind": session.target_kind,
                    "discussion_target_id": session.target_id,
                    "discussion_summary": distilled.summary,
                    "discussion_decisions": distilled.decisions,
                    "discussion_risks": distilled.risks,
                    "discussion_open_questions": distilled.open_questions,
                },
                owner=owner.strip() or "operator",
            )
        )
        session.promoted_record_ids["task"] = [task.task_id]
        session.updated_at = datetime.now(timezone.utc)
        self._save_session(session)
        return task.task_id

    def _save_session(self, session: DiscussionSession) -> None:
        upsert_jsonl(self.registry_path, "session_id", to_record(session))

    def _build_context_bundle(
        self,
        *,
        session_id: str,
        project: Project,
        branch_kind: str,
        target_kind: str,
        target_id: str,
        target_label: str,
        focus_question: str,
        operator_prompt: str,
        questions_to_answer: list[str],
        attached_entities: list[DiscussionEntityRef],
    ) -> DiscussionContextBundle:
        target_payload = self._resolve_entity(target_kind, target_id)
        attachment_payloads = [self._resolve_entity(ref.entity_type, ref.entity_id) for ref in attached_entities]
        open_questions = self.kb_service.search_bucket(
            "open_questions",
            query=project.description or project.name,
            limit=5,
            current_project_id=project.project_id,
        )
        controversies = self._collect_controversies(target_payload, attachment_payloads, open_questions)
        questions = self._unique_strings(
            [question for question in questions_to_answer if question.strip()]
            or [focus_question.strip()]
            or [self._default_focus_question(target_kind, target_label or target_id)]
        )
        current_state = {
            "project": {
                "project_id": project.project_id,
                "name": project.name,
                "description": project.description,
                "stage": project.stage.name if hasattr(project.stage, "name") else str(project.stage),
            },
            "target": target_payload,
            "attachments": attachment_payloads,
            "open_questions": open_questions,
        }
        packet = {
            "mode": "research_discussion_handoff",
            "project": current_state["project"],
            "branch_kind": branch_kind,
            "target_kind": target_kind,
            "target_id": target_id,
            "focus_question": focus_question.strip(),
            "operator_prompt": operator_prompt.strip(),
            "questions_to_answer": questions,
            "controversies": controversies,
            "target": target_payload,
            "attachments": attachment_payloads,
            "instruction": (
                "Challenge the current direction, identify evidence gaps, call out risks, "
                "and propose concrete next actions in a structured way."
            ),
        }
        return DiscussionContextBundle(
            bundle_id=f"bundle:{session_id}",
            project_id=project.project_id,
            stage=current_state["project"]["stage"],
            branch_kind=branch_kind,
            target_kind=target_kind,
            target_id=target_id,
            target_label=target_label,
            research_goal=project.description,
            focus_question=focus_question.strip(),
            operator_prompt=operator_prompt.strip(),
            current_state=current_state,
            controversies=controversies,
            questions_to_answer=questions,
            attached_entities=attached_entities,
            handoff_packet=json.dumps(packet, ensure_ascii=False, indent=2),
        )

    def _build_coverage_report(
        self,
        *,
        cited_dois: list[str],
        referenced_claim_ids: list[str],
    ) -> DiscussionCoverageReport:
        checks: list[DiscussionCoverageCheck] = []
        for doi in cited_dois:
            card = self.paper_card_service.get_card(doi)
            checks.append(
                DiscussionCoverageCheck(
                    ref=doi,
                    ref_type="doi",
                    status="covered" if card is not None else "missing",
                    note="Paper card is registered." if card is not None else "No local paper card found for this DOI.",
                    linked_entity_id=card.paper_id if card is not None else None,
                )
            )
        for claim_id in referenced_claim_ids:
            claim = self.claim_service.get_claim(claim_id)
            if claim is None:
                checks.append(
                    DiscussionCoverageCheck(
                        ref=claim_id,
                        ref_type="claim",
                        status="missing",
                        note="Claim is referenced in the discussion but not registered locally.",
                    )
                )
                continue
            covered = bool(claim.supported_by_runs or claim.supported_by_tables)
            checks.append(
                DiscussionCoverageCheck(
                    ref=claim_id,
                    ref_type="claim",
                    status="covered" if covered else "partial",
                    note="Claim has support references." if covered else "Claim exists but has no linked run/table support.",
                    linked_entity_id=claim.claim_id,
                )
            )
        summary = (
            "All referenced evidence is covered."
            if checks and all(check.status == "covered" for check in checks)
            else "Discussion references include gaps that still need local evidence coverage."
            if checks
            else "No explicit DOI or claim references were detected in the imported discussion."
        )
        return DiscussionCoverageReport(checks=checks, summary=summary)

    def _resolve_entity(self, entity_type: str, entity_id: str) -> dict[str, Any]:
        entity_type = entity_type.strip()
        entity_id = entity_id.strip()
        if entity_type in {"doi", "paper_card"}:
            card = self.paper_card_service.get_card(entity_id)
            if card is not None:
                return self._paper_card_payload(entity_type, card)
            return {
                "entity_type": entity_type,
                "entity_id": entity_id,
                "label": entity_id,
                "status": "external_only",
                "summary": "No local paper card is registered for this DOI/paper id yet.",
            }
        if entity_type == "project":
            project = self.project_service.get_project(entity_id)
            if project is not None:
                return {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "label": project.name,
                    "summary": project.description,
                    "stage": project.stage.name if hasattr(project.stage, "name") else str(project.stage),
                    "status": project.status,
                }
        if entity_type == "task":
            task = self.task_service.get_task(entity_id)
            if task is not None:
                return {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "label": task.goal,
                    "status": task.status.value,
                    "kind": task.kind,
                    "summary": task.goal,
                    "input_payload": task.input_payload,
                }
        if entity_type == "run":
            run = self.run_service.get_run(entity_id)
            if run is not None:
                return self._run_payload(run)
        if entity_type == "claim":
            claim = self.claim_service.get_claim(entity_id)
            if claim is not None:
                return {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "label": claim.text,
                    "claim_type": claim.claim_type,
                    "risk_level": claim.risk_level,
                    "supported_by_runs": claim.supported_by_runs,
                    "supported_by_tables": claim.supported_by_tables,
                }
        if entity_type == "topic_freeze":
            freeze = self.freeze_service.load_topic_freeze()
            if freeze is not None and freeze.topic_id == entity_id:
                return self._topic_freeze_payload(freeze)
        if entity_type == "spec_freeze":
            freeze = self.freeze_service.load_spec_freeze()
            if freeze is not None and freeze.spec_id == entity_id:
                return self._spec_freeze_payload(freeze)
        if entity_type == "results_freeze":
            freeze = self.freeze_service.load_results_freeze()
            if freeze is not None and freeze.results_id == entity_id:
                return self._results_freeze_payload(freeze)
        if entity_type == "gap":
            gap = self._find_gap(entity_id)
            if gap is not None:
                return gap
        return {
            "entity_type": entity_type,
            "entity_id": entity_id,
            "label": entity_id,
            "status": "unresolved",
            "summary": "ResearchOS could not fully resolve this entity from local state.",
        }

    def _find_gap(self, gap_id: str) -> dict[str, Any] | None:
        for gap_map in self.gap_map_service.list_gap_maps():
            for cluster in gap_map.clusters:
                for gap in cluster.gaps:
                    if gap.gap_id != gap_id:
                        continue
                    return {
                        "entity_type": "gap",
                        "entity_id": gap_id,
                        "label": gap.description,
                        "topic": gap_map.topic,
                        "cluster": cluster.name,
                        "description": gap.description,
                        "supporting_papers": gap.supporting_papers,
                        "attack_surface": gap.attack_surface,
                        "difficulty": gap.difficulty,
                        "novelty_type": gap.novelty_type,
                    }
        return None

    def _collect_controversies(
        self,
        target_payload: dict[str, Any],
        attachment_payloads: list[dict[str, Any]],
        open_questions: list[dict[str, object]],
    ) -> list[str]:
        controversies: list[str] = []
        for payload in [target_payload, *attachment_payloads]:
            for key in ("likely_failure_modes", "repro_risks", "hidden_dependencies", "risks"):
                values = payload.get(key, [])
                if isinstance(values, list):
                    controversies.extend(str(item).strip() for item in values if str(item).strip())
            risk_level = str(payload.get("risk_level", "")).strip()
            if risk_level:
                controversies.append(f"Risk level: {risk_level}")
        controversies.extend(str(item.get("summary", "")).strip() for item in open_questions if str(item.get("summary", "")).strip())
        return self._unique_strings(controversies)[:8]

    def _build_context_tags(self, session: DiscussionSession) -> list[str]:
        tags = [
            session.branch_kind,
            session.target_kind,
            session.target_id,
            session.source_type,
            *(ref.entity_id for ref in session.attached_entities),
        ]
        return self._unique_strings(tags)

    def _kb_record(self, project_id: str, record_id: str, title: str, summary: str, tags: list[str]):
        from app.services.kb_service import KnowledgeRecord

        return KnowledgeRecord(
            record_id=record_id,
            project_id=project_id,
            title=title,
            summary=summary,
            context_tags=tags,
            payload={"source": "discussion"},
        )

    def _infer_task_kind(self, session: DiscussionSession) -> str:
        if session.branch_kind == "writing-branch":
            return "write_draft"
        if session.target_kind == "spec_freeze":
            return "build_spec"
        if session.target_kind == "run":
            return "analyze_run"
        if session.target_kind == "claim":
            return "verify_claim"
        if session.target_kind in {"gap", "topic_freeze"}:
            return "hypothesis_draft"
        return "review_build"

    def _default_next_actions(self, session: DiscussionSession) -> list[str]:
        if session.target_kind == "spec_freeze":
            return ["Refine the spec freeze and tighten the experiment criteria."]
        if session.target_kind == "run":
            return ["Audit the run anomalies before using the result in a claim."]
        if session.target_kind == "claim":
            return ["Verify the claim support chain before freezing results."]
        if session.branch_kind == "writing-branch":
            return ["Translate the discussion into a tighter draft section with explicit caveats."]
        return ["Convert the discussion into one bounded follow-up task with explicit evidence requirements."]

    def _default_focus_question(self, target_kind: str, target_label: str) -> str:
        return f"What is the strongest next decision for {target_kind}:{target_label} given the current evidence?"

    def _paper_card_payload(self, entity_type: str, card: PaperCard) -> dict[str, Any]:
        return {
            "entity_type": entity_type,
            "entity_id": card.paper_id,
            "label": card.title,
            "summary": card.method_summary or card.problem,
            "problem": card.problem,
            "setting": card.setting,
            "task_type": card.task_type,
            "claimed_contributions": card.claimed_contributions,
            "hidden_dependencies": card.hidden_dependencies,
            "likely_failure_modes": card.likely_failure_modes,
            "repro_risks": card.repro_risks,
        }

    @staticmethod
    def _run_payload(run: RunManifest) -> dict[str, Any]:
        return {
            "entity_type": "run",
            "entity_id": run.run_id,
            "label": run.run_id,
            "status": run.status,
            "spec_id": run.spec_id,
            "metrics": run.metrics,
            "artifacts": run.artifacts,
            "source_type": run.source_type,
            "source_label": run.source_label,
            "notes": run.notes,
        }

    @staticmethod
    def _topic_freeze_payload(freeze: TopicFreeze) -> dict[str, Any]:
        return {
            "entity_type": "topic_freeze",
            "entity_id": freeze.topic_id,
            "label": freeze.research_question,
            "research_question": freeze.research_question,
            "selected_gap_ids": freeze.selected_gap_ids,
            "novelty_type": freeze.novelty_type,
            "status": freeze.status,
        }

    @staticmethod
    def _spec_freeze_payload(freeze: SpecFreeze) -> dict[str, Any]:
        return {
            "entity_type": "spec_freeze",
            "entity_id": freeze.spec_id,
            "label": freeze.spec_id,
            "hypothesis": freeze.hypothesis,
            "datasets": freeze.datasets,
            "metrics": freeze.metrics,
            "must_beat_baselines": freeze.must_beat_baselines,
            "human_constraints": freeze.human_constraints,
            "status": freeze.status,
        }

    @staticmethod
    def _results_freeze_payload(freeze: ResultsFreeze) -> dict[str, Any]:
        return {
            "entity_type": "results_freeze",
            "entity_id": freeze.results_id,
            "label": freeze.results_id,
            "main_claims": freeze.main_claims,
            "supporting_run_ids": freeze.supporting_run_ids,
            "external_sources": freeze.external_sources,
            "notes": freeze.notes,
            "status": freeze.status,
        }

    def _require_project(self, project_id: str) -> Project:
        project = self.project_service.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        return project

    def _require_session(self, session_id: str) -> DiscussionSession:
        session = self.get_session(session_id)
        if session is None:
            raise KeyError(f"Discussion session not found: {session_id}")
        return session

    def _record_event(
        self,
        project_id: str,
        *,
        event_type: str,
        message: str,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self.activity_service is None:
            return
        from app.schemas.activity import RunEvent

        self.activity_service.record_event(
            RunEvent(
                project_id=project_id,
                event_type=event_type,
                message=message,
                payload=dict(payload or {}),
            )
        )

    def _unique_task_id(self, prefix: str) -> str:
        normalized = prefix.lower().replace(" ", "-").replace("_", "-")
        candidate = normalized
        index = 1
        while self.task_service.get_task(candidate) is not None:
            index += 1
            candidate = f"{normalized}-{index}"
        return candidate

    def _normalize_refs(
        self,
        refs: list[Any],
        *,
        target_kind: str,
        target_id: str,
        target_label: str,
    ) -> list[DiscussionEntityRef]:
        normalized_refs: list[DiscussionEntityRef] = []
        for ref in refs:
            if isinstance(ref, DiscussionEntityRef):
                normalized_refs.append(ref)
                continue
            if isinstance(ref, dict):
                normalized_refs.append(
                    DiscussionEntityRef(
                        entity_type=str(ref.get("entity_type", "")),
                        entity_id=str(ref.get("entity_id", "")),
                        label=str(ref.get("label", "")),
                    )
                )
        combined = [DiscussionEntityRef(entity_type=target_kind, entity_id=target_id, label=target_label), *normalized_refs]
        unique: list[DiscussionEntityRef] = []
        seen: set[tuple[str, str]] = set()
        for ref in combined:
            key = (ref.entity_type.strip(), ref.entity_id.strip())
            if key in seen or not key[0] or not key[1]:
                continue
            seen.add(key)
            unique.append(
                DiscussionEntityRef(
                    entity_type=key[0],
                    entity_id=key[1],
                    label=ref.label.strip(),
                )
            )
        return unique

    @classmethod
    def _extract_dois(cls, text: str) -> list[str]:
        return cls._unique_strings(match.group(0).rstrip(".,)") for match in cls._DOI_PATTERN.finditer(text))

    @classmethod
    def _extract_claim_ids(cls, text: str) -> list[str]:
        return cls._unique_strings(match.group(0) for match in cls._CLAIM_PATTERN.finditer(text))

    @classmethod
    def _resolve_or_extract(
        cls,
        provided: list[str] | None,
        text: str,
        *,
        keywords: tuple[str, ...],
    ) -> list[str]:
        if provided:
            return cls._unique_strings(item.strip() for item in provided if item.strip())
        lines = cls._candidate_lines(text)
        matched = [
            line for line in lines if any(keyword.lower() in line.lower() for keyword in keywords)
        ]
        return cls._unique_strings(matched[:4] or lines[:3])

    @staticmethod
    def _candidate_lines(text: str) -> list[str]:
        lines = [
            line.strip(" -*\t")
            for chunk in text.splitlines()
            for line in chunk.split("。")
        ]
        return [line.strip() for line in lines if len(line.strip()) > 12]

    @staticmethod
    def _first_paragraph(text: str) -> str:
        for block in text.splitlines():
            normalized = block.strip()
            if normalized:
                return normalized[:360]
        return text.strip()[:360]

    @staticmethod
    def _unique_strings(items) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for item in items:
            value = str(item).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            normalized.append(value)
        return normalized

    @staticmethod
    def _row_to_session(row: dict[str, Any]) -> DiscussionSession:
        return DiscussionSession(
            session_id=str(row["session_id"]),
            project_id=str(row["project_id"]),
            title=str(row["title"]),
            source_type=str(row.get("source_type", "web_handoff")),
            source_label=str(row.get("source_label", "")),
            status=str(row.get("status", "draft")),
            stage=str(row.get("stage", "")),
            branch_kind=str(row.get("branch_kind", "idea-branch")),
            target_kind=str(row.get("target_kind", "project")),
            target_id=str(row.get("target_id", "")),
            target_label=str(row.get("target_label", "")),
            focus_question=str(row.get("focus_question", "")),
            operator_prompt=str(row.get("operator_prompt", "")),
            attached_entities=[
                DiscussionEntityRef(
                    entity_type=str(item.get("entity_type", "")),
                    entity_id=str(item.get("entity_id", "")),
                    label=str(item.get("label", "")),
                )
                for item in row.get("attached_entities", [])
                if isinstance(item, dict)
            ],
            context_bundle=None
            if not isinstance(row.get("context_bundle"), dict)
            else DiscussionContextBundle(
                bundle_id=str(row["context_bundle"].get("bundle_id", "")),
                project_id=str(row["context_bundle"].get("project_id", "")),
                stage=str(row["context_bundle"].get("stage", "")),
                branch_kind=str(row["context_bundle"].get("branch_kind", "idea-branch")),
                target_kind=str(row["context_bundle"].get("target_kind", "project")),
                target_id=str(row["context_bundle"].get("target_id", "")),
                target_label=str(row["context_bundle"].get("target_label", "")),
                research_goal=str(row["context_bundle"].get("research_goal", "")),
                focus_question=str(row["context_bundle"].get("focus_question", "")),
                operator_prompt=str(row["context_bundle"].get("operator_prompt", "")),
                current_state=dict(row["context_bundle"].get("current_state", {})),
                controversies=[str(item) for item in row["context_bundle"].get("controversies", [])],
                questions_to_answer=[str(item) for item in row["context_bundle"].get("questions_to_answer", [])],
                attached_entities=[
                    DiscussionEntityRef(
                        entity_type=str(item.get("entity_type", "")),
                        entity_id=str(item.get("entity_id", "")),
                        label=str(item.get("label", "")),
                    )
                    for item in row["context_bundle"].get("attached_entities", [])
                    if isinstance(item, dict)
                ],
                handoff_packet=str(row["context_bundle"].get("handoff_packet", "")),
                created_at=datetime.fromisoformat(str(row["context_bundle"].get("created_at"))),
            ),
            latest_import=None
            if not isinstance(row.get("latest_import"), dict)
            else DiscussionImportRecord(
                source_mode=str(row["latest_import"].get("source_mode", "")),
                provider_label=str(row["latest_import"].get("provider_label", "")),
                verbatim_text=str(row["latest_import"].get("verbatim_text", "")),
                transcript_title=str(row["latest_import"].get("transcript_title", "")),
                cited_dois=[str(item) for item in row["latest_import"].get("cited_dois", [])],
                referenced_claim_ids=[
                    str(item) for item in row["latest_import"].get("referenced_claim_ids", [])
                ],
                imported_at=datetime.fromisoformat(str(row["latest_import"].get("imported_at"))),
            ),
            machine_distilled=None
            if not isinstance(row.get("machine_distilled"), dict)
            else DiscussionDistillation(
                summary=str(row["machine_distilled"].get("summary", "")),
                findings=[str(item) for item in row["machine_distilled"].get("findings", [])],
                decisions=[str(item) for item in row["machine_distilled"].get("decisions", [])],
                literature_notes=[str(item) for item in row["machine_distilled"].get("literature_notes", [])],
                open_questions=[str(item) for item in row["machine_distilled"].get("open_questions", [])],
                risks=[str(item) for item in row["machine_distilled"].get("risks", [])],
                counterarguments=[str(item) for item in row["machine_distilled"].get("counterarguments", [])],
                suggested_next_actions=[
                    str(item) for item in row["machine_distilled"].get("suggested_next_actions", [])
                ],
                cited_dois=[str(item) for item in row["machine_distilled"].get("cited_dois", [])],
                referenced_claim_ids=[
                    str(item) for item in row["machine_distilled"].get("referenced_claim_ids", [])
                ],
            ),
            adopted_decision=None
            if not isinstance(row.get("adopted_decision"), dict)
            else DiscussionDistillation(
                summary=str(row["adopted_decision"].get("summary", "")),
                findings=[str(item) for item in row["adopted_decision"].get("findings", [])],
                decisions=[str(item) for item in row["adopted_decision"].get("decisions", [])],
                literature_notes=[str(item) for item in row["adopted_decision"].get("literature_notes", [])],
                open_questions=[str(item) for item in row["adopted_decision"].get("open_questions", [])],
                risks=[str(item) for item in row["adopted_decision"].get("risks", [])],
                counterarguments=[str(item) for item in row["adopted_decision"].get("counterarguments", [])],
                suggested_next_actions=[
                    str(item) for item in row["adopted_decision"].get("suggested_next_actions", [])
                ],
                cited_dois=[str(item) for item in row["adopted_decision"].get("cited_dois", [])],
                referenced_claim_ids=[
                    str(item) for item in row["adopted_decision"].get("referenced_claim_ids", [])
                ],
            ),
            coverage_report=None
            if not isinstance(row.get("coverage_report"), dict)
            else DiscussionCoverageReport(
                checks=[
                    DiscussionCoverageCheck(
                        ref=str(item.get("ref", "")),
                        ref_type=str(item.get("ref_type", "")),
                        status=str(item.get("status", "")),
                        note=str(item.get("note", "")),
                        linked_entity_id=None
                        if item.get("linked_entity_id") in {None, ""}
                        else str(item.get("linked_entity_id")),
                    )
                    for item in row["coverage_report"].get("checks", [])
                    if isinstance(item, dict)
                ],
                summary=str(row["coverage_report"].get("summary", "")),
            ),
            promoted_record_ids={
                str(key): [str(item) for item in value]
                for key, value in dict(row.get("promoted_record_ids", {})).items()
                if isinstance(value, list)
            },
            metadata=dict(row.get("metadata", {})),
            created_at=datetime.fromisoformat(str(row.get("created_at"))),
            updated_at=datetime.fromisoformat(str(row.get("updated_at"))),
        )
