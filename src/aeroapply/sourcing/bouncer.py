"""SourcingBouncer — edge filter that drops junk jobs BEFORE any DB write.

Runs inside the 24/7 sourcing daemon. Every scraped posting passes through
`should_keep()`; failures are discarded (and optionally counted) so the Icebox
and the heavy LLMs never see garbage. Rules are loaded from config/profile.yaml
(see `bouncer:` and `search_profile:`), with the defaults below matching the
canonical brief.

See: docs/SOURCING_AND_RANKING.md
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

try:  # geopy is optional at import time so unit tests can run without it
    from geopy.distance import geodesic
except Exception:  # pragma: no cover
    geodesic = None

if TYPE_CHECKING:
    from aeroapply.sourcing.geocoding import Geocoder

# Geo-gate drop reasons (distinct so calibration can tell a real out-of-range posting
# from one we simply couldn't place — #89).
DROP_OUTSIDE_RADIUS = "drop: hybrid/onsite outside commute radius"
DROP_UNRESOLVABLE_LOCATION = "drop: unresolvable location"


@dataclass(frozen=True)
class BouncerConfig:
    """Defaults are NEUTRAL/FICTIONAL placeholders (PII boundary, Brief §2) — the real
    operator values come from config/profile.yaml via `Profile.to_bouncer_config()`.
    """

    home_coords: tuple[float, float] = (39.7817, -89.6501)  # Springfield, IL — fictional anchor
    max_commute_miles: float = 40.0
    min_salary_floor: int = 0  # 0 = salary gate off until the profile sets a floor
    max_age_days: int = 45
    drop_title_regex: str = (  # seniority junk only; industry exclusions are per-profile
        r"\b(junior|associate|entry[\s-]?level|intern(ship)?|graduate)\b"
    )
    legal_blocker_regex: str = (
        r"\b(active ts/sci|top secret|polygraph|clearance required|"
        r"no c2c|w2 only|us citizens only)\b"
    )


@dataclass
class SourcingBouncer:
    config: BouncerConfig = field(default_factory=BouncerConfig)
    # Optional geocoder: resolves a non-remote posting's free-text location to lat/lon
    # when the connector couldn't (e.g. Greenhouse). None preserves prior behavior.
    geocoder: Geocoder | None = None

    def __post_init__(self) -> None:
        self._bad_titles = re.compile(self.config.drop_title_regex, re.IGNORECASE)
        self._legal = re.compile(self.config.legal_blocker_regex, re.IGNORECASE)

    # --- individual gates -------------------------------------------------
    def check_location(self, remote_mode: str, lat: float | None, lon: float | None) -> bool:
        """Remote passes immediately. Hybrid/onsite are fenced by commute distance."""
        if remote_mode and remote_mode.lower() == "remote":
            return True
        if lat is None or lon is None:
            return False  # not remote and no coordinates -> drop, to be safe
        if geodesic is None:  # pragma: no cover
            return True  # geopy unavailable: don't false-drop in tests
        miles = geodesic(self.config.home_coords, (lat, lon)).miles
        return bool(miles <= self.config.max_commute_miles)

    def _geo_decision(self, job: dict[str, Any]) -> tuple[bool, str]:
        """Geo gate with optional geocoding: (keep?, reason).

        Remote always keeps. For non-remote postings missing coordinates, try the
        geocoder against the free-text `location`; a miss is a *distinct* drop reason
        from a successfully-placed posting that is simply out of range (#89).
        """
        remote_mode = job.get("remote_mode") or ""
        if remote_mode.lower() == "remote":
            return True, "keep"

        lat, lon = job.get("lat"), job.get("lon")
        if (lat is None or lon is None) and self.geocoder is not None:
            coords = self.geocoder.geocode(job.get("location"))
            if coords is None:
                return False, DROP_UNRESOLVABLE_LOCATION
            lat, lon = coords

        if lat is None or lon is None:
            # No geocoder configured (or nothing to resolve) — keep the prior safe drop.
            return False, DROP_OUTSIDE_RADIUS
        if self.check_location(remote_mode, lat, lon):
            return True, "keep"
        return False, DROP_OUTSIDE_RADIUS

    @staticmethod
    def parse_max_salary(salary_text: str | None) -> int:
        """Extract the MAX value from messy bands like '$120k - $160,000' or 'Up to 150K'.

        Returns 0 when unparseable/unlisted — callers treat 0 as 'let it through'.
        """
        if not salary_text:
            return 0
        clean = salary_text.lower().replace(",", "")
        values: list[int] = []
        for num, is_k in re.findall(r"(\d+)(k)?", clean):
            val = int(num)
            if is_k or val < 1000:  # '150k' or bare '150' -> 150000
                val *= 1000
            values.append(val)
        return max(values) if values else 0

    # --- main gate --------------------------------------------------------
    def should_keep(self, job: dict[str, Any]) -> tuple[bool, str]:
        """Return (keep?, reason). Cheapest regex checks first to save compute."""
        # 1. Seniority / industry
        if self._bad_titles.search(job.get("title", "")):
            return False, "drop: title/seniority regex"

        # 2. Clearance / visa (per operator work authorization)
        if self._legal.search(job.get("description", "")):
            return False, "drop: legal/clearance blocker"

        # 3. Salary floor — only drop when a salary is stated AND too low.
        max_sal = self.parse_max_salary(job.get("salary_text"))
        if 0 < max_sal < self.config.min_salary_floor:
            return False, f"drop: max salary {max_sal} < floor"

        # 4. Geo fence (geocodes a missing location when a geocoder is configured)
        geo_keep, geo_reason = self._geo_decision(job)
        if not geo_keep:
            return False, geo_reason

        # 5. Ghost-job expiration
        posted = job.get("posted_at")
        if isinstance(posted, datetime):
            if posted.tzinfo is None:
                posted = posted.replace(tzinfo=UTC)
            age = (datetime.now(UTC) - posted).days
            if age > self.config.max_age_days:
                return False, f"drop: {age}d old (ghost job)"

        return True, "keep"


__all__ = [
    "SourcingBouncer",
    "BouncerConfig",
    "DROP_OUTSIDE_RADIUS",
    "DROP_UNRESOLVABLE_LOCATION",
]
