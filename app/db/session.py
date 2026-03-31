from __future__ import annotations

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateColumn

from app.db.base import Base
from app.db.models import TaskModel


def _ensure_task_columns(engine) -> None:
    inspector = inspect(engine)
    if "tasks" not in inspector.get_table_names():
        return

    existing_columns = {column["name"] for column in inspector.get_columns("tasks")}
    missing_columns = [
        TaskModel.__table__.c.latest_strategy_trace,
        TaskModel.__table__.c.latest_retrieval_evidence,
        TaskModel.__table__.c.latest_handoff_packet,
    ]

    statements: list[str] = []
    for column in missing_columns:
        if column.name in existing_columns:
            continue
        compiled = str(CreateColumn(column).compile(dialect=engine.dialect)).strip()
        statements.append(f"ALTER TABLE tasks ADD COLUMN {compiled}")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))


def create_session_factory(database_url: str) -> sessionmaker:
    engine = create_engine(database_url, future=True)
    Base.metadata.create_all(engine)
    _ensure_task_columns(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)
