import csv
from pathlib import Path

from app.services.run_service import RunService


def main() -> None:
    output_path = Path("writing/tables/main_results.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    runs = RunService().list_runs()

    with output_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["run_id", "spec_id", "status", "metrics"])
        for run in runs:
            writer.writerow([run.run_id, run.spec_id, run.status, run.metrics])

    print(f"Exported tables to {output_path}")


if __name__ == "__main__":
    main()
