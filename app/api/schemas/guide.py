from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ResearchStartRequest(BaseModel):
    research_goal: str
    project_name: str = ""
    project_id: str = ""
    owner: str = "operator"
    keywords: list[str] = Field(default_factory=list)
    max_papers: int = 8
    expected_min_papers: int = 5
    auto_dispatch: bool = True


class IdeaCandidateRead(BaseModel):
    gap_id: str
    score: float | None = None
    rationale: str = ""


class AutopilotRead(BaseModel):
    dispatched_task_ids: list[str]
    stop_reason: str
    human_select_task_id: str | None = None


class ResearchStartResponse(BaseModel):
    project_id: str
    project_name: str
    intake_task_id: str
    autopilot: AutopilotRead
    next_step: str


class AdoptDirectionRequest(BaseModel):
    project_id: str
    human_select_task_id: str
    gap_id: str
    research_question: str = ""
    operator_note: str = ""
    novelty_type: list[str] = Field(default_factory=list)
    owner: str = "operator"
    auto_dispatch: bool = True


class AdoptDirectionResponse(BaseModel):
    topic_id: str
    build_task_id: str
    autopilot: AutopilotRead
    next_step: str


class AutopilotResponse(BaseModel):
    project_id: str
    autopilot: AutopilotRead


class DiscussionMessage(BaseModel):
    message_id: int | None = None
    role: str
    content: str
    created_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscussDirectionRequest(BaseModel):
    project_id: str
    human_select_task_id: str
    gap_id: str
    user_message: str = ""
    history: list[DiscussionMessage] = Field(default_factory=list)


class DiscussDirectionResponse(BaseModel):
    thread_id: str
    assistant_message: str
    gap_id: str
    topic: str
    strengths: list[str]
    risks: list[str]
    next_checks: list[str]
    cited_papers: list[str]
    research_question_suggestion: str
    assistant_role: str
    provider_name: str
    model_name: str
    reasoning_effort: str
    skill_name: str


class DiscussionHistoryRead(BaseModel):
    thread_id: str
    messages: list[DiscussionMessage] = Field(default_factory=list)
