from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.bootstrap import build_runtime_services
from app.core.config import load_config


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="researchos-evals-") as tmp_dir:
        root = Path(tmp_dir)
        config = load_config()
        config.workspace_root = str(root)
        config.db_path = str(root / "data" / "researchos.db")
        services = build_runtime_services(config)
        summary = services.benchmark_service.run(project_id=None)
        print(json.dumps(
            {
                "benchmark_id": summary.benchmark_id,
                "success_rate": summary.success_rate,
                "routing_accuracy": summary.routing_accuracy,
                "retrieval_usefulness": summary.retrieval_usefulness,
                "resume_success": summary.resume_success,
                "branch_selection_quality": summary.branch_selection_quality,
                "scenario_count": summary.scenario_count,
                "failure_reasons": list(summary.failure_reasons),
            },
            ensure_ascii=False,
            indent=2,
        ))


if __name__ == "__main__":
    main()
