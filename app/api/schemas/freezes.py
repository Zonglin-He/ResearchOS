from __future__ import annotations

from pydantic import BaseModel, Field


class TopicFreezeSave(BaseModel):
    topic_id: str
    selected_gap_ids: list[str]
    research_question: str
    novelty_type: list[str] = Field(default_factory=list)
    owner: str = ""
    status: str = "approved"


class TopicFreezeRead(TopicFreezeSave):
    pass


class TopicFreezeSaveResponse(BaseModel):
    topic_id: str


class SpecFreezeSave(BaseModel):
    spec_id: str
    topic_id: str
    hypothesis: list[str] = Field(default_factory=list)
    must_beat_baselines: list[str] = Field(default_factory=list)
    datasets: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    fairness_constraints: list[str] = Field(default_factory=list)
    ablations: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    failure_criteria: list[str] = Field(default_factory=list)
    target_venue: str = ""
    human_constraints: list[str] = Field(default_factory=list)
    approved_by: str = ""
    status: str = "approved"


class SpecFreezeRead(SpecFreezeSave):
    pass


class SpecFreezeSaveResponse(BaseModel):
    spec_id: str


class ResultsFreezeSave(BaseModel):
    results_id: str
    spec_id: str
    main_claims: list[str] = Field(default_factory=list)
    tables: list[str] = Field(default_factory=list)
    figures: list[str] = Field(default_factory=list)
    approved_by: str = ""
    status: str = "approved"


class ResultsFreezeRead(ResultsFreezeSave):
    pass


class ResultsFreezeSaveResponse(BaseModel):
    results_id: str
