# Phase 3: Interactive Terminal Control Plane

## Summary

ResearchOS now has an interactive terminal control plane on top of the existing scriptable CLI.

The goal of this phase is not a chat shell and not a web UI rewrite. It is a terminal-first operator surface for:

- projects
- tasks
- approvals
- runs
- registries and artifacts

## Launch Command

```powershell
uv run researchos console
```

Optional:

```powershell
uv run researchos console --refresh-interval 1.5
```

## Architecture

The console layer is split into three parts:

- [catalog.py](/C:/Anti%20Project/ResearchOS/app/console/catalog.py)
  - provider/model/profile options and profile builders
- [control_plane.py](/C:/Anti%20Project/ResearchOS/app/console/control_plane.py)
  - reusable service adapter layer
  - no widget logic
  - no duplicated business rules
- [app.py](/C:/Anti%20Project/ResearchOS/app/console/app.py)
  - menu flow, prompts, watch loops, rendering

Rendering is handled with Rich tables and panels. The console calls the existing service/orchestrator layer instead of bypassing domain logic.

## Interactive Features

The console supports:

- listing and creating projects
- listing, creating, dispatching, retrying, and cancelling tasks
- selecting routing profiles through menus
- approval inbox viewing and approval creation
- run listing and live run watch
- task listing and live task watch
- registry inspection for:
  - artifacts
  - paper cards
  - gap maps
  - claims
  - freeze documents

## Provider and Profile Selection

When creating projects or tasks, the console offers:

- inherit system default
- known provider/model presets
- custom provider/model entry

This avoids requiring raw env edits or JSON-heavy command lines for common flows.

## What Remains Classic CLI

The existing subcommands remain intact, including:

- `create-project`
- `create-task`
- `list-tasks`
- `dispatch-task`
- `retry-task`
- `cancel-task`
- registry and freeze commands

These remain the right path for scripting and automation.

## Compatibility Notes

- The new console is additive only.
- Existing command URLs and CLI subcommands are unchanged.
- The console is a thin control plane over existing services.
- No orchestration logic was moved into the terminal layer.
