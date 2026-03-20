from __future__ import annotations

import asyncio
import gc
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from app.bootstrap import build_runtime_services
from app.core.config import AppConfig
from app.schemas.project import Project
from app.schemas.task import Task


async def main_async() -> dict:
    temp_dir = Path(tempfile.mkdtemp(prefix="researchos-live-flow-"))
    cwd = Path.cwd()
    try:
        os.chdir(temp_dir)
        config = AppConfig(
            db_path=str(Path("data") / "live_flow.db"),
            provider_name="claude",
            provider_model="sonnet",
        )
        services = build_runtime_services(config)
        services.project_service.create_project(
            Project(
                project_id="live-flow-project",
                name="Live Flow Smoke",
                description="Smoke test for Reader -> Mapper",
                status="active",
            )
        )

        reader_task = services.task_service.create_task(
            Task(
                task_id="reader-live-task",
                project_id="live-flow-project",
                kind="paper_ingest",
                goal="Read the provided source summary into a paper card.",
                input_payload={
                    "topic": "auditable research agents",
                    "source_summary": {
                        "title": "ResearchOS: Auditable Multi-Agent Research Workflows",
                        "abstract": (
                            "We describe a code-first system that structures literature ingestion, "
                            "gap mapping, experiment execution, auditing, and evidence-driven writing "
                            "into a recoverable research workflow."
                        ),
                        "setting": "research systems",
                    },
                },
                owner="system",
            )
        )

        reader_dispatch = await services.orchestrator.dispatch(reader_task.task_id)
        next_tasks = reader_dispatch.result.next_tasks

        mapper_dispatch_payload = None
        if next_tasks:
            mapper_dispatch = await services.orchestrator.dispatch(next_tasks[0].task_id)
            mapper_dispatch_payload = {
                "task_status": mapper_dispatch.task.status.value,
                "result_status": mapper_dispatch.result.status,
                "output": mapper_dispatch.result.output,
                "audit_notes": mapper_dispatch.result.audit_notes,
            }

        return {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "reader": {
                "task_status": reader_dispatch.task.status.value,
                "result_status": reader_dispatch.result.status,
                "output": reader_dispatch.result.output,
                "next_task_kinds": [task.kind for task in next_tasks],
                "audit_notes": reader_dispatch.result.audit_notes,
            },
            "mapper": mapper_dispatch_payload,
            "registered_paper_cards": [
                {
                    "paper_id": card.paper_id,
                    "title": card.title,
                }
                for card in services.paper_card_service.list_cards()
            ],
            "registered_gap_maps": [
                {
                    "topic": gap_map.topic,
                    "cluster_count": len(gap_map.clusters),
                }
                for gap_map in services.gap_map_service.list_gap_maps()
            ],
        }
    finally:
        os.chdir(cwd)
        gc.collect()
        for _ in range(5):
            try:
                shutil.rmtree(temp_dir)
                break
            except PermissionError:
                time.sleep(0.2)


def main() -> int:
    report = asyncio.run(main_async())
    output_path = Path("artifacts/live_research_flow_smoke_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
