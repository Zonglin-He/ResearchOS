from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ApprovalCreate(BaseModel):
    approval_id: str
    project_id: str
    target_type: str
    target_id: str
    approved_by: str
    decision: str
    comment: str = ""


class ApprovalRead(ApprovalCreate):
    created_at: datetime
