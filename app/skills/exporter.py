from __future__ import annotations

from pathlib import Path

from app.roles.catalog import ROLE_SPECS
from app.roles.prompts import ROLE_PROMPT_REGISTRY
from app.skills.catalog import ROLE_SKILL_REGISTRY
from app.skills.models import SkillSpec


def build_codex_wrapper(skill: SkillSpec) -> str:
    return (
        f"---\n"
        f"name: {skill.name}\n"
        f"description: Thin Codex wrapper for the canonical ResearchOS {skill.role_id.value} role skill. "
        f"Use when the task matches the {skill.role_id.value} role contract.\n"
        f"---\n\n"
        f"Follow the canonical ResearchOS role skill at `{skill.path}`.\n\n"
        f"Required outputs: {', '.join(skill.expected_outputs)}\n"
        f"Validation checklist:\n"
        + "".join(f"- {item}\n" for item in skill.validation_checklist)
    )


def build_claude_wrapper(skill: SkillSpec) -> str:
    return (
        f"# ResearchOS {skill.role_id.value.replace('_', ' ').title()} Skill Wrapper\n\n"
        f"Use the canonical ResearchOS role skill at `{skill.path}`.\n\n"
        f"Trigger when:\n"
        + "".join(f"- {item}\n" for item in skill.when_to_use)
        + "\nDo not use when:\n"
        + "".join(f"- {item}\n" for item in skill.when_not_to_use)
        + f"\nArtifact obligations: {', '.join(skill.expected_outputs)}\n"
    )


def build_gemini_wrapper(skill: SkillSpec) -> str:
    return (
        f"# /{skill.name}\n\n"
        f"Canonical ResearchOS role skill path: `{skill.path}`\n\n"
        f"Use this command wrapper for the `{skill.role_id.value}` role.\n\n"
        f"Expected inputs:\n"
        + "".join(f"- {item}\n" for item in skill.expected_inputs)
        + "Expected outputs:\n"
        + "".join(f"- {item}\n" for item in skill.expected_outputs)
    )


def export_provider_wrappers(output_root: Path) -> list[Path]:
    written: list[Path] = []
    for role_spec in ROLE_SPECS:
        prompt_spec = ROLE_PROMPT_REGISTRY.require_for_role(role_spec.role_id)
        for skill_name in role_spec.canonical_skill_names:
            skill = ROLE_SKILL_REGISTRY.require(skill_name)
            for wrapper in skill.provider_wrappers:
                path = output_root / wrapper.relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                if wrapper.provider == "codex":
                    content = build_codex_wrapper(skill)
                elif wrapper.provider == "claude":
                    content = build_claude_wrapper(skill)
                else:
                    content = build_gemini_wrapper(skill)
                content = (
                    f"<!-- Generated from role prompt {prompt_spec.path} and skill {skill.path}. -->\n"
                    f"{content}"
                )
                path.write_text(content, encoding="utf-8")
                written.append(path)
    return written
