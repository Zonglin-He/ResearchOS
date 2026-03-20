# Iteration A

Iteration A hardens control-plane integration without changing the core ResearchOS architecture.

## Included Changes

- API contract cleanup for artifact, registry, and freeze endpoints
- workspace-root-aware registry and artifact path resolution
- a true deterministic `local` provider backend
- API dispatch smoke coverage in CI using the local provider
- direct terminal launch with `researchos` and the short alias `ros`

## Operator Notes

- Keep using existing CLI subcommands for automation.
- Use `researchos` with no subcommand for the interactive control plane.
- Use `RESEARCHOS_WORKSPACE_ROOT` when you want registry and artifact state isolated per workspace.
- Use the `local` provider for demos, CI, smoke tests, and onboarding.

## Verification

Recommended local verification commands:

```powershell
python -m compileall app tests
uv run pytest -q
uv run pytest tests\integration\test_dispatch_workflow.py -q
uv run researchos --help
uv run ros --help
```
