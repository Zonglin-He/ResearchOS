from __future__ import annotations

import json
import re
from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import WRITER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task, write_artifact
from app.roles import writer_role_binding
from app.schemas.freeze import ResultsFreeze
from app.schemas.run_manifest import RunManifest
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService
from app.services.freeze_service import FreezeService
from app.services.run_service import RunService
from app.services.verified_metrics_registry import (
    build_verified_metrics_registry,
    ground_text_numbers,
)
from app.tools.citation_verifier import verify_citations

FALSE_POSITIVE_PREFIXES = {
    "[Figure",
    "[Table",
    "[Note",
    "[Eq",
    "[Equation",
    "[Section",
    "[Algorithm",
    "[Appendix",
}


class WriterAgent(PromptDrivenAgent):
    name = "writer_agent"
    description = "Writes draft sections from frozen evidence."
    prompt_path = "prompts/writer.md"
    role_binding = writer_role_binding()

    def __init__(
        self,
        provider,
        *,
        artifact_service: ArtifactService | None = None,
        run_service: RunService | None = None,
        freeze_service: FreezeService | None = None,
        model: str | None = None,
        tool_registry=None,
        provider_registry=None,
        routing_policy=None,
        provider_invocation_service=None,
        role_prompt_registry=None,
        role_skill_registry=None,
    ) -> None:
        super().__init__(
            provider,
            model=model,
            response_schema=WRITER_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
            provider_invocation_service=provider_invocation_service,
            role_binding=self.role_binding,
            role_prompt_registry=role_prompt_registry,
            role_skill_registry=role_skill_registry,
        )
        self.artifact_service = artifact_service
        self.run_service = run_service
        self.freeze_service = freeze_service

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        target_venue = str(task.input_payload.get("target_venue", "")).strip()
        output_format = self._desired_output_format(target_venue)
        results_freeze = self._resolve_results_freeze(task)
        evidence_runs = self._resolve_evidence_runs(task, results_freeze)
        evidence_artifacts = []
        if self.artifact_service is not None:
            evidence_run_ids = {run.run_id for run in evidence_runs}
            evidence_artifacts = [
                artifact
                for artifact in self.artifact_service.list_artifacts()
                if artifact.run_id in evidence_run_ids
            ]
        metrics_registry = build_verified_metrics_registry(
            runs=evidence_runs,
            artifacts=evidence_artifacts,
            results_freeze=results_freeze,
            external_results=[
                item
                for item in task.input_payload.get("external_results", [])
                if isinstance(item, dict)
            ],
        )
        payload["writer_focus"] = {
            "required_outputs": ["title", "sections", "audit_notes", "citations"],
            "hard_constraints": [
                "write only from frozen evidence",
                "do not invent new results",
                "keep claim-evidence alignment explicit",
                "use imported or external runs only when they are explicitly present in evidence_sources",
                "numeric claims must be grounded in the verified_metrics_registry",
            ],
            "output_format": output_format,
            "target_venue": target_venue,
            "venue_checklist": self._venue_checklist(target_venue),
            "evidence_sources": {
                "registered_runs": [self._run_record(run) for run in evidence_runs],
                "results_freeze": None if results_freeze is None else self._results_freeze_record(results_freeze),
                "imported_runs": task.input_payload.get("imported_runs", []),
                "external_results": task.input_payload.get("external_results", []),
                "verified_metrics_registry": metrics_registry.to_record(),
            },
        }
        return payload

    def build_result(self, task: Task, ctx, output: dict[str, Any]) -> AgentResult:
        title = output.get("title", "Draft")
        sections = output.get("sections", [])
        target_venue = str(task.input_payload.get("target_venue", "")).strip()
        output_format = str(output.get("output_format", "")).strip().lower() or self._desired_output_format(target_venue)
        citation_repair_round = max(0, int(task.input_payload.get("citation_repair_round", 0) or 0))
        metric_repair_round = max(0, int(task.input_payload.get("metric_grounding_round", 0) or 0))
        citations, used_fallback_citations = self._collect_citations(output, task)
        verification = (
            verify_citations(citations)
            if citations
            else {
                "valid": [],
                "hallucinated": [],
                "details": [],
                "summary": {
                    "total": 0,
                    "verified_count": 0,
                    "unresolved_count": 0,
                    "sources_used": [],
                },
            }
        )
        audit_notes = list(output.get("audit_notes", []))
        if used_fallback_citations:
            audit_notes.append("writer used fallback citation extraction because output.citations was empty or invalid")
        if verification["hallucinated"]:
            audit_notes.append(
                "citation verification flagged unresolved citations: "
                + ", ".join(verification["hallucinated"][:5])
            )
        document = self._render_document(
            title=title,
            sections=sections,
            output_format=output_format,
            abstract=str(output.get("abstract", "")).strip(),
            target_venue=target_venue,
        )
        results_freeze = self._resolve_results_freeze(task)
        evidence_runs = self._resolve_evidence_runs(task, results_freeze)
        evidence_run_ids = {run.run_id for run in evidence_runs}
        evidence_artifacts = []
        if self.artifact_service is not None:
            evidence_artifacts = [
                artifact
                for artifact in self.artifact_service.list_artifacts()
                if artifact.run_id in evidence_run_ids
            ]
        metrics_registry = build_verified_metrics_registry(
            runs=evidence_runs,
            artifacts=evidence_artifacts,
            results_freeze=results_freeze,
            external_results=[
                item
                for item in task.input_payload.get("external_results", [])
                if isinstance(item, dict)
            ],
        )
        grounding_report = ground_text_numbers(document, metrics_registry)
        if grounding_report["summary"]["ungrounded_count"]:
            audit_notes.append(
                "metric grounding flagged unsupported numbers: "
                + ", ".join(item["token"] for item in grounding_report["ungrounded"][:5])
            )
        verification_report = {
            "citations": citations,
            "used_fallback_citations": used_fallback_citations,
            **verification,
        }
        extension = "tex" if output_format == "latex" else "md"
        artifact_kind = "draft_latex" if output_format == "latex" else "draft_markdown"
        artifact = write_artifact(
            run_id=ctx.run_id,
            artifact_id=f"{ctx.run_id}-draft",
            kind=artifact_kind,
            content=document.strip() + "\n",
            extension=extension,
            metadata={
                "section_count": len(sections),
                "output_format": output_format,
                "target_venue": target_venue,
                "citation_verification": verification.get("summary", verification),
            },
            artifacts_dir=ctx.artifacts_dir or "artifacts",
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(artifact)
        verification_artifact = write_artifact(
            run_id=ctx.run_id,
            artifact_id=f"{ctx.run_id}-citation-verification",
            kind="citation_verification_report",
            content=json.dumps(verification_report, ensure_ascii=False, indent=2),
            extension="json",
            metadata={
                "verified_count": len(verification.get("valid", [])),
                "unresolved_count": len(verification.get("hallucinated", [])),
            },
            artifacts_dir=ctx.artifacts_dir or "artifacts",
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(verification_artifact)
        metrics_registry_artifact = write_artifact(
            run_id=ctx.run_id,
            artifact_id=f"{ctx.run_id}-verified-metrics-registry",
            kind="verified_metrics_registry",
            content=json.dumps(metrics_registry.to_record(), ensure_ascii=False, indent=2),
            extension="json",
            metadata={"entry_count": len(metrics_registry.entries)},
            artifacts_dir=ctx.artifacts_dir or "artifacts",
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(metrics_registry_artifact)
        grounding_artifact = write_artifact(
            run_id=ctx.run_id,
            artifact_id=f"{ctx.run_id}-metric-grounding",
            kind="metric_grounding_report",
            content=json.dumps(grounding_report, ensure_ascii=False, indent=2),
            extension="json",
            metadata=grounding_report["summary"],
            artifacts_dir=ctx.artifacts_dir or "artifacts",
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(grounding_artifact)

        if verification["hallucinated"] and citation_repair_round < 3:
            return AgentResult(
                status="handoff",
                output={
                    "title": title,
                    "sections": sections,
                    "draft_artifact_path": artifact.path,
                    "citation_verification": verification,
                    "metric_grounding": grounding_report,
                },
                artifacts=[
                    artifact.artifact_id,
                    verification_artifact.artifact_id,
                    metrics_registry_artifact.artifact_id,
                    grounding_artifact.artifact_id,
                ],
                next_tasks=[
                    build_child_task(
                        task,
                        kind="write_draft",
                        goal=f"Repair unresolved citations and regenerate the draft (round {citation_repair_round + 1}/3)",
                        input_payload={
                            **task.input_payload,
                            "citation_repair_round": citation_repair_round + 1,
                            "citation_feedback": verification["hallucinated"],
                            "draft_artifact_path": artifact.path,
                        },
                        assigned_agent="writer_agent",
                    )
                ],
                audit_notes=audit_notes,
            )
        if grounding_report["summary"]["ungrounded_count"] and metric_repair_round < 3:
            return AgentResult(
                status="handoff",
                output={
                    "title": title,
                    "sections": sections,
                    "draft_artifact_path": artifact.path,
                    "output_format": output_format,
                    "citation_verification": verification,
                    "metric_grounding": grounding_report,
                },
                artifacts=[
                    artifact.artifact_id,
                    verification_artifact.artifact_id,
                    metrics_registry_artifact.artifact_id,
                    grounding_artifact.artifact_id,
                ],
                next_tasks=[
                    build_child_task(
                        task,
                        kind="write_draft",
                        goal=f"Repair unsupported numeric claims and regenerate the draft (round {metric_repair_round + 1}/3)",
                        input_payload={
                            **task.input_payload,
                            "metric_grounding_round": metric_repair_round + 1,
                            "metric_grounding_feedback": grounding_report["ungrounded"],
                            "draft_artifact_path": artifact.path,
                        },
                        assigned_agent="writer_agent",
                    )
                ],
                audit_notes=audit_notes,
            )
        if verification["hallucinated"]:
            audit_notes.append(
                "citation_repair_failed: " + ", ".join(verification["hallucinated"][:5])
            )
            return AgentResult(
                status="needs_approval",
                output={
                    "title": title,
                    "sections": sections,
                    "draft_artifact_path": artifact.path,
                    "output_format": output_format,
                    "citation_verification": verification,
                    "metric_grounding": grounding_report,
                },
                artifacts=[
                    artifact.artifact_id,
                    verification_artifact.artifact_id,
                    metrics_registry_artifact.artifact_id,
                    grounding_artifact.artifact_id,
                ],
                audit_notes=audit_notes,
            )
        if grounding_report["summary"]["ungrounded_count"]:
            audit_notes.append(
                "metric_grounding_failed: "
                + ", ".join(item["token"] for item in grounding_report["ungrounded"][:5])
            )
            return AgentResult(
                status="needs_approval",
                output={
                    "title": title,
                    "sections": sections,
                    "draft_artifact_path": artifact.path,
                    "output_format": output_format,
                    "citation_verification": verification,
                    "metric_grounding": grounding_report,
                },
                artifacts=[
                    artifact.artifact_id,
                    verification_artifact.artifact_id,
                    metrics_registry_artifact.artifact_id,
                    grounding_artifact.artifact_id,
                ],
                audit_notes=audit_notes,
            )

        next_tasks = [
            build_child_task(
                task,
                kind="style_pass",
                goal="Polish the draft without changing factual content",
                input_payload={
                    "draft_artifact_path": artifact.path,
                    "title": title,
                },
                assigned_agent="style_agent",
            )
        ]

        return AgentResult(
            status="success",
            output={
                "title": title,
                "sections": sections,
                "draft_artifact_path": artifact.path,
                "output_format": output_format,
                "citation_verification": verification,
                "metric_grounding": grounding_report,
            },
            artifacts=[
                artifact.artifact_id,
                verification_artifact.artifact_id,
                metrics_registry_artifact.artifact_id,
                grounding_artifact.artifact_id,
            ],
            next_tasks=next_tasks,
            audit_notes=audit_notes,
        )

    @staticmethod
    def _desired_output_format(target_venue: str) -> str:
        return "latex" if target_venue in {"NeurIPS", "ICLR", "ICML", "ACL"} else "markdown"

    @staticmethod
    def _venue_checklist(target_venue: str) -> list[str]:
        if target_venue in {"NeurIPS", "ICLR", "ICML", "ACL"}:
            return [
                "state compute resources",
                "include limitations",
                "compare baselines fairly under comparable budget",
                "list reproducibility hyperparameters",
                "mention statistical significance when relevant",
            ]
        return []

    @staticmethod
    def _collect_citations(output: dict[str, Any], task: Task) -> tuple[list[str], bool]:
        raw = output.get("citations")
        if isinstance(raw, list):
            citations = [str(item).strip() for item in raw if str(item).strip()]
            if citations:
                return citations, False
        fallback: list[str] = []
        patterns = [
            r"(?:arXiv:\s*\d{4}\.\d{4,5}(?:v\d+)?)",
            r"(?:DOI:\s*10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
            r"(?:10\.\d{4,9}/[-._;()/:A-Z0-9]+)",
            r"(?:\[[A-Z][A-Za-z]+(?:\s+et\s+al\.)?\s+\d{4}[a-z]?\])",
            r"(?:\([A-Z][A-Za-z]+(?:\s+et\s+al\.)?,\s*\d{4}[a-z]?\))",
        ]
        for section in output.get("sections", []):
            if not isinstance(section, dict):
                continue
            markdown = str(section.get("markdown", ""))
            for pattern in patterns:
                fallback.extend(re.findall(pattern, markdown, flags=re.IGNORECASE))
        if fallback:
            filtered = [
                citation
                for citation in list(dict.fromkeys(fallback))
                if not any(citation.startswith(prefix) for prefix in FALSE_POSITIVE_PREFIXES)
            ]
            return filtered, True
        return (
            [str(item).strip() for item in task.input_payload.get("paper_ids", []) if str(item).strip()],
            True,
        )

    @classmethod
    def _render_document(
        cls,
        *,
        title: str,
        sections: list[dict[str, Any]],
        output_format: str,
        abstract: str,
        target_venue: str,
    ) -> str:
        if output_format == "latex":
            return cls._render_latex(title=title, sections=sections, abstract=abstract, target_venue=target_venue)
        markdown = [f"# {title}"]
        if abstract:
            markdown.append(f"\n## Abstract\n\n{abstract}")
        for section in sections:
            markdown.append(f"\n## {section['heading']}\n")
            markdown.append(section["markdown"])
        return "\n".join(markdown)

    @staticmethod
    def _render_latex(
        *,
        title: str,
        sections: list[dict[str, Any]],
        abstract: str,
        target_venue: str,
    ) -> str:
        body = []
        if abstract:
            body.append("\\begin{abstract}\n" + abstract + "\n\\end{abstract}\n")
        for section in sections:
            heading = WriterAgent._escape_latex(str(section.get("heading", "Section")))
            content = WriterAgent._escape_latex(str(section.get("markdown", "")))
            body.append(f"\\section{{{heading}}}\n{content}\n")
        documentclass = "article"
        if target_venue in {"NeurIPS", "ICLR", "ICML", "ACL"}:
            documentclass = "article"
        return (
            f"\\documentclass{{{documentclass}}}\n"
            "\\usepackage[utf8]{inputenc}\n"
            "\\usepackage{hyperref}\n"
            f"\\title{{{WriterAgent._escape_latex(title)}}}\n"
            "\\author{ResearchOS}\n"
            "\\begin{document}\n"
            "\\maketitle\n\n"
            + "\n".join(body)
            + "\n\\end{document}\n"
        )

    @staticmethod
    def _escape_latex(text: str) -> str:
        replacements = {
            "\\": "\\textbackslash{}",
            "&": "\\&",
            "%": "\\%",
            "$": "\\$",
            "#": "\\#",
            "_": "\\_",
            "{": "\\{",
            "}": "\\}",
        }
        escaped = text
        for source, target in replacements.items():
            escaped = escaped.replace(source, target)
        return escaped

    def _resolve_results_freeze(self, task: Task) -> ResultsFreeze | None:
        if self.freeze_service is None:
            return None
        requested_results_id = str(task.input_payload.get("results_id", "")).strip()
        freeze = self.freeze_service.load_results_freeze()
        if freeze is None:
            return None
        if requested_results_id and freeze.results_id != requested_results_id:
            return None
        return freeze

    def _resolve_evidence_runs(self, task: Task, results_freeze: ResultsFreeze | None) -> list[RunManifest]:
        if self.run_service is None:
            return []
        run_ids: list[str] = []
        for value in (
            task.input_payload.get("run_id"),
            *(task.input_payload.get("supporting_run_ids", []) or []),
            *(task.input_payload.get("imported_run_ids", []) or []),
        ):
            if value is None:
                continue
            text = str(value).strip()
            if text:
                run_ids.append(text)
        if results_freeze is not None:
            run_ids.extend(str(item).strip() for item in results_freeze.supporting_run_ids if str(item).strip())
        unique_ids = list(dict.fromkeys(run_ids))
        return [run for run_id in unique_ids if (run := self.run_service.get_run(run_id)) is not None]

    @staticmethod
    def _run_record(run: RunManifest) -> dict[str, Any]:
        return {
            "run_id": run.run_id,
            "spec_id": run.spec_id,
            "status": run.status,
            "metrics": run.metrics,
            "artifacts": run.artifacts,
            "source_type": run.source_type,
            "source_label": run.source_label,
            "source_metadata": run.source_metadata,
            "notes": run.notes,
        }

    @staticmethod
    def _results_freeze_record(freeze: ResultsFreeze) -> dict[str, Any]:
        return {
            "results_id": freeze.results_id,
            "spec_id": freeze.spec_id,
            "main_claims": freeze.main_claims,
            "tables": freeze.tables,
            "figures": freeze.figures,
            "supporting_run_ids": freeze.supporting_run_ids,
            "external_sources": freeze.external_sources,
            "notes": freeze.notes,
        }
