from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


@dataclass
class SmokeResult:
    provider: str
    command: list[str]
    returncode: int
    ok: bool
    stdout: str
    stderr: str
    started_at: str


def resolve_command(command: list[str]) -> list[str]:
    resolved = shutil.which(command[0]) or command[0]
    if resolved.lower().endswith(".ps1"):
        shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
        return [
            shell,
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            resolved,
            *command[1:],
        ]
    return [resolved, *command[1:]]


def run_smoke(provider: str, command: list[str], *, cwd: str) -> SmokeResult:
    started_at = datetime.now(timezone.utc).isoformat()
    process = subprocess.run(
        resolve_command(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=180,
    )
    stdout = process.stdout.strip()
    stderr = process.stderr.strip()
    ok = process.returncode == 0 and "pong" in stdout.lower()
    return SmokeResult(
        provider=provider,
        command=command,
        returncode=process.returncode,
        ok=ok,
        stdout=stdout,
        stderr=stderr,
        started_at=started_at,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="researchos-provider-smoke-") as temp_dir:
        results = [
            run_smoke(
                "codex",
                [
                    "codex",
                    "exec",
                    "Return exactly the text pong and nothing else.",
                    "--skip-git-repo-check",
                    "--ephemeral",
                    "-C",
                    temp_dir,
                    "--model",
                    "gpt-5.4",
                ],
                cwd=temp_dir,
            ),
            run_smoke(
                "claude",
                [
                    "claude",
                    "-p",
                    "Return exactly the text pong and nothing else.",
                    "--output-format",
                    "text",
                    "--model",
                    "sonnet",
                    "--no-session-persistence",
                ],
                cwd=temp_dir,
            ),
            run_smoke(
                "gemini",
                [
                    "gemini",
                    "-p",
                    "Return exactly the text pong and nothing else.",
                    "--output-format",
                    "text",
                    "--model",
                    "gemini-2.5-pro",
                ],
                cwd=temp_dir,
            ),
        ]

        report = {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "results": [asdict(result) for result in results],
        }
        output_path = Path("artifacts/provider_smoke_report.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if all(item.ok for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
