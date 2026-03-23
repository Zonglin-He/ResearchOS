from __future__ import annotations

import re
from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import WRITER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task, write_artifact
from app.roles import writer_role_binding
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService
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

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        target_venue = str(task.input_payload.get("target_venue", "")).strip()
        output_format = self._desired_output_format(target_venue)
        payload["writer_focus"] = {
            "required_outputs": ["title", "sections", "audit_notes", "citations"],
            "hard_constraints": [
                "write only from frozen evidence",
                "do not invent new results",
                "keep claim-evidence alignment explicit",
            ],
            "output_format": output_format,
            "target_venue": target_venue,
            "venue_checklist": self._venue_checklist(target_venue),
        }
        return payload

    def build_result(self, task: Task, ctx, output: dict[str, Any]) -> AgentResult:
        title = output.get("title", "Draft")
        sections = output.get("sections", [])
        target_venue = str(task.input_payload.get("target_venue", "")).strip()
        output_format = str(output.get("output_format", "")).strip().lower() or self._desired_output_format(target_venue)
        repair_round = max(0, int(task.input_payload.get("citation_repair_round", 0) or 0))
        citations, used_fallback_citations = self._collect_citations(output, task)
        verification = verify_citations(citations) if citations else {"valid": [], "hallucinated": []}
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
                "citation_verification": verification,
            },
            artifacts_dir=ctx.artifacts_dir or "artifacts",
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(artifact)

        if verification["hallucinated"] and repair_round < 3:
            return AgentResult(
                status="handoff",
                output={
                    "title": title,
                    "sections": sections,
                    "draft_artifact_path": artifact.path,
                    "citation_verification": verification,
                },
                artifacts=[artifact.artifact_id],
                next_tasks=[
                    build_child_task(
                        task,
                        kind="write_draft",
                        goal=f"Repair unresolved citations and regenerate the draft (round {repair_round + 1}/3)",
                        input_payload={
                            **task.input_payload,
                            "citation_repair_round": repair_round + 1,
                            "citation_feedback": verification["hallucinated"],
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
                },
                artifacts=[artifact.artifact_id],
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
            },
            artifacts=[artifact.artifact_id],
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
