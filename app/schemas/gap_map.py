from dataclasses import dataclass, field


@dataclass
class Gap:
    gap_id: str
    description: str
    supporting_papers: list[str] = field(default_factory=list)
    attack_surface: str = ""
    difficulty: str = ""
    novelty_type: str = ""


@dataclass
class GapCluster:
    name: str
    gaps: list[Gap] = field(default_factory=list)


@dataclass
class GapMap:
    topic: str
    clusters: list[GapCluster] = field(default_factory=list)
