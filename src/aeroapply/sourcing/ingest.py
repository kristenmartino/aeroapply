"""Read-only ingestion planning: bouncer edge-filter + in-batch dedupe.

Pure step — no DB, no network. Takes normalized postings, applies the
SourcingBouncer (drops never persist), dedupes within the batch by fingerprint,
and returns survivors + a per-reason drop tally. The DB write (job + icebox
application) is in `aeroapply.db.repo`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from aeroapply.connectors.base import NormalizedPosting
from aeroapply.sourcing.bouncer import SourcingBouncer


@dataclass
class IngestPlan:
    fetched: int
    survivors: list[NormalizedPosting]
    dropped: dict[str, int] = field(default_factory=dict)
    deduped_in_batch: int = 0

    @property
    def kept(self) -> int:
        return len(self.survivors)


def plan_ingest(postings: Iterable[NormalizedPosting], bouncer: SourcingBouncer) -> IngestPlan:
    items = list(postings)
    survivors: list[NormalizedPosting] = []
    dropped: dict[str, int] = {}
    seen: set[str] = set()
    deduped = 0
    for p in items:
        keep, reason = bouncer.should_keep(p.to_bouncer_dict())
        if not keep:
            dropped[reason] = dropped.get(reason, 0) + 1
            continue
        fp = p.fingerprint()
        if fp in seen:
            deduped += 1
            continue
        seen.add(fp)
        survivors.append(p)
    return IngestPlan(
        fetched=len(items), survivors=survivors, dropped=dropped, deduped_in_batch=deduped
    )


__all__ = ["IngestPlan", "plan_ingest"]
