from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from app.schemas.artifact import ArtifactRecord
from app.schemas.freeze import ResultsFreeze
from app.schemas.run_manifest import RunManifest


@dataclass(frozen=True)
class VerifiedMetricEntry:
    metric_key: str
    numeric_value: float
    display_value: str
    run_id: str | None = None
    source_type: str = "run_metric"
    artifact_id: str | None = None
    branch_name: str | None = None
    spec_id: str | None = None

    def to_record(self) -> dict[str, Any]:
        return {
            "metric_key": self.metric_key,
            "numeric_value": self.numeric_value,
            "display_value": self.display_value,
            "run_id": self.run_id,
            "source_type": self.source_type,
            "artifact_id": self.artifact_id,
            "branch_name": self.branch_name,
            "spec_id": self.spec_id,
        }


@dataclass(frozen=True)
class VerifiedMetricsRegistry:
    entries: tuple[VerifiedMetricEntry, ...] = ()
    supporting_run_ids: tuple[str, ...] = ()
    results_id: str | None = None
    external_sources: tuple[str, ...] = ()

    def to_record(self) -> dict[str, Any]:
        return {
            "results_id": self.results_id,
            "supporting_run_ids": list(self.supporting_run_ids),
            "external_sources": list(self.external_sources),
            "entries": [entry.to_record() for entry in self.entries],
        }


def build_verified_metrics_registry(
    *,
    runs: list[RunManifest],
    artifacts: list[ArtifactRecord] | None = None,
    results_freeze: ResultsFreeze | None = None,
    external_results: list[dict[str, Any]] | None = None,
) -> VerifiedMetricsRegistry:
    artifact_map = {artifact.artifact_id: artifact for artifact in artifacts or []}
    entries: list[VerifiedMetricEntry] = []
    for run in runs:
        for metric_key, numeric_value in _flatten_numeric_values(run.metrics).items():
            entries.append(
                VerifiedMetricEntry(
                    metric_key=metric_key,
                    numeric_value=numeric_value,
                    display_value=_display_number(numeric_value),
                    run_id=run.run_id,
                    source_type="run_metric",
                    branch_name=run.experiment_branch,
                    spec_id=run.spec_id,
                )
            )
        for artifact_id in run.artifacts:
            artifact = artifact_map.get(artifact_id)
            if artifact is None:
                continue
            for metric_key, numeric_value in _flatten_numeric_values(artifact.metadata, prefix=f"artifact.{artifact.kind}").items():
                entries.append(
                    VerifiedMetricEntry(
                        metric_key=metric_key,
                        numeric_value=numeric_value,
                        display_value=_display_number(numeric_value),
                        run_id=run.run_id,
                        source_type="artifact_metadata",
                        artifact_id=artifact.artifact_id,
                        branch_name=run.experiment_branch,
                        spec_id=run.spec_id,
                    )
                )
    for item in external_results or []:
        if not isinstance(item, dict):
            continue
        metric_key = str(item.get("metric") or item.get("name") or "").strip()
        try:
            numeric_value = float(item.get("value"))
        except (TypeError, ValueError):
            continue
        if not metric_key:
            metric_key = "external.metric"
        entries.append(
            VerifiedMetricEntry(
                metric_key=metric_key,
                numeric_value=numeric_value,
                display_value=_display_number(numeric_value),
                source_type="external_result",
                artifact_id=str(item.get("artifact_id")) if item.get("artifact_id") else None,
            )
        )
    deduped = _dedupe_entries(entries)
    return VerifiedMetricsRegistry(
        entries=tuple(deduped),
        supporting_run_ids=tuple(run.run_id for run in runs),
        results_id=None if results_freeze is None else results_freeze.results_id,
        external_sources=tuple(results_freeze.external_sources if results_freeze is not None else ()),
    )


def ground_text_numbers(
    text: str,
    registry: VerifiedMetricsRegistry,
) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    grounded: list[dict[str, Any]] = []
    ungrounded: list[dict[str, Any]] = []
    for candidate in _extract_numeric_candidates(text):
        registry_matches = _match_registry_value(candidate["numeric_value"], registry.entries)
        record = {
            "token": candidate["token"],
            "numeric_value": candidate["numeric_value"],
            "normalized_candidates": candidate["normalized_candidates"],
            "matches": [entry.to_record() for entry in registry_matches],
        }
        matches.append(record)
        if registry_matches:
            grounded.append(record)
        else:
            ungrounded.append(record)
    return {
        "grounded": grounded,
        "ungrounded": ungrounded,
        "summary": {
            "numbers_checked": len(matches),
            "grounded_count": len(grounded),
            "ungrounded_count": len(ungrounded),
        },
    }


def _flatten_numeric_values(
    payload: dict[str, Any] | None,
    *,
    prefix: str = "",
) -> dict[str, float]:
    if not isinstance(payload, dict):
        return {}
    flattened: dict[str, float] = {}
    for key, value in payload.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, dict):
            flattened.update(_flatten_numeric_values(value, prefix=name))
            continue
        if isinstance(value, bool):
            continue
        if isinstance(value, (int, float)):
            flattened[name] = float(value)
    return flattened


def _extract_numeric_candidates(text: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    pattern = re.compile(r"(?<![\w/])(-?\d+(?:\.\d+)?%?)")
    for match in pattern.finditer(text):
        token = match.group(1)
        if re.fullmatch(r"\d{4}", token):
            continue
        if "." not in token and not token.endswith("%"):
            continue
        normalized_candidates: list[float] = []
        if token.endswith("%"):
            base = float(token[:-1])
            normalized_candidates.extend([base, base / 100.0])
        else:
            base = float(token)
            normalized_candidates.append(base)
            if 0.0 <= base <= 100.0:
                normalized_candidates.append(base / 100.0)
        candidates.append(
            {
                "token": token,
                "numeric_value": normalized_candidates[0],
                "normalized_candidates": normalized_candidates,
            }
        )
    return candidates


def _match_registry_value(
    numeric_value: float,
    entries: tuple[VerifiedMetricEntry, ...],
    *,
    tolerance: float = 1e-3,
) -> list[VerifiedMetricEntry]:
    matches: list[VerifiedMetricEntry] = []
    normalized_candidates = [numeric_value]
    if abs(numeric_value) <= 100.0:
        normalized_candidates.append(numeric_value / 100.0)
        normalized_candidates.append(numeric_value * 100.0)
    for entry in entries:
        if any(abs(entry.numeric_value - candidate) <= tolerance for candidate in normalized_candidates):
            matches.append(entry)
    return matches


def _dedupe_entries(entries: list[VerifiedMetricEntry]) -> list[VerifiedMetricEntry]:
    seen: set[tuple[str, float, str | None, str | None]] = set()
    deduped: list[VerifiedMetricEntry] = []
    for entry in entries:
        key = (entry.metric_key, round(entry.numeric_value, 6), entry.run_id, entry.artifact_id)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)
    return deduped


def _display_number(value: float) -> str:
    return f"{value:.6g}"
