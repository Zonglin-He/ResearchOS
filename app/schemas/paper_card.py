from dataclasses import dataclass, field


@dataclass
class EvidenceRef:
    section: str
    page: int


@dataclass
class PaperCard:
    paper_id: str
    title: str
    problem: str
    setting: str
    task_type: str
    core_assumption: list[str] = field(default_factory=list)
    method_summary: str = ""
    key_modules: list[str] = field(default_factory=list)
    datasets: list[str] = field(default_factory=list)
    metrics: list[str] = field(default_factory=list)
    strongest_result: str = ""
    claimed_contributions: list[str] = field(default_factory=list)
    hidden_dependencies: list[str] = field(default_factory=list)
    likely_failure_modes: list[str] = field(default_factory=list)
    repro_risks: list[str] = field(default_factory=list)
    idea_seeds: list[str] = field(default_factory=list)
    evidence_refs: list[EvidenceRef] = field(default_factory=list)
