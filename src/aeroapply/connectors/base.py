"""Connector contract + the normalized posting every source connector emits.

READ-ONLY sourcing only: connectors fetch and normalize postings. They never
submit, create accounts, or file applications. `NormalizedPosting` maps onto the
`job` table and feeds the SourcingBouncer + the Python ranker.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field


class NormalizedPosting(BaseModel):
    """A connector-agnostic posting. One per scraped job, before any DB write."""

    source_key: str
    external_id: str
    company: str
    title: str
    location: str | None = None
    remote_mode: str | None = None  # remote | hybrid | onsite | None (unknown)
    lat: float | None = None
    lon: float | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_text: str | None = None  # free-text band for the bouncer's parser
    currency: str = "USD"
    description: str = ""
    requirements: dict[str, Any] = Field(default_factory=dict)
    url: str | None = None
    portal_url: str | None = None
    portal_type: str | None = None
    posted_at: datetime | None = None
    closing_date: datetime | None = None
    applicant_count: int | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    def fingerprint(self) -> str:
        """Dedupe key = sha256(company|title|location), 64 hex chars (matches job.fingerprint)."""
        key = f"{self.company}|{self.title}|{self.location or ''}".lower()
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def to_bouncer_dict(self) -> dict[str, Any]:
        """The dict shape `SourcingBouncer.should_keep` expects."""
        return {
            "title": self.title,
            "description": self.description,
            "salary_text": self.salary_text,
            "remote_mode": self.remote_mode,
            "lat": self.lat,
            "lon": self.lon,
            "posted_at": self.posted_at,
        }


class SourceConnector(Protocol):
    """Read-only source connector. No apply/submit surface by contract."""

    key: str
    kind: str           # 'api' | 'browser'
    autonomy_tier: str  # 'A' | 'B' | 'C'

    def fetch(self) -> list[NormalizedPosting]: ...


__all__ = ["NormalizedPosting", "SourceConnector"]
