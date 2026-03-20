from __future__ import annotations

from pathlib import Path

from app.roles.models import WorkflowRole
from app.skills.models import ProviderWrapperSpec, RoleSkillRegistry, SkillSpec


_SKILLS_DIR = Path(__file__).resolve().parents[2] / "skills"


def _wrappers(role_slug: str) -> tuple[ProviderWrapperSpec, ...]:
    codex_slug = f"researchos-{role_slug}"
    return (
        ProviderWrapperSpec(
            provider="codex",
            relative_path=f"codex/{codex_slug}/SKILL.md",
            wrapper_kind="skill",
        ),
        ProviderWrapperSpec(
            provider="claude",
            relative_path=f"claude/{codex_slug}.md",
            wrapper_kind="subagent_wrapper",
        ),
        ProviderWrapperSpec(
            provider="gemini",
            relative_path=f"gemini/commands/{codex_slug}.md",
            wrapper_kind="command_wrapper",
        ),
    )


def _skill(
    *,
    role: WorkflowRole,
    description: str,
    when_to_use: tuple[str, ...],
    when_not_to_use: tuple[str, ...],
    expected_inputs: tuple[str, ...],
    expected_outputs: tuple[str, ...],
    procedure_steps: tuple[str, ...],
    validation_checklist: tuple[str, ...],
    safety_notes: tuple[str, ...],
    tags: tuple[str, ...] = (),
) -> SkillSpec:
    role_slug = role.value.replace("_", "-")
    return SkillSpec(
        name=f"researchos-{role_slug}",
        role_id=role,
        description=description,
        when_to_use=when_to_use,
        when_not_to_use=when_not_to_use,
        expected_inputs=expected_inputs,
        expected_outputs=expected_outputs,
        procedure_steps=procedure_steps,
        validation_checklist=validation_checklist,
        safety_notes=safety_notes,
        path=_SKILLS_DIR / role_slug / "SKILL.md",
        provider_wrappers=_wrappers(role_slug),
        tags=tags,
    )


