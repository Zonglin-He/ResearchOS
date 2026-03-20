from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.api.schemas.routing import DispatchProfileModel


class ProjectCreate(BaseModel):
    project_id: str
    name: str
    description: str
    status: str = "active"
    dispatch_profile: DispatchProfileModel | None = None


class ProjectRead(ProjectCreate):
    created_at: datetime
