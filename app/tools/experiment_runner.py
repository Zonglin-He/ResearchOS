from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool


ERROR_CLASSIFIERS: dict[str, tuple[str, str]] = {
    r"CUDA out of memory|out of memory": ("cuda_oom", "auto"),
    r"\bnan\b|NaN|inf\b": ("nan_detected", "auto"),
    r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]": ("import_error", "auto"),
    r"AssertionError": ("logic_error", "llm"),
    r"TimeoutExpired|timed out": ("timeout", "auto"),
}


def classify_error(stderr: str) -> tuple[str, str]:
    for pattern, outcome in ERROR_CLASSIFIERS.items():
        if re.search(pattern, stderr, re.IGNORECASE):
            return outcome
    return ("unknown", "llm")


def run_experiment(
    script_path: str,
    timeout: int = 600,
    *,
    checkpoint_dir: str | None = None,
    max_rounds: int = 1,
) -> dict[str, Any]:
    return run_with_healing(
        script_path,
        timeout=timeout,
        checkpoint_dir=checkpoint_dir,
        max_rounds=max(1, max_rounds),
    )


def run_with_healing(
    script_path: str,
    *,
    timeout: int = 600,
    checkpoint_dir: str | None = None,
    max_rounds: int = 5,
) -> dict[str, Any]:
    current_script = Path(script_path).expanduser().resolve()
    checkpoint_root = Path(checkpoint_dir or current_script.parent / "checkpoints").expanduser().resolve()
    checkpoint_root.mkdir(parents=True, exist_ok=True)
    repair_log: list[str] = []
    last_result: dict[str, Any] | None = None

    for round_index in range(max_rounds):
        result = _invoke_script(current_script, timeout=timeout, checkpoint_dir=checkpoint_root)
        result["round"] = round_index + 1
        result["script_path"] = str(current_script)
        last_result = result
        if result["returncode"] == 0:
            result["status"] = "success"
            result["repair_rounds"] = round_index
            result["repair_log"] = repair_log
            result["checkpoint_dir"] = str(checkpoint_root)
            return result

        error_kind, strategy = classify_error(result["stderr"])
        repair_log.append(f"round {round_index + 1}: {error_kind} via {strategy}")
        if round_index >= max_rounds - 1:
            break

        if strategy == "auto":
            patched_script = _auto_patch(current_script, error_kind=error_kind, stderr=result["stderr"], round_index=round_index)
            if patched_script is None:
                break
            current_script = patched_script
            continue
        break

    if last_result is None:
        last_result = {
            "stdout": "",
            "stderr": "experiment runner did not start",
            "returncode": 1,
            "round": 0,
            "script_path": str(script_path),
        }
    last_result["status"] = "partial" if repair_log else "failed"
    last_result["repair_rounds"] = len(repair_log)
    last_result["repair_log"] = repair_log
    last_result["checkpoint_dir"] = str(checkpoint_root)
    return last_result


def _invoke_script(
    script_path: Path,
    *,
    timeout: int,
    checkpoint_dir: Path,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["RESEARCHOS_CHECKPOINT_DIR"] = str(checkpoint_dir)
    try:
        completed = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
        return {
            "stdout": completed.stdout[-5000:],
            "stderr": completed.stderr[-2000:],
            "returncode": completed.returncode,
        }
    except subprocess.TimeoutExpired as error:
        stdout = (error.stdout or "")[-5000:]
        stderr = ((error.stderr or "") + "\nTimeoutExpired")[-2000:]
        return {
            "stdout": stdout,
            "stderr": stderr,
            "returncode": 124,
        }


def _auto_patch(
    script_path: Path,
    *,
    error_kind: str,
    stderr: str,
    round_index: int,
) -> Path | None:
    script = script_path.read_text(encoding="utf-8")
    patched = script

    if error_kind == "cuda_oom":
        patched = _reduce_batch_size(script)
    elif error_kind == "timeout":
        patched = _reduce_runtime(script)
    elif error_kind == "nan_detected":
        patched = _reduce_learning_rate(script)
    elif error_kind == "import_error":
        module_name = _missing_module(stderr)
        if module_name:
            _pip_install(module_name)
            patched = script
        else:
            return None
    else:
        return None

    if patched == script and error_kind != "import_error":
        return None

    patched_path = script_path.with_name(f"{script_path.stem}.repair{round_index + 1}{script_path.suffix}")
    patched_path.write_text(patched, encoding="utf-8")
    return patched_path


def _reduce_batch_size(script: str) -> str:
    def _halve(match: re.Match[str]) -> str:
        value = max(1, int(match.group("value")) // 2)
        return f"{match.group('prefix')}{value}"

    return re.sub(
        r"(?P<prefix>batch_size\s*=\s*)(?P<value>\d+)",
        _halve,
        script,
        flags=re.IGNORECASE,
    )


def _reduce_runtime(script: str) -> str:
    script = re.sub(
        r"(epochs\s*=\s*)(\d+)",
        lambda match: f"{match.group(1)}{max(1, int(match.group(2)) // 2)}",
        script,
        flags=re.IGNORECASE,
    )
    script = re.sub(
        r"(max_steps\s*=\s*)(\d+)",
        lambda match: f"{match.group(1)}{max(10, int(match.group(2)) // 2)}",
        script,
        flags=re.IGNORECASE,
    )
    return script


def _reduce_learning_rate(script: str) -> str:
    patched = re.sub(
        r"((?:lr|learning_rate)\s*=\s*)(\d+(?:\.\d+)?(?:e-?\d+)?)",
        lambda match: f"{match.group(1)}{_scale_float(match.group(2), 0.1)}",
        script,
        flags=re.IGNORECASE,
    )
    if "clip_grad_norm_" not in patched and "torch" in patched:
        patched += (
            "\n\n# ResearchOS auto-healing hint: add gradient clipping in the training loop if NaNs persist.\n"
        )
    return patched


def _scale_float(raw: str, factor: float) -> str:
    try:
        value = float(raw) * factor
    except ValueError:
        return raw
    if value == 0:
        return raw
    return f"{value:.6g}"


def _missing_module(stderr: str) -> str | None:
    match = re.search(r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]", stderr)
    if match is None:
        return None
    return match.group(1)


def _pip_install(module_name: str) -> None:
    subprocess.run(
        [sys.executable, "-m", "pip", "install", module_name],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


class ExperimentRunnerTool(BaseTool):
    name = "experiment_runner"
    description = "Run a local Python experiment script and collect stdout/stderr."
    input_schema = {
        "type": "object",
        "properties": {
            "script_path": {"type": "string"},
            "timeout": {"type": "integer"},
            "checkpoint_dir": {"type": "string"},
            "max_rounds": {"type": "integer"},
        },
        "required": ["script_path"],
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        script_path = str(kwargs["script_path"]).strip()
        timeout = int(kwargs.get("timeout", 600))
        checkpoint_dir = kwargs.get("checkpoint_dir")
        max_rounds = int(kwargs.get("max_rounds", 1))
        return run_experiment(
            script_path,
            timeout=timeout,
            checkpoint_dir=checkpoint_dir,
            max_rounds=max_rounds,
        )
