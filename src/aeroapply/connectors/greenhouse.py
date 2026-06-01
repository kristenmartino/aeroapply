"""Greenhouse public Job Board API connector — READ-ONLY.

Uses the public, unauthenticated `boards-api.greenhouse.io` endpoint (the same data
that powers company career pages). No login, no ToS gray area, no apply path. This
is the canonical Tier-A source for the first ingestion wedge.

Caveats / follow-ups:
- Location is a free-text string with no lat/lon, so non-remote postings cannot be
  geo-fenced without a geocoder (future work) — the bouncer drops hybrid/onsite
  postings that lack coordinates. Remote roles flow through.
- The public API exposes only `updated_at` (last-edit time), NOT a first-publication
  date. It is mapped to `posted_at`, so the bouncer's 45-day ghost-job filter is
  unreliable for this source: a stale posting with any recent edit reads as fresh.
- No rate-limiting / retry here; callers must throttle across multiple boards. A 429
  surfaces as `httpx.HTTPStatusError` via `raise_for_status()`.
"""

from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any

import httpx

from aeroapply.connectors.base import NormalizedPosting

BOARDS_API = "https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_TOKEN_RE = re.compile(r"[A-Za-z0-9_-]+")  # Greenhouse board tokens are alphanumeric slugs


def _strip_html(raw: str) -> str:
    text = html.unescape(raw or "")
    text = _TAG_RE.sub(" ", text)
    return _WS_RE.sub(" ", text).strip()


def _infer_remote(location: str | None) -> str | None:
    loc = (location or "").lower()
    if "remote" in loc:
        return "remote"
    if "hybrid" in loc:
        return "hybrid"
    return None  # unknown; onsite geocoding is future work


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


class GreenhouseConnector:
    key = "greenhouse"
    kind = "api"
    autonomy_tier = "A"

    def __init__(self, board_token: str, company: str | None = None, *, timeout: float = 15.0):
        # Validate before URL interpolation — reject path-traversal / query injection.
        if not _TOKEN_RE.fullmatch(board_token or ""):
            raise ValueError(f"invalid Greenhouse board_token: {board_token!r}")
        self.board_token = board_token
        self.company = company or board_token
        self._timeout = timeout

    def fetch_raw(self) -> list[dict[str, Any]]:
        resp = httpx.get(
            BOARDS_API.format(token=self.board_token),
            params={"content": "true"},
            timeout=self._timeout,
            headers={"User-Agent": "AeroApply/0.1 (read-only job sourcing)"},
        )
        resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return list(data.get("jobs", []))

    def normalize(self, raw_jobs: list[dict[str, Any]]) -> list[NormalizedPosting]:
        return [self._normalize_one(j) for j in raw_jobs]

    def fetch(self) -> list[NormalizedPosting]:
        return self.normalize(self.fetch_raw())

    def _normalize_one(self, j: dict[str, Any]) -> NormalizedPosting:
        location = (j.get("location") or {}).get("name")
        url = j.get("absolute_url")
        return NormalizedPosting(
            source_key=self.key,
            external_id=str(j.get("id") or ""),  # null id -> "" (not the string "None")
            company=self.company,
            title=(j.get("title") or "").strip(),
            location=location,
            remote_mode=_infer_remote(location),
            description=_strip_html(j.get("content", "")),
            url=url,
            portal_url=url,
            portal_type="greenhouse",
            posted_at=_parse_dt(j.get("updated_at")),
            raw=j,
        )


__all__ = ["GreenhouseConnector"]
