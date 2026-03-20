from __future__ import annotations

from pathlib import Path

from app.schemas.claim import Claim
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class ClaimService:
    def __init__(self, registry_path: str | Path = "registry/claims.jsonl") -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()

    def register_claim(self, claim: Claim) -> Claim:
        append_jsonl(self.registry_path, to_record(claim))
        return claim

    def get_claim(self, claim_id: str) -> Claim | None:
        for claim in self.list_claims():
            if claim.claim_id == claim_id:
                return claim
        return None

    def list_claims(self) -> list[Claim]:
        rows = read_jsonl(self.registry_path)
        return [
            Claim(
                claim_id=row["claim_id"],
                text=row["text"],
                claim_type=row["claim_type"],
                supported_by_runs=row.get("supported_by_runs", []),
                supported_by_tables=row.get("supported_by_tables", []),
                risk_level=row.get("risk_level", "medium"),
                approved_by_human=row.get("approved_by_human", False),
            )
            for row in rows
        ]
