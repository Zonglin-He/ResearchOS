from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool


@dataclass(frozen=True)
class RepairAction:
    action_id: str
    description: str
    mode: str
    parameters: dict[str, Any] = field(default_factory=dict)

    def to_record(self) -> dict[str, Any]:
        return {
            "action_id": self.action_id,
            "description": self.description,
            "mode": self.mode,
            "parameters": dict(self.parameters),
        }


@dataclass(frozen=True)
class ExperimentDiagnosis:
    error_kind: str
    strategy: str
    confidence: str
    rationale: str
    repair_actions: tuple[RepairAction, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "error_kind": self.error_kind,
            "strategy": self.strategy,
            "confidence": self.confidence,
            "rationale": self.rationale,
            "repair_actions": [action.to_record() for action in self.repair_actions],
        }


@dataclass(frozen=True)
class AttemptRecord:
    round_index: int
    script_path: str
    status: str
    returncode: int
    stdout: str
    stderr: str
    metrics: dict[str, float] = field(default_factory=dict)
    score: float | None = None
    diagnosis: ExperimentDiagnosis | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "round": self.round_index,
            "script_path": self.script_path,
            "status": self.status,
            "returncode": self.returncode,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "metrics": dict(self.metrics),
            "score": self.score,
            "diagnosis": None if self.diagnosis is None else self.diagnosis.to_record(),
        }


ERROR_CLASSIFIERS: tuple[tuple[str, str, str], ...] = (
    ("cuda_oom", r"CUDA out of memory|out of memory", "Training exceeded the available memory budget."),
    ("nan_detected", r"\bnan\b|NaN|inf\b", "Training diverged and produced invalid numeric values."),
    (
        "import_error",
        r"ModuleNotFoundError: No module named ['\"]([^'\"]+)['\"]",
        "The script depends on a missing Python module.",
    ),
    ("logic_error", r"AssertionError", "The script hit an explicit assertion failure."),
    ("timeout", r"TimeoutExpired|timed out", "The script exceeded its execution budget."),
)


def classify_error(stderr: str) -> tuple[str, str]:
    diagnosis = diagnose_failure(stderr)
    return diagnosis.error_kind, diagnosis.strategy


def diagnose_failure(stderr: str) -> ExperimentDiagnosis:
    for error_kind, pattern, rationale in ERROR_CLASSIFIERS:
        match = re.search(pattern, stderr, re.IGNORECASE)
        if match is None:
            continue
        if error_kind == "cuda_oom":
            return ExperimentDiagnosis(
                error_kind=error_kind,
                strategy="auto",
                confidence="high",
                rationale=rationale,
                repair_actions=(
                    RepairAction(
                        action_id="halve_batch_size",
                        description="Reduce batch_size assignments by half.",
                        mode="patch_script",
                        parameters={"patch_kind": "reduce_batch_size"},
                    ),
                ),
            )
        if error_kind == "timeout":
            return ExperimentDiagnosis(
                error_kind=error_kind,
                strategy="auto",
                confidence="high",
                rationale=rationale,
                repair_actions=(
                    RepairAction(
                        action_id="halve_runtime_budget",
                        description="Reduce epochs and max_steps to fit within the budget.",
                        mode="patch_script",
                        parameters={"patch_kind": "reduce_runtime"},
                    ),
                ),
            )
        if error_kind == "nan_detected":
            return ExperimentDiagnosis(
                error_kind=error_kind,
                strategy="auto",
                confidence="medium",
                rationale=rationale,
                repair_actions=(
                    RepairAction(
                        action_id="reduce_learning_rate",
                        description="Lower learning rate and suggest gradient clipping.",
                        mode="patch_script",
                        parameters={"patch_kind": "reduce_learning_rate"},
                    ),
                ),
            )
        if error_kind == "import_error":
            module_name = match.group(1)
            return ExperimentDiagnosis(
                error_kind=error_kind,
                strategy="auto",
                confidence="high",
                rationale=f"{rationale} Missing module: {module_name}.",
                repair_actions=(
                    RepairAction(
                        action_id="install_dependency",
                        description=f"Install missing dependency {module_name}.",
                        mode="install_dependency",
                        parameters={"module_name": module_name},
                    ),
                ),
            )
        return ExperimentDiagnosis(
            error_kind=error_kind,
            strategy="llm",
            confidence="medium",
            rationale=rationale,
        )
    return ExperimentDiagnosis(
        error_kind="unknown",
        strategy="llm",
        confidence="low",
        rationale="The failure signature does not match a known deterministic repair policy.",
    )


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
    attempts: list[AttemptRecord] = []

    for round_index in range(max_rounds):
        result = _invoke_script(current_script, timeout=timeout, checkpoint_dir=checkpoint_root)
        metrics = extract_metrics(result["stdout"])
        score = _score_metrics(metrics) if metrics else None
        diagnosis = None
        status = "success" if result["returncode"] == 0 else "failed"
        if status != "success":
            diagnosis = diagnose_failure(result["stderr"])
        attempts.append(
            AttemptRecord(
                round_index=round_index + 1,
                script_path=str(current_script),
                status=status,
                returncode=int(result["returncode"]),
                stdout=str(result["stdout"]),
                stderr=str(result["stderr"]),
                metrics=metrics,
                score=score,
                diagnosis=diagnosis,
            )
        )
        if status == "success":
            break
        if round_index >= max_rounds - 1 or diagnosis is None or diagnosis.strategy != "auto":
            break

        patched_script = None
        for action in diagnosis.repair_actions:
            candidate = _apply_repair_action(
                current_script,
                action=action,
                stderr=result["stderr"],
                round_index=round_index,
            )
            if candidate is None:
                continue
            repair_log.append(
                f"round {round_index + 1}: {diagnosis.error_kind} -> {action.action_id}"
            )
            patched_script = candidate
            break
        if patched_script is None:
            break
        current_script = patched_script

    best_attempt = promote_best_result(attempts)
    final_attempt = best_attempt or (attempts[-1] if attempts else None)
    if final_attempt is None:
        return {
            "stdout": "",
            "stderr": "experiment runner did not start",
            "returncode": 1,
            "round": 0,
            "script_path": str(script_path),
            "status": "failed",
            "repair_rounds": 0,
            "repair_log": [],
            "checkpoint_dir": str(checkpoint_root),
            "attempts": [],
            "best_result": None,
            "promoted_script_path": None,
        }

    top_level = {
        "stdout": final_attempt.stdout,
        "stderr": final_attempt.stderr,
        "returncode": final_attempt.returncode,
        "round": final_attempt.round_index,
        "script_path": final_attempt.script_path,
        "status": "success" if best_attempt is not None else ("partial" if repair_log else "failed"),
        "repair_rounds": len(repair_log),
        "repair_log": repair_log,
        "checkpoint_dir": str(checkpoint_root),
        "attempts": [attempt.to_record() for attempt in attempts],
        "best_result": None if best_attempt is None else best_attempt.to_record(),
        "promoted_script_path": None if best_attempt is None else best_attempt.script_path,
        "metrics": dict(final_attempt.metrics),
    }
    return top_level


