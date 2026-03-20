import asyncio
import json
from pathlib import Path

from app.agents.reader import ReaderAgent
from app.providers.base import BaseProvider
from app.roles import ROLE_PROMPT_REGISTRY, ROLE_REGISTRY, WorkflowRole, role_routing_policy_for_role
from app.skills import ROLE_SKILL_REGISTRY, export_provider_wrappers
from app.schemas.context import RunContext
from app.schemas.task import Task


class CapturingProvider(BaseProvider):
    def __init__(self, payload: dict) -> None:
        self.payload = payload
        self.system_prompt = ""
        self.user_payload: dict[str, object] = {}

    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        tools=None,
        response_schema=None,
        model=None,
    ) -> dict:
        self.system_prompt = system_prompt
        self.user_payload = json.loads(user_input)
        return self.payload


def test_all_roles_have_prompt_and_skill_coverage() -> None:
    for role in WorkflowRole:
        role_spec = ROLE_REGISTRY.require(role)
        prompt_spec = ROLE_PROMPT_REGISTRY.require_for_role(role)
        skill_specs = ROLE_SKILL_REGISTRY.list_for_role(role)

        assert role_spec.canonical_prompt_id == prompt_spec.prompt_id
        assert prompt_spec.path.exists()
        assert skill_specs
        for skill_name in role_spec.canonical_skill_names:
            assert ROLE_SKILL_REGISTRY.require(skill_name).path.exists()


def test_reader_agent_resolves_canonical_role_prompt_and_skill_metadata() -> None:
    provider = CapturingProvider(
        {
            "paper_cards": [
                {
                    "paper_id": "p-1",
                    "title": "Test Paper",
                    "problem": "Weak retrieval grounding",
                    "setting": "open-domain QA",
                    "task_type": "retrieval",
                    "evidence_refs": [{"section": "3", "page": 4}],
                }
            ]
        }
    )
    agent = ReaderAgent(provider)
    task = Task(
        task_id="t-reader-role-assets",
        project_id="proj",
        kind="paper_ingest",
        goal="Read source papers",
        input_payload={"topic": "retrieval"},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-reader-role-assets", project_id="proj", task_id=task.task_id)

    asyncio.run(agent.run(task, ctx))

    assert "ResearchOS canonical role contract prompt:" in provider.system_prompt
    assert "Mission:" in provider.system_prompt
    assert "Retrieve, filter, and normalize sources into structured paper cards." in provider.system_prompt

    assert provider.user_payload["role_contract"]["resolved_role"] == "librarian"
    role_assets = provider.user_payload["role_assets"]
    assert role_assets["prompt"]["prompt_id"] == "librarian"
    assert role_assets["skills"][0]["name"] == "researchos-librarian"


def test_role_skill_registry_supports_metadata_first_and_lazy_instruction_loading() -> None:
    spec = ROLE_SKILL_REGISTRY.require("researchos-verifier")

    assert spec.description.startswith("Verify evidence chains")
    instructions = ROLE_SKILL_REGISTRY.load_instructions("researchos-verifier")

    assert "ResearchOS Verifier" in instructions
    assert "Do not use this skill to fake citation validation" in instructions


def test_provider_wrapper_export_generation(tmp_path: Path) -> None:
    written = export_provider_wrappers(tmp_path)

    assert written
    codex_wrapper = tmp_path / "codex" / "researchos-librarian" / "SKILL.md"
    claude_wrapper = tmp_path / "claude" / "researchos-librarian.md"
    gemini_wrapper = tmp_path / "gemini" / "commands" / "researchos-librarian.md"

    assert codex_wrapper.exists()
    assert claude_wrapper.exists()
    assert gemini_wrapper.exists()
    assert "canonical ResearchOS role skill" in codex_wrapper.read_text(encoding="utf-8")


def test_role_contract_prompt_skill_and_routing_align_for_current_task_kinds() -> None:
    librarian = ROLE_REGISTRY.require(WorkflowRole.LIBRARIAN)
    prompt = ROLE_PROMPT_REGISTRY.require_for_role(WorkflowRole.LIBRARIAN)
    skill = ROLE_SKILL_REGISTRY.require(librarian.canonical_skill_names[0])
    routing = role_routing_policy_for_role(WorkflowRole.LIBRARIAN)

    assert prompt.prompt_id == librarian.canonical_prompt_id
    assert skill.role_id == WorkflowRole.LIBRARIAN
    assert routing.role_name == WorkflowRole.LIBRARIAN.value
    assert routing.family_priority[0] == "gemini"
