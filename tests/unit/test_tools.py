from pathlib import Path

from app.tools.citation_verifier import verify_citations
from app.tools.experiment_runner import AttemptRecord, promote_best_result, run_with_healing
from app.tools.filesystem import FilesystemTool
from app.tools.python_exec import PythonExecTool
from app.tools.shell_tool import ShellTool


def test_filesystem_tool_read_write_and_list(tmp_path: Path) -> None:
    import asyncio

    tool = FilesystemTool()
    target = tmp_path / "note.txt"

    asyncio.run(tool.execute(action="write_text", path=str(target), content="hello"))
    read_result = asyncio.run(tool.execute(action="read_text", path=str(target)))
    list_result = asyncio.run(tool.execute(action="list_dir", path=str(tmp_path)))

    assert read_result["content"] == "hello"
    assert str(target) in list_result["items"]


def test_shell_tool_executes_command() -> None:
    import asyncio

    result = asyncio.run(ShellTool().execute(command="python -c \"print('ok')\""))

    assert result["returncode"] == 0
    assert result["stdout"].strip() == "ok"


def test_python_exec_tool_executes_code() -> None:
    import asyncio

    result = asyncio.run(PythonExecTool().execute(code="print('hello')"))

    assert result["returncode"] == 0
    assert result["stdout"].strip() == "hello"


def test_verify_citations_aggregates_multisource_details() -> None:
    def resolver(citation: str) -> dict[str, object]:
        if citation == "Verified Paper":
            return {
                "citation": citation,
                "status": "verified",
                "confidence": "high",
                "sources_hit": ["crossref", "semantic_scholar"],
                "matched_title": "Verified Paper",
                "matched_identifiers": {"doi": "10.1000/verified"},
                "notes": "Verified via direct identifier.",
            }
        return {
            "citation": citation,
            "status": "unresolved",
            "confidence": "none",
            "sources_hit": [],
            "matched_title": "",
            "matched_identifiers": {},
            "notes": "No match found.",
        }

    result = verify_citations(
        ["Verified Paper", "Missing Paper"],
        resolver=resolver,
    )

    assert result["valid"] == ["Verified Paper"]
    assert result["hallucinated"] == ["Missing Paper"]
    assert result["summary"]["verified_count"] == 1
    assert result["summary"]["unresolved_count"] == 1
    assert result["summary"]["sources_used"] == ["crossref", "semantic_scholar"]
    assert result["details"][0]["matched_identifiers"]["doi"] == "10.1000/verified"


def test_experiment_runner_uses_diagnosis_loop_and_promotes_best_success(tmp_path: Path) -> None:
    script = tmp_path / "oom_experiment.py"
    script.write_text(
        "\n".join(
            [
                "import json",
                "import sys",
                "",
                "batch_size = 8",
                "if batch_size > 4:",
                "    sys.stderr.write('CUDA out of memory')",
                "    raise SystemExit(1)",
                "",
                "print('METRICS: ' + json.dumps({'accuracy': 0.91, 'loss': 0.12}))",
            ]
        ),
        encoding="utf-8",
    )

    result = run_with_healing(str(script), max_rounds=3)

    assert result["status"] == "success"
    assert result["repair_rounds"] == 1
    assert result["best_result"]["diagnosis"] is None
    assert result["attempts"][0]["diagnosis"]["error_kind"] == "cuda_oom"
    assert result["promoted_script_path"].endswith(".repair1.py")
    assert result["metrics"]["accuracy"] == 0.91


def test_promote_best_result_prefers_highest_score() -> None:
    attempts = [
        AttemptRecord(
            round_index=1,
            script_path="a.py",
            status="success",
            returncode=0,
            stdout="",
            stderr="",
            metrics={"accuracy": 0.8},
            score=0.8,
        ),
        AttemptRecord(
            round_index=2,
            script_path="b.py",
            status="success",
            returncode=0,
            stdout="",
            stderr="",
            metrics={"accuracy": 0.9},
            score=0.9,
        ),
    ]
    best = promote_best_result(attempts)

    assert best is not None
    assert best.script_path == "b.py"
