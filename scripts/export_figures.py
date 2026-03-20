from pathlib import Path

from app.services.run_service import RunService


def main() -> None:
    output_path = Path("writing/figures.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    runs = RunService().list_runs()

    lines = ["# Exported Figures", ""]
    for run in runs:
        for artifact in run.artifacts:
            lines.append(f"- {run.run_id}: {artifact}")

    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported figure index to {output_path}")


if __name__ == "__main__":
    main()
