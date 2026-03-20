test:
	uv run pytest -q

api:
	uv run uvicorn app.api.app:create_app --factory --host 127.0.0.1 --port 8000

init-db:
	uv run researchos init-db
