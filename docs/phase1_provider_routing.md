# Phase 1: Explicit Provider and Model Routing

## Summary

ResearchOS now resolves provider and model selection through explicit typed routing objects instead of relying only on environment variables.

The routing layer is additive and backward compatible:

- existing env-based behavior still works
- projects can define a default dispatch profile
- tasks can carry an explicit override
- agents expose a fallback routing policy
- the resolved provider/model is stored in runtime state and persisted on the task

## Routing Objects

- `ProviderSpec`
  - concrete provider choice and optional model
- `ModelProfile`
  - named model/profile preset with optional provider, model, max steps, and metadata
- `DispatchProfile`
  - serializable routing payload attached to system, project, or task
- `AgentRoutingPolicy`
  - agent-level fallback used only when higher layers do not specify a value
- `ResolvedDispatch`
  - effective provider/model/max-steps selection used at runtime

## Exact Precedence Order

For each field (`provider_name`, `model`, `max_steps`) the resolver applies this order:

1. task override
2. project default
3. system default
4. agent fallback

This means:

- task-level dispatch profiles always win
- project profiles override env defaults for tasks in that project
- env defaults still drive behavior when no explicit routing is provided
- agent fallback is only used when the higher layers leave a field unset

## Runtime Visibility

Resolved routing is visible in multiple places:

- `RunContext.routing`
- `AgentResult.routing`
- `Task.last_run_routing`
- builder-created `RunManifest.dispatch_routing`
- orchestrator audit notes

## Examples

### Env only

If:

- `RESEARCHOS_PROVIDER=claude`
- `RESEARCHOS_PROVIDER_MODEL=sonnet`

and neither project nor task specify routing, dispatch resolves to:

- provider: `claude`
- model: `sonnet`

### Project default

If the project has:

```json
{
  "provider": {
    "provider_name": "gemini",
    "model": "gemini-2.5-pro"
  }
}
```

and the task has no override, dispatch resolves to:

- provider: `gemini`
- model: `gemini-2.5-pro`

### Task override

If the project default is Gemini but the task carries:

```json
{
  "provider": {
    "provider_name": "codex",
    "model": "gpt-5.4"
  },
  "max_steps": 22
}
```

dispatch resolves to:

- provider: `codex`
- model: `gpt-5.4`
- max steps: `22`

## CLI and API Serialization

### CLI

`create-project` and `create-task` accept `--dispatch-profile` as JSON.

Example:

```powershell
uv run researchos create-task `
  --task-id t1 `
  --project-id p1 `
  --kind paper_ingest `
  --goal "Read source" `
  --owner you `
  --dispatch-profile "{\"provider\":{\"provider_name\":\"codex\",\"model\":\"gpt-5.4\"}}"
```

### API

`POST /projects` and `POST /tasks` accept nested `dispatch_profile` objects.

## Migration Notes

- SQLite databases are upgraded in place by adding optional routing columns when missing.
- New PostgreSQL deployments work through `Base.metadata.create_all`.
- Existing PostgreSQL databases need a schema migration for:
  - `projects.dispatch_profile`
  - `tasks.dispatch_profile`
  - `tasks.last_run_routing`

No existing CLI or API command is removed in this phase.
