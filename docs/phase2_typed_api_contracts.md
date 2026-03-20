# Phase 2: Typed API Schemas and Contract Cleanup

## Summary

This phase removes raw `dict` request bodies from the registry-backed API endpoints and replaces them with typed Pydantic schemas.

The main goals were:

- stronger request and response contracts
- cleaner handlers
- better validation errors
- improved OpenAPI output
- preserved endpoint URLs

## Endpoints Migrated

The following endpoints now use typed request and response models:

- `POST /paper-cards`
- `GET /paper-cards`
- `POST /gap-maps`
- `GET /gap-maps`
- `POST /freezes/topic`
- `GET /freezes/topic`
- `POST /freezes/spec`
- `GET /freezes/spec`
- `POST /freezes/results`
- `GET /freezes/results`

## Contract Structure

API I/O schemas now live under:

- [schemas](/C:/Anti%20Project/ResearchOS/app/api/schemas)

The old [models.py](/C:/Anti%20Project/ResearchOS/app/api/models.py) file remains as a compatibility re-export layer for existing imports.

This keeps the refactor additive and avoids a hidden architectural leap.

## Separation of Concerns

- domain models remain under `app/schemas`
- API request/response models now live under `app/api/schemas`
- handlers convert API models into domain objects explicitly

This avoids leaking persistence or registry details into the public API contract.

## Validation Improvements

Before this phase, several handlers manually indexed payloads like:

- `payload["paper_id"]`
- `payload["topic"]`
- `payload["spec_id"]`

That pattern is now removed from the migrated endpoints.

Validation failures are now handled by FastAPI/Pydantic as `422 Unprocessable Entity` responses with field-level error messages.

Examples:

- missing `title` in `POST /paper-cards`
- missing `gap_id` in a nested gap inside `POST /gap-maps`
- wrong type for `selected_gap_ids` in `POST /freezes/topic`

## Compatibility Notes

- Endpoint URLs are unchanged.
- Existing happy-path payload shapes remain accepted.
- Response bodies remain compatible at the field level for the migrated endpoints.
- The main change is stronger validation and explicit OpenAPI typing.

No migration is required for storage because this phase only changes API boundary types.
