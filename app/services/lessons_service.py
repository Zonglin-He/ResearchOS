from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.db.sqlite import SQLiteDatabase
from app.schemas.lesson import LessonKind, LessonRecord
from app.services.registry_store import read_jsonl, to_record, upsert_jsonl


class LessonsService:
    def __init__(
        self,
        registry_path: str | Path = "registry/lessons.jsonl",
        *,
        database: SQLiteDatabase | None = None,
    ) -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()
        self.database = database

    def record_lesson(self, lesson: LessonRecord) -> LessonRecord:
        if self.database is not None:
            with self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO lessons (
                        lesson_id,
                        lesson_kind,
                        task_kind,
                        agent_name,
                        provider_name,
                        model_name,
                        source_task_id,
                        created_at,
                        record_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        lesson.lesson_id,
                        lesson.lesson_kind.value,
                        lesson.task_kind,
                        lesson.agent_name,
                        lesson.provider_name,
                        lesson.model_name,
                        lesson.source_task_id,
                        lesson.created_at.isoformat(),
                        json.dumps(to_record(lesson), ensure_ascii=False),
                    ),
                )
            return lesson
        upsert_jsonl(self.registry_path, "lesson_id", to_record(lesson))
        return lesson

    def list_lessons(
        self,
        *,
        task_kind: str | None = None,
        agent_name: str | None = None,
        tool_name: str | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        failure_type: str | None = None,
        repository_ref: str | None = None,
        dataset_ref: str | None = None,
        lesson_kind: LessonKind | None = None,
    ) -> list[LessonRecord]:
        lessons = self._filter_active_lessons(self._read_lessons())
        filtered: list[LessonRecord] = []
        for lesson in lessons:
            if task_kind is not None and lesson.task_kind != task_kind:
                continue
            if agent_name is not None and lesson.agent_name != agent_name:
                continue
            if tool_name is not None and lesson.tool_name != tool_name:
                continue
            if provider_name is not None and lesson.provider_name != provider_name:
                continue
            if model_name is not None and lesson.model_name != model_name:
                continue
            if failure_type is not None and lesson.failure_type != failure_type:
                continue
            if repository_ref is not None and lesson.repository_ref != repository_ref:
                continue
            if dataset_ref is not None and lesson.dataset_ref != dataset_ref:
                continue
            if lesson_kind is not None and lesson.lesson_kind != lesson_kind:
                continue
            filtered.append(lesson)
        return filtered

    def get_relevant_lessons(
        self,
        *,
        task_kind: str,
        agent_name: str | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        repository_ref: str | None = None,
        dataset_ref: str | None = None,
        topic: str | None = None,
        limit: int = 5,
    ) -> list[LessonRecord]:
        lessons = self.resolve_prior_lessons(
            task_kind=task_kind,
            agent_name=agent_name,
            provider_name=provider_name,
            model_name=model_name,
            repository_ref=repository_ref,
            dataset_ref=dataset_ref,
            topic=topic,
            limit=limit,
        )
        self._touch_lessons(lessons)
        return lessons

    def resolve_prior_lessons(
        self,
        *,
        task_kind: str,
        agent_name: str | None = None,
        provider_name: str | None = None,
        model_name: str | None = None,
        repository_ref: str | None = None,
        dataset_ref: str | None = None,
        topic: str | None = None,
        limit: int = 5,
    ) -> list[LessonRecord]:
        exact = self.list_lessons(
            task_kind=task_kind,
            agent_name=agent_name,
            provider_name=provider_name,
            model_name=model_name,
            repository_ref=repository_ref,
            dataset_ref=dataset_ref,
        )
        cross_agent = self.list_lessons(task_kind=task_kind)
        topic_related = [
            lesson
            for lesson in self.list_lessons(task_kind=task_kind)
            if topic and topic in lesson.context_tags
        ]
        deduped: list[LessonRecord] = []
        seen: set[str] = set()
        for lesson in sorted(
            [*exact, *cross_agent, *topic_related],
            key=lambda item: (item.hit_count, item.created_at),
            reverse=True,
        ):
            if lesson.lesson_id in seen:
                continue
            seen.add(lesson.lesson_id)
            deduped.append(lesson)
            if len(deduped) >= limit:
                break
        return deduped

    def capture_agent_outcome(
        self,
        *,
        task,
        agent_name: str,
        result,
    ) -> LessonRecord | None:
        blocking_issues = []
        if isinstance(result.output, dict):
            blocking_issues = result.output.get("blocking_issues", [])
        rationale_parts = list(result.audit_notes)
        if blocking_issues:
            rationale_parts.extend(blocking_issues)

        if result.status == "success" and not rationale_parts:
            return None

        failure_type = None
        lesson_kind = LessonKind.LESSON
        if result.status == "fail":
            lesson_kind = LessonKind.FAILURE_SIGNATURE
            failure_type = "agent_failure"
        elif result.status == "handoff":
            lesson_kind = LessonKind.ANTI_PATTERN
            failure_type = "review_blocker"
        elif result.status == "needs_approval":
            lesson_kind = LessonKind.PLAYBOOK
            failure_type = "approval_gate"

        summary = rationale_parts[0] if rationale_parts else f"{task.kind} completed without reusable notes."
        lesson = LessonRecord(
            lesson_id=f"lesson:{task.task_id}:{agent_name}:{len(self._read_lessons()) + 1}",
            lesson_kind=lesson_kind,
            title=f"{task.kind} via {agent_name}",
            summary=summary,
            rationale=" | ".join(rationale_parts),
            recommended_action=blocking_issues[0] if blocking_issues else "",
            task_kind=task.kind,
            agent_name=agent_name,
            provider_name=getattr(task.last_run_routing, "provider_name", None),
            model_name=getattr(task.last_run_routing, "model", None),
            failure_type=failure_type,
            repository_ref=task.input_payload.get("repository"),
            dataset_ref=task.input_payload.get("dataset_snapshot")
            or task.input_payload.get("dataset"),
            context_tags=task.input_payload.get("context_tags", []),
            evidence_refs=[f"task:{task.task_id}"],
            artifact_ids=list(result.artifacts),
            source_task_id=task.task_id,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        return self.record_lesson(lesson)

    def _read_lessons(self) -> list[LessonRecord]:
        if self.database is not None:
            self._hydrate_database_if_needed()
            with self.database.connect() as connection:
                rows = connection.execute(
                    "SELECT record_json FROM lessons ORDER BY created_at, lesson_id"
                ).fetchall()
            return [
                lesson
                for lesson in (self._row_to_lesson(json.loads(row["record_json"])) for row in rows)
                if lesson is not None
            ]
        rows = read_jsonl(self.registry_path)
        return [lesson for lesson in (self._row_to_lesson(row) for row in rows) if lesson is not None]

    @staticmethod
    def _filter_active_lessons(lessons: list[LessonRecord]) -> list[LessonRecord]:
        now = datetime.now(timezone.utc)
        return [
            lesson
            for lesson in lessons
            if lesson.is_valid and (lesson.expires_at is None or lesson.expires_at > now)
        ]

    def _touch_lessons(self, lessons: list[LessonRecord]) -> None:
        if not lessons:
            return
        now = datetime.now(timezone.utc)
        for lesson in lessons:
            lesson.hit_count += 1
            lesson.last_hit_at = now
            self.record_lesson(lesson)

    def _hydrate_database_if_needed(self) -> None:
        if self.database is None:
            return
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM lessons").fetchone()
            count = int(row["count"] if row is not None else 0)
        if count > 0:
            return
        rows = read_jsonl(self.registry_path)
        if not rows:
            return
        with self.database.connect() as connection:
            for row in rows:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO lessons (
                        lesson_id,
                        lesson_kind,
                        task_kind,
                        agent_name,
                        provider_name,
                        model_name,
                        source_task_id,
                        created_at,
                        record_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["lesson_id"],
                        row["lesson_kind"],
                        row.get("task_kind"),
                        row.get("agent_name"),
                        row.get("provider_name"),
                        row.get("model_name"),
                        row.get("source_task_id"),
                        row["created_at"],
                        json.dumps(row, ensure_ascii=False),
                    ),
                )

    @staticmethod
    def _row_to_lesson(row: dict[str, object]) -> LessonRecord | None:
        try:
            return LessonRecord(
                lesson_id=row["lesson_id"],
                lesson_kind=LessonKind(row["lesson_kind"]),
                title=row["title"],
                summary=row["summary"],
                rationale=row.get("rationale", ""),
                recommended_action=row.get("recommended_action", ""),
                task_kind=row.get("task_kind"),
                agent_name=row.get("agent_name"),
                tool_name=row.get("tool_name"),
                provider_name=row.get("provider_name"),
                model_name=row.get("model_name"),
                failure_type=row.get("failure_type"),
                repository_ref=row.get("repository_ref"),
                dataset_ref=row.get("dataset_ref"),
                context_tags=row.get("context_tags", []),
                evidence_refs=row.get("evidence_refs", []),
                artifact_ids=row.get("artifact_ids", []),
                source_task_id=row.get("source_task_id"),
                source_run_id=row.get("source_run_id"),
                source_claim_id=row.get("source_claim_id"),
                expires_at=None
                if row.get("expires_at") in {None, ""}
                else datetime.fromisoformat(row["expires_at"]),
                hit_count=int(row.get("hit_count", 0) or 0),
                last_hit_at=None
                if row.get("last_hit_at") in {None, ""}
                else datetime.fromisoformat(row["last_hit_at"]),
                is_valid=bool(row.get("is_valid", True)),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        except (KeyError, TypeError, ValueError):
            return None