ROLE_SKILL_SPECS: tuple[SkillSpec, ...] = (
    _skill(
        role=WorkflowRole.SCOPER,
        description="Decompose a research problem into bounded questions, phases, and task graph edges.",
        when_to_use=("Topic is broad or ambiguous.", "A project needs first-pass decomposition."),
        when_not_to_use=("A frozen spec already exists.", "The task is pure execution or formatting."),
        expected_inputs=("topic", "constraints", "current evidence"),
        expected_outputs=("research_question_tree", "task_decomposition"),
        procedure_steps=(
            "State the core question and operator constraints.",
            "Split the question into answerable subquestions.",
            "Identify blockers, dependencies, and the first actionable task.",
        ),
        validation_checklist=(
            "Every subquestion is independently testable.",
            "The first task can run without hidden prerequisites.",
        ),
        safety_notes=("Do not invent evidence.", "Escalate when scope or approval boundaries are unclear."),
        tags=("planning", "decomposition"),
    ),
    _skill(
        role=WorkflowRole.LIBRARIAN,
        description="Search, filter, screen, and normalize sources into structured paper cards.",
        when_to_use=("A task needs source retrieval.", "Paper cards must be produced from search results or summaries."),
        when_not_to_use=("The task is hypothesis drafting or experiment execution.",),
        expected_inputs=("topic", "source summary or search scope", "selection criteria"),
        expected_outputs=("paper_card", "screening notes"),
        procedure_steps=(
            "Search or parse candidate sources.",
            "Screen for direct relevance and extract concrete evidence.",
            "Emit paper cards with evidence refs and explicit uncertainties.",
        ),
        validation_checklist=(
            "Paper cards include problem, setting, and task type.",
            "Unsupported details are pushed into uncertainties, not facts.",
        ),
        safety_notes=("Do not fabricate citations.", "Do not approve a research direction from retrieval alone."),
        tags=("retrieval", "paper-card"),
    ),
    _skill(
        role=WorkflowRole.SYNTHESIZER,
        description="Aggregate paper cards into gap maps, claim clusters, and candidate research directions.",
        when_to_use=("Multiple paper cards exist.", "The operator needs gap analysis or claim clustering."),
        when_not_to_use=("The task is fresh retrieval with no usable evidence base.",),
        expected_inputs=("paper cards", "topic", "constraints"),
        expected_outputs=("gap_map", "claim_clusters"),
        procedure_steps=(
            "Group evidence by theme and attack surface.",
            "Separate observed gaps from speculative opportunities.",
            "Rank candidate directions with explicit rationale.",
        ),
        validation_checklist=(
            "Each gap links back to supporting papers when available.",
            "Novelty, difficulty, and uncertainty are explicit.",
        ),
        safety_notes=("Do not collapse disagreements into a fake consensus.",),
        tags=("synthesis", "gap-map"),
    ),
    _skill(
        role=WorkflowRole.HYPOTHESIST,
        description="Generate falsifiable hypotheses and bounded research directions from current evidence.",
        when_to_use=("A gap map exists and the project needs candidate hypotheses.",),
        when_not_to_use=("The task is direct execution or writing polish.",),
        expected_inputs=("gap map", "paper cards", "topic freeze if present"),
        expected_outputs=("hypothesis_set",),
        procedure_steps=(
            "Translate each promising gap into one or more falsifiable claims.",
            "Filter out directions that are not novel, feasible, or measurable.",
            "State what evidence would confirm or falsify each hypothesis.",
        ),
        validation_checklist=(
            "Each hypothesis is testable.",
            "Baseline alternatives are considered.",
        ),
        safety_notes=("Do not optimize for novelty at the cost of falsifiability.",),
        tags=("ideation", "hypothesis"),
    ),
    _skill(
        role=WorkflowRole.EXPERIMENT_DESIGNER,
        description="Turn hypotheses into experiment specs with baselines, metrics, ablations, and budget.",
        when_to_use=("A hypothesis set needs an executable spec.",),
        when_not_to_use=("The task is pure retrieval, review, or archival.",),
        expected_inputs=("hypothesis set", "constraints", "resource budget"),
        expected_outputs=("experiment_spec",),
        procedure_steps=(
            "Pick baselines, metrics, datasets, and failure criteria.",
            "Define ablations and budget-sensitive execution ordering.",
            "Emit a spec that an executor can run without hidden assumptions.",
        ),
        validation_checklist=(
            "Spec includes baseline and ablation plan.",
            "Budget, stop conditions, and success criteria are present.",
        ),
        safety_notes=("Do not hide expensive steps inside vague implementation notes.",),
        tags=("spec", "budget", "ablation"),
    ),
    _skill(
        role=WorkflowRole.EXECUTOR,
        description="Execute specs safely, collect artifacts, and record reproducible run manifests.",
        when_to_use=("An approved experiment spec is ready to run.",),
        when_not_to_use=("No concrete experiment spec exists.",),
        expected_inputs=("experiment spec", "repo state", "dataset snapshot"),
        expected_outputs=("run_manifest", "artifact list"),
        procedure_steps=(
            "Confirm execution preconditions and required tools.",
            "Run the experiment with explicit config and seed capture.",
            "Register artifacts and record failures without suppression.",
        ),
        validation_checklist=(
            "Run manifest includes config, dataset snapshot, seed, and artifacts.",
            "Failed runs are still recorded honestly.",
        ),
        safety_notes=("Do not mutate frozen specs silently.", "Stop and escalate when sandbox or approval gates block execution."),
        tags=("execution", "run-manifest"),
    ),
    _skill(
        role=WorkflowRole.ANALYST,
        description="Interpret run results, isolate anomalies, and separate observed evidence from speculation.",
        when_to_use=("A run manifest and outputs need interpretation.",),
        when_not_to_use=("No run evidence exists.",),
        expected_inputs=("run manifest", "metrics", "artifacts"),
        expected_outputs=("result_summary",),
        procedure_steps=(
            "Identify the main result deltas against baselines.",
            "Call out anomalies and plausible causes separately.",
            "Recommend next actions tied to concrete evidence gaps or anomalies.",
        ),
        validation_checklist=(
            "Observed outcomes and speculation are separated.",
            "Result summary references the run being analyzed.",
        ),
        safety_notes=("Do not imply statistical significance if it was not checked.",),
        tags=("analysis", "anomaly"),
    ),
    _skill(
        role=WorkflowRole.REVIEWER,
        description="Check structure, completeness, consistency, and blocking issues before downstream approval or publication.",
        when_to_use=("An artifact or run needs structured review.",),
        when_not_to_use=("The task is source retrieval or pure archival curation.",),
        expected_inputs=("artifacts", "claims", "review scope"),
        expected_outputs=("review_report",),
        procedure_steps=(
            "Inspect required artifacts and compare them to task obligations.",
            "List blocking issues, missing evidence, and consistency failures.",
            "Emit a clear decision plus rationale and follow-up expectations.",
        ),
        validation_checklist=(
            "Decision and blocking issues are explicit.",
            "Missing baselines or missing evidence are flagged.",
        ),
        safety_notes=("Do not downgrade critical issues into vague prose.",),
        tags=("review", "quality"),
    ),
    _skill(
        role=WorkflowRole.VERIFIER,
        description="Verify evidence chains and methodological validity without overstating what was actually checked.",
        when_to_use=("Claims, runs, or freezes need verification review.",),
        when_not_to_use=("The system lacks even registry-level evidence to inspect.",),
        expected_inputs=("run manifest", "claims", "freeze state"),
        expected_outputs=("verification_report",),
        procedure_steps=(
            "Map each claim or result to recorded evidence.",
            "Check completeness, missing links, and methodological red flags.",
            "Emit verification status plus concrete remediation steps.",
        ),
        validation_checklist=(
            "Verification scope is explicit.",
            "Missing evidence is recorded as missing, not guessed.",
        ),
        safety_notes=("Never claim citation verification beyond available evidence.",),
        tags=("verification", "evidence"),
    ),
    _skill(
        role=WorkflowRole.PUBLISHER,
        description="Draft sections and papers that stay aligned with frozen evidence and approved claims.",
        when_to_use=("A draft or section must be written from approved material.",),
        when_not_to_use=("Claims are still unfrozen or under verification dispute.",),
        expected_inputs=("frozen claims", "supporting artifacts", "writing scope"),
        expected_outputs=("section_draft", "paper_draft"),
        procedure_steps=(
            "Choose the requested scope and target audience.",
            "Translate approved evidence into concise structured prose.",
            "Keep claim-to-evidence traceability visible for review.",
        ),
        validation_checklist=(
            "Draft uses only supported claims.",
            "Sections follow the requested scope rather than free-form expansion.",
        ),
        safety_notes=("Do not add evidence-free interpretation to pad narrative flow.",),
        tags=("writing", "draft"),
    ),
    _skill(
        role=WorkflowRole.ARCHIVIST,
        description="Curate archive entries, durable lessons, and provenance links after runs and reviews complete.",
        when_to_use=("A run or task has produced durable lessons or provenance worth keeping.",),
        when_not_to_use=("The data is only transient debugging noise.",),
        expected_inputs=("run summary", "lesson candidates", "provenance notes"),
        expected_outputs=("archive_entry", "lesson linkage"),
        procedure_steps=(
            "Distill durable lessons from transient logs.",
            "Link lessons, artifacts, and provenance references cleanly.",
            "Record archive entries that future roles can retrieve before acting.",
        ),
        validation_checklist=(
            "Archive entries point to source evidence or task context.",
            "Lessons remain reusable across runs.",
        ),
        safety_notes=("Do not treat ephemeral execution noise as durable knowledge.",),
        tags=("archival", "lessons", "provenance"),
    ),
)

ROLE_SKILL_REGISTRY = RoleSkillRegistry(ROLE_SKILL_SPECS)
