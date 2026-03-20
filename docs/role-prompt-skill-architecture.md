# Role Prompt and Skill Architecture

ResearchOS uses a two-layer role asset design:

1. Canonical repo-owned source
   - role prompts in `prompts/roles/`
   - role skills in `skills/<role>/SKILL.md`
2. Provider-specific thin wrappers
   - generated on demand with `python scripts/export_role_assets.py`
   - output under `provider_exports/`

The canonical layer is the source of truth. Provider-specific wrappers are export artifacts, not the place where role logic lives.

## Why this architecture

- Role prompts carry responsibility boundaries, artifact obligations, escalation conditions, and handoff expectations.
- Role skills carry reusable workflow procedure and validation checklists.
- Runtime agents resolve role contracts, canonical role prompts, and skill metadata lazily.
- Provider-specific exports stay thin so Codex, Claude, and Gemini wrappers do not drift into three separate implementations.

## Sources reviewed

### Official mechanism docs

| Source | Useful pattern | Classification | Notes |
| --- | --- | --- | --- |
| [OpenAI Codex skills docs](https://developers.openai.com/codex/skills) | `SKILL.md` + optional `scripts/`, `references/`, `assets/`; progressive disclosure; metadata-driven triggering | Adopt pattern | This directly informed the canonical skill folder shape and lazy metadata loading. |
| [OpenAI Docs MCP page](https://developers.openai.com/learn/docs-mcp) | Explicit tool/config snippets for Codex CLI and MCP-backed docs retrieval | Adapt pattern | Useful as an example of repo-owned instructions plus thin tool-specific integration. |
| [Claude Code tutorials](https://code.claude.com/docs/en/tutorials) | Subagent usage and slash-command-centric workflow organization | Adapt pattern | Helped shape thin Claude wrappers and the separation between role contract and provider wrapper. |
| [Claude Code interactive mode docs](https://docs.anthropic.com/en/docs/claude-code/interactive-mode) | Slash-command interaction model | Adapt pattern | Reinforced that Claude-facing wrappers should stay command/subagent friendly instead of duplicating canonical prompts. |
| [Gemini CLI README](https://github.com/google-gemini/gemini-cli) | Custom commands, `GEMINI.md`, MCP integration, extension structure | Adapt pattern | Informed Gemini command-wrapper exports and the choice to keep per-role invocation explicit. |

### GitHub repositories and community catalogs

| Source | Useful pattern | Classification | License / attribution | Safety notes |
| --- | --- | --- | --- | --- |
| [openai/skills](https://github.com/openai/skills) | Curated skill packaging and naming patterns | Adapt pattern | Review the specific skill license before copying any content; no wholesale copying used here. | Treat third-party scripts as untrusted until reviewed. |
| [anthropics/skills](https://github.com/anthropics/skills) | Claude-oriented skill packaging and task-focused boundaries | Adapt pattern | Anthropic skills include mixed ownership and per-folder guidance; do not assume blanket reuse. | Avoid importing hidden slash-command side effects or unsafe shell assumptions. |
| [Orchestra-Research/AI-Research-SKILLs](https://github.com/Orchestra-Research/AI-Research-SKILLs) | Role-rich research workflow breakdown and research-specific skill decomposition | Adapt pattern | MIT license at repo level, but ResearchOS rewrites prompts and skills instead of vendoring them. | Large domain libraries can overfit to one research stack; use only the workflow decomposition pattern. |
| [am-will/codex-skills](https://github.com/am-will/codex-skills) | Small, targeted Codex skill packaging | Adapt pattern | Review per-repo terms before copying content; no direct content copied here. | Reject skills that bake in overly broad shell autonomy. |
| [VoltAgent/awesome-agent-skills](https://github.com/VoltAgent/awesome-agent-skills) | Discovery catalog of skill patterns and role/task coverage | Adopt pattern for research only | Catalog only; use it to find ideas, not as a content source. | Catalog entries are not automatically trustworthy. |
| [gemini-cli-extensions/conductor](https://github.com/gemini-cli-extensions/conductor) | Command-wrapper pattern and context/spec/plan lifecycle | Adapt pattern | Apache-2.0 at repo level. No direct command content copied. | Strong workflow control is useful; heavy token-consuming global context injection was rejected. |

## Patterns borrowed

Adopted:
- metadata-first skill discovery
- `SKILL.md` as the canonical executable guide
- optional wrapper/export generation per provider
- concise, task-trigger-oriented descriptions

Adapted:
- Claude subagent wrapper style into thin markdown exports
- Gemini custom-command wrapper style into generated command markdown
- research workflow decomposition from large research-skill libraries into smaller role-specific contracts

Rejected:
- giant monolithic “super skill” libraries loaded eagerly into every run
- hidden shell automation or unchecked execution defaults from third-party skills
- persona-heavy prompts with weak artifact contracts
- provider-specific forks of the same role logic

## Safety rules for importing third-party skills

- Treat all third-party skills as untrusted until reviewed.
- Never copy shell snippets or scripts without checking for destructive behavior, secret exfiltration, network side effects, or prompt injection.
- Prefer adapting workflow patterns and checklists over copying prose.
- Keep canonical role prompts and canonical role skills repo-owned.
- If a snippet is copied verbatim in the future, add attribution and license notes next to the file or in this document.

## Maintainer workflow

When adding or updating a role prompt or role skill:

1. Update `app/roles/catalog.py` if the role contract changes.
2. Update the canonical prompt in `prompts/roles/`.
3. Update the canonical skill in `skills/<role>/SKILL.md`.
4. Update `app/skills/catalog.py` metadata if inputs, outputs, or wrapper exports change.
5. Run `python scripts/export_role_assets.py` if provider wrappers need regeneration.
6. Run the role asset tests before merging.

## Why ResearchOS does not vendor large third-party skill blobs

ResearchOS uses external repos as design input, not as the canonical execution substrate. Large vendored skill blobs tend to:

- drift from ResearchOS task and artifact contracts
- hide unsafe shell assumptions
- create provider-specific fragmentation
- bloat runtime context

That is why canonical prompts and skills are intentionally short, boundary-driven, and repo-owned.
