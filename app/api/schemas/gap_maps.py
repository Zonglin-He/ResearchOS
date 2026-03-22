from __future__ import annotations

from pydantic import BaseModel, Field


class GapCreate(BaseModel):
    gap_id: str
    description: str
    supporting_papers: list[str] = Field(default_factory=list)
    evidence_summary: str = ""
    attack_surface: str = ""
    difficulty: str = ""
    novelty_type: str = ""
    feasibility: str = ""
    novelty_score: float = 0.0


class GapClusterCreate(BaseModel):
    name: str
    gaps: list[GapCreate] = Field(default_factory=list)


class GapMapCreate(BaseModel):
    topic: str
    clusters: list[GapClusterCreate] = Field(default_factory=list)


class GapMapRead(GapMapCreate):
    pass


class GapMapSummaryRead(BaseModel):
    topic: str
    clusters: int


class GapMapCreateResponse(BaseModel):
    topic: str
