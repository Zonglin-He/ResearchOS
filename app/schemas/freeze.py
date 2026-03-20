from dataclasses import dataclass, field


@dataclass
class TopicFreeze:
    topic_id: str
    selected_gap_ids: list[str]
    research_question: str
    novelty_type: list[str] = field(default_factory=list)
    owner: str = ""
    status: str = "approved"


@dataclass
class SpecFreeze:
    spec_id: str
    topic_id: str
    hypothesis: list[str] = field(default_factory=list)
    must_beat_baselines: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    fairness_constraints: list[str] = field(default_factory=list)
    ablations: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    failure_criteria: list[str] = field(default_factory=list)
    approved_by: str = ""
    status: str = "approved"


@dataclass
class ResultsFreeze:
    results_id: str
    spec_id: str
    main_claims: list[str] = field(default_factory=list)
    tables: list[str] = field(default_factory=list)
    figures: list[str] = field(default_factory=list)
    approved_by: str = ""
    status: str = "approved"
