from __future__ import annotations

from pydantic import BaseModel, Field


class ClaimCreate(BaseModel):
    claim_id: str
    text: str
    claim_type: str
    risk_level: str = "medium"
    approved_by_human: bool = False


class ClaimRead(ClaimCreate):
    supported_by_runs: list[str] = Field(default_factory=list)
    supported_by_tables: list[str] = Field(default_factory=list)
