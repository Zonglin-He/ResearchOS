from __future__ import annotations

import gc
from pathlib import Path
import shutil
import tempfile
import time

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.bootstrap import build_runtime_services
from app.cli import main
from app.console.control_plane import ConsoleControlPlane
from app.core.config import load_config


def main_smoke() -> None:
    root = Path(tempfile.mkdtemp(prefix="researchos-smoke-"))
    try:
        db_path = root / "researchos.db"

        import os

        os.environ["RESEARCHOS_WORKSPACE_ROOT"] = str(root)
        os.environ["RESEARCHOS_PROVIDER"] = "local"
        os.environ["RESEARCHOS_PROVIDER_MODEL"] = "deterministic-reader"

        main(
            [
                "--db-path",
                str(db_path),
                "create-project",
                "--project-id",
                "p1",
                "--name",
                "Unified Flow",
                "--description",
                "manual unified smoke",
            ]
        )

        with TestClient(create_app(str(db_path), workspace_root=str(root))) as client:
            client.post(
                "/tasks",
                json={
                    "task_id": "t1",
                    "project_id": "p1",
                    "kind": "paper_ingest",
                    "goal": "Read one source",
                    "input_payload": {
                        "topic": "retrieval",
                        "source_summary": {
                            "title": "Unified Source",
                            "abstract": "Compact summary.",
                            "setting": "streaming retrieval",
                        },
                    },
                    "owner": "smoke",
                    "dispatch_profile": {
                        "provider": {"provider_name": "local", "model": "deterministic-reader"},
                        "max_steps": 12,
                    },
                },
            )
            client.post("/tasks/t1/dispatch")

        config = load_config()
        config.db_path = str(db_path)
        config.workspace_root = str(root)
        services = build_runtime_services(config)
        control_plane = ConsoleControlPlane.from_runtime_services(services)

        dashboard = control_plane.project_dashboard("p1")
        routing = control_plane.inspect_task_routing("t1")
        artifact = control_plane.inspect_artifact(control_plane.list_artifacts()[0].artifact_id)

        print(
            f"dashboard project={dashboard.project_id} tasks={dashboard.total_tasks} artifacts={dashboard.artifact_count}"
        )
        print(
            f"routing provider={routing.resolved_dispatch.provider_name} model={routing.resolved_dispatch.model or '<default>'}"
        )
        print(
            f"artifact artifact_id={artifact.artifact_id} verifications={artifact.verification_count} annotations={artifact.annotation_count}"
        )
    finally:
        gc.collect()
        for _ in range(5):
            try:
                shutil.rmtree(root)
                break
            except PermissionError:
                time.sleep(0.2)


if __name__ == "__main__":
    main_smoke()
