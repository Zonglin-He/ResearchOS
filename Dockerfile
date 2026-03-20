FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY app ./app
COPY prompts ./prompts

RUN pip install uv && uv sync --frozen

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
