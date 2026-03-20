from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from redis import Redis
from sqlalchemy import create_engine, text


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str


def run_command(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, capture_output=True, text=True, timeout=300)


def wait_for_postgres(database_url: str, timeout: float = 60.0) -> CheckResult:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            engine = create_engine(database_url, future=True)
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            return CheckResult("postgres", True, "connected")
        except Exception as error:  # pragma: no cover - exercised in smoke only
            last_error = str(error)
            time.sleep(1)
    return CheckResult("postgres", False, last_error)


def wait_for_redis(redis_url: str, timeout: float = 60.0) -> CheckResult:
    deadline = time.time() + timeout
    client = Redis.from_url(redis_url)
    while time.time() < deadline:
        try:
            client.ping()
            return CheckResult("redis", True, "ping ok")
        except Exception as error:  # pragma: no cover - exercised in smoke only
            last_error = str(error)
            time.sleep(1)
    return CheckResult("redis", False, last_error)


def wait_for_api(api_url: str, timeout: float = 60.0) -> CheckResult:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(f"{api_url.rstrip('/')}/health", timeout=3) as response:
                body = response.read().decode("utf-8")
            return CheckResult("api", True, body)
        except Exception as error:  # pragma: no cover - exercised in smoke only
            last_error = str(error)
            time.sleep(1)
    return CheckResult("api", False, last_error)


def post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def check_celery_flow(task_id: str) -> list[CheckResult]:
    from app.worker.celery_app import celery_app

    ping_result = celery_app.send_task("researchos.ping")
    ping_payload = ping_result.get(timeout=120)

    advance_result = celery_app.send_task(
        "researchos.advance_task",
        args=[task_id, "running"],
    )
    advance_payload = advance_result.get(timeout=120)

    return [
        CheckResult("celery_ping", ping_payload.get("status") == "ok", json.dumps(ping_payload)),
        CheckResult(
            "celery_advance_task",
            advance_payload.get("task_id") == task_id and advance_payload.get("status") == "running",
            json.dumps(advance_payload),
        ),
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-compose", action="store_true")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000")
    parser.add_argument(
        "--database-url",
        default="postgresql+psycopg://researchos:researchos@127.0.0.1:5432/researchos",
    )
    parser.add_argument("--redis-url", default="redis://127.0.0.1:6379/0")
    args = parser.parse_args()

    report: dict[str, object] = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "checks": [],
    }

    if args.start_compose:
        compose = run_command(["docker", "compose", "up", "-d", "postgres", "redis", "api", "worker"])
        report["compose_up"] = {
            "returncode": compose.returncode,
            "stdout": compose.stdout,
            "stderr": compose.stderr,
        }
        if compose.returncode != 0:
            output_path = Path("artifacts/production_stack_smoke_report.json")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return compose.returncode

    os.environ["RESEARCHOS_DATABASE_URL"] = args.database_url
    os.environ["RESEARCHOS_REDIS_URL"] = args.redis_url
    os.environ["RESEARCHOS_CELERY_BACKEND"] = args.redis_url

    checks = [
        wait_for_postgres(args.database_url),
        wait_for_redis(args.redis_url),
        wait_for_api(args.api_url),
    ]

    if all(check.ok for check in checks):
        project = post_json(
            f"{args.api_url.rstrip('/')}/projects",
            {
                "project_id": "stack-project",
                "name": "Stack Smoke",
                "description": "production stack smoke test",
                "status": "active",
            },
        )
        task = post_json(
            f"{args.api_url.rstrip('/')}/tasks",
            {
                "task_id": "stack-task",
                "project_id": project["project_id"],
                "kind": "paper_ingest",
                "goal": "Smoke the Celery task path",
                "input_payload": {"topic": "smoke"},
                "owner": "system",
                "assigned_agent": None,
                "parent_task_id": None,
            },
        )
        checks.append(CheckResult("api_create_project", project["project_id"] == "stack-project", json.dumps(project)))
        checks.append(CheckResult("api_create_task", task["task_id"] == "stack-task", json.dumps(task)))
        checks.extend(check_celery_flow(task["task_id"]))

    report["checks"] = [asdict(check) for check in checks]
    output_path = Path("artifacts/production_stack_smoke_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(check.ok for check in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
