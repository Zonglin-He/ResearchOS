from dataclasses import dataclass, field


@dataclass
class Claim:
    claim_id: str
    text: str
    claim_type: str
    supported_by_runs: list[str] = field(default_factory=list)
    supported_by_tables: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    approved_by_human: bool = False