def promote_best_result(attempts: list[AttemptRecord]) -> AttemptRecord | None:
    successes = [attempt for attempt in attempts if attempt.status == "success"]
    if not successes:
        return None
    return max(
        successes,
        key=lambda attempt: (
            attempt.score if attempt.score is not None else float("-inf"),
            attempt.round_index,
        ),
    )


def extract_metrics(stdout: str) -> dict[str, float]:
    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    for line in reversed(lines):
        payload = line
        if line.lower().startswith("metrics:"):
            payload = line.split(":", 1)[1].strip()
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            parsed = None
        metrics = _flatten_metric_payload(parsed)
        if metrics:
            return metrics
    matches = re.findall(r"([A-Za-z0-9_.-]+)\s*=\s*(-?\d+(?:\.\d+)?(?:e[-+]?\d+)?)", stdout)
    return {name: float(value) for name, value in matches}


def _flatten_metric_payload(
    payload: object,
    *,
    prefix: str = "",
) -> dict[str, float]:
    if isinstance(payload, dict):
        flattened: dict[str, float] = {}
        for key, value in payload.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            flattened.update(_flatten_metric_payload(value, prefix=name))
        return flattened
    if isinstance(payload, bool):
        return {}
    if isinstance(payload, (int, float)):
        return {prefix or "value": float(payload)}
    return {}


def _score_metrics(metrics: dict[str, float]) -> float:
    score = 0.0
    for name, value in metrics.items():
        label = name.lower()
        if any(token in label for token in ("loss", "error", "perplexity", "wer")):
            score -= value
            continue
        if any(token in label for token in ("accuracy", "acc", "f1", "auc", "bleu", "rouge", "precision", "recall")):
            score += value
            continue
        score += value
    return score


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


def _apply_repair_action(
    script_path: Path,
    *,
    action: RepairAction,
    stderr: str,
    round_index: int,
) -> Path | None:
    if action.mode == "install_dependency":
        module_name = str(action.parameters.get("module_name", "")).strip() or _missing_module(stderr)
        if not module_name:
            return None
        _pip_install(module_name)
        return script_path
    if action.mode != "patch_script":
        return None

    script = script_path.read_text(encoding="utf-8")
    patch_kind = str(action.parameters.get("patch_kind", "")).strip()
    if patch_kind == "reduce_batch_size":
        patched = _reduce_batch_size(script)
    elif patch_kind == "reduce_runtime":
        patched = _reduce_runtime(script)
    elif patch_kind == "reduce_learning_rate":
        patched = _reduce_learning_rate(script)
    else:
        return None
    if patched == script:
        return None
    return _write_repaired_script(script_path, patched, round_index=round_index)


def _write_repaired_script(script_path: Path, patched: str, *, round_index: int) -> Path:
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
    patched = re.sub(
        r"(epochs\s*=\s*)(\d+)",
        lambda match: f"{match.group(1)}{max(1, int(match.group(2)) // 2)}",
        script,
        flags=re.IGNORECASE,
    )
    patched = re.sub(
        r"(max_steps\s*=\s*)(\d+)",
        lambda match: f"{match.group(1)}{max(10, int(match.group(2)) // 2)}",
        patched,
        flags=re.IGNORECASE,
    )
    return patched


def _reduce_learning_rate(script: str) -> str:
    patched = re.sub(
        r"((?:lr|learning_rate)\s*=\s*)(\d+(?:\.\d+)?(?:e-?\d+)?)",
        lambda match: f"{match.group(1)}{_scale_float(match.group(2), 0.1)}",
        script,
        flags=re.IGNORECASE,
    )
    if "clip_grad_norm_" not in patched and "torch" in patched:
        patched += "\n\n# ResearchOS repair hint: add gradient clipping if NaNs persist.\n"
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
    description = "Run a local Python experiment script, repair common failures, and promote the best successful result."
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
