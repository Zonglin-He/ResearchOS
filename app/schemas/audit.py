from dataclasses import dataclass, field


@dataclass
class AuditReport:
    report_type: str
    status: str
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
