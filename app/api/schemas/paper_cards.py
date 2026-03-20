from __future__ import annotations

from pydantic import BaseModel, Field


class EvidenceRefModel(BaseModel):
    section: str
    page: int


class PaperCardCreate(BaseModel):
    paper_id: str
    title: str
    problem: str
    setting: str
    task_type: str
    core_assumption: list[str] = Field(default_factory=list)
    method_summary: str = ""
    key_modules: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    strongest_result: str = ""
    claimed_contributions: list[str] = Field(default_factory=list)
    hidden_dependencies: list[str] = Field(default_factory=list)
    likely_failure_modes: list[str] = Field(default_factory=list)
    repro_risks: list[str] = Field(default_factory=list)
    idea_seeds: list[str] = Field(default_factory=list)
    evidence_refs: list[EvidenceRefModel] = Field(default_factory=list)


class PaperCardRead(PaperCardCreate):
    pass


class PaperCardSummaryRead(BaseModel):
    paper_id: str
    title: str
    task_type: str


class PaperCardCreateResponse(BaseModel):
    paper_id: str
