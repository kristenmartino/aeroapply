"""Geocoding for the SourcingBouncer's geo fence (#89).

Greenhouse/Lever/Ashby postings carry a free-text `location` ("San Francisco, CA",
"Hybrid - Tampa, FL", "Remote - US") with no lat/lon. Without coordinates the
bouncer drops every non-remote posting "to be safe", which silently kills the
hybrid/onsite half of an operator's targeting. This module resolves a location
string to `(lat, lon)` so the commute fence can actually run.

Design:
  * `STATIC_CENTROIDS` — a zero-network lookup of US city/metro centroids. Good
    enough for a 40-mile fence (centroid error ≪ fence radius) and fully
    deterministic, so unit tests need no network.
  * Optional `fallback` (e.g. Nominatim) for strings the table misses, behind a
    per-call rate limit. Off by default; opt in via `build_default_geocoder()`.
  * An in-process cache keyed by the *normalized* string — the same handful of
    location strings recur across thousands of postings, so we geocode each once.

The bouncer owns the geo gate and calls `Geocoder.geocode`; a miss yields a
distinct "unresolvable location" drop reason (vs. "outside commute radius").
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable
from dataclasses import dataclass, field

Coords = tuple[float, float]

# Two-letter abbreviations for the US states that appear in our centroid table.
_STATE_ABBREV: dict[str, str] = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar",
    "california": "ca", "colorado": "co", "connecticut": "ct", "delaware": "de",
    "florida": "fl", "georgia": "ga", "hawaii": "hi", "idaho": "id",
    "illinois": "il", "indiana": "in", "iowa": "ia", "kansas": "ks",
    "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
    "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
    "missouri": "mo", "montana": "mt", "nebraska": "ne", "nevada": "nv",
    "new hampshire": "nh", "new jersey": "nj", "new mexico": "nm", "new york": "ny",
    "north carolina": "nc", "north dakota": "nd", "ohio": "oh", "oklahoma": "ok",
    "oregon": "or", "pennsylvania": "pa", "rhode island": "ri", "south carolina": "sc",
    "south dakota": "sd", "tennessee": "tn", "texas": "tx", "utah": "ut",
    "vermont": "vt", "virginia": "va", "washington": "wa", "west virginia": "wv",
    "wisconsin": "wi", "wyoming": "wy", "district of columbia": "dc",
}

# City/metro centroids, keyed by "city, st" (lowercase, 2-letter state). Approximate
# centroids — precise to well within a commute fence. Extend freely; unknown strings
# fall through to the optional network fallback.
STATIC_CENTROIDS: dict[str, Coords] = {
    # Personas / South & Central Florida
    "springfield, il": (39.7817, -89.6501),
    "tampa, fl": (27.9506, -82.4572),
    "st. petersburg, fl": (27.7676, -82.6403),
    "st petersburg, fl": (27.7676, -82.6403),
    "clearwater, fl": (27.9659, -82.8001),
    "jupiter, fl": (26.9342, -80.0942),
    "west palm beach, fl": (26.7153, -80.0534),
    "miami, fl": (25.7617, -80.1918),
    "fort lauderdale, fl": (26.1224, -80.1373),
    "orlando, fl": (28.5383, -81.3792),
    "jacksonville, fl": (30.3322, -81.6557),
    # Other persona anchors
    "seattle, wa": (47.6062, -122.3321),
    "bellevue, wa": (47.6101, -122.2015),
    "denver, co": (39.7392, -104.9903),
    "boulder, co": (40.0150, -105.2705),
    # Major US metros
    "new york, ny": (40.7128, -74.0060),
    "new york city, ny": (40.7128, -74.0060),
    "nyc, ny": (40.7128, -74.0060),
    "brooklyn, ny": (40.6782, -73.9442),
    "san francisco, ca": (37.7749, -122.4194),
    "oakland, ca": (37.8044, -122.2712),
    "san jose, ca": (37.3382, -121.8863),
    "palo alto, ca": (37.4419, -122.1430),
    "los angeles, ca": (34.0522, -118.2437),
    "san diego, ca": (32.7157, -117.1611),
    "austin, tx": (30.2672, -97.7431),
    "dallas, tx": (32.7767, -96.7970),
    "houston, tx": (29.7604, -95.3698),
    "chicago, il": (41.8781, -87.6298),
    "boston, ma": (42.3601, -71.0589),
    "cambridge, ma": (42.3736, -71.1097),
    "washington, dc": (38.9072, -77.0369),
    "atlanta, ga": (33.7490, -84.3880),
    "portland, or": (45.5152, -122.6784),
    "phoenix, az": (33.4484, -112.0740),
    "philadelphia, pa": (39.9526, -75.1652),
    "minneapolis, mn": (44.9778, -93.2650),
    "nashville, tn": (36.1627, -86.7816),
    "raleigh, nc": (35.7796, -78.6382),
    "charlotte, nc": (35.2271, -80.8431),
    "salt lake city, ut": (40.7608, -111.8910),
}

# Tokens that mark work-arrangement, not place — stripped before matching.
_MODE_TOKENS = re.compile(
    r"\b(remote|hybrid|on[\s-]?site|onsite|in[\s-]?office|wfh|anywhere)\b", re.IGNORECASE
)
_US_SUFFIX = re.compile(r"[,\s]+(usa|us|united states)\s*$", re.IGNORECASE)


def normalize_location(location: str | None) -> str:
    """Reduce a free-text location to a stable lookup/cache key like 'tampa, fl'.

    Strips work-arrangement words ("Hybrid - Tampa, FL" -> "tampa, fl"), a trailing
    country, and surrounding punctuation; expands a spelled-out state to its 2-letter
    code. Returns '' if nothing place-like remains.
    """
    if not location:
        return ""
    text = _MODE_TOKENS.sub(" ", location)
    text = _US_SUFFIX.sub("", text)
    text = text.replace("/", " ").replace("|", " ")
    text = text.strip().strip("-–—•·,").strip().lower()
    text = re.sub(r"\s+", " ", text)
    if not text:
        return ""
    # Expand a spelled-out state in the last comma segment ("tampa, florida" -> "tampa, fl").
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) >= 2 and parts[-1] in _STATE_ABBREV:
        parts[-1] = _STATE_ABBREV[parts[-1]]
    return ", ".join(parts)


@dataclass
class Geocoder:
    """Resolve a location string to `(lat, lon)`, static-table-first then optional fallback.

    `fallback` is any callable `str -> Coords | None` (e.g. a Nominatim wrapper); it is
    only consulted on a static miss, and its results are cached too. The cache is keyed
    by the normalized string so each distinct location is resolved at most once.
    """

    static: dict[str, Coords] = field(default_factory=lambda: STATIC_CENTROIDS)
    fallback: Callable[[str], Coords | None] | None = None
    _cache: dict[str, Coords | None] = field(default_factory=dict)

    def geocode(self, location: str | None) -> Coords | None:
        key = normalize_location(location)
        if not key:
            return None
        if key in self._cache:
            return self._cache[key]
        coords = self._resolve(key)
        self._cache[key] = coords
        return coords

    def _resolve(self, key: str) -> Coords | None:
        if key in self.static:
            return self.static[key]
        # City-only fallback for an unambiguous "city, st" miss isn't safe (many
        # same-named cities), so only the network fallback handles misses.
        if self.fallback is not None:
            try:
                return self.fallback(key)
            except Exception:  # pragma: no cover - network/parse errors must not crash sourcing
                return None
        return None


def _build_nominatim_fallback(min_seconds: float = 1.0) -> Callable[[str], Coords | None] | None:
    """Construct a rate-limited Nominatim lookup, or None if geopy is unavailable.

    Nominatim's usage policy is ≤1 req/s; `RateLimiter` enforces it. Network-gated and
    opt-in (see `build_default_geocoder`) so the default path and tests stay offline.
    """
    try:  # pragma: no cover - exercised only when opted in with network
        from geopy.extra.rate_limiter import RateLimiter
        from geopy.geocoders import Nominatim
    except Exception:
        return None

    geocoder = Nominatim(user_agent="AeroApply/0.1 (sourcing geo fence)")
    limited = RateLimiter(geocoder.geocode, min_delay_seconds=min_seconds)

    def _lookup(key: str) -> Coords | None:  # pragma: no cover - network
        loc = limited(key, country_codes="us")
        return (loc.latitude, loc.longitude) if loc else None

    return _lookup


def build_default_geocoder() -> Geocoder:
    """The geocoder the CLI sourcing path uses.

    Static-only by default (zero network). Set `AEROAPPLY_GEOCODER=nominatim` to enable
    the rate-limited Nominatim fallback for strings the static table misses.
    """
    fallback = None
    if os.getenv("AEROAPPLY_GEOCODER", "").lower() == "nominatim":
        fallback = _build_nominatim_fallback()
    return Geocoder(fallback=fallback)


__all__ = [
    "Coords",
    "Geocoder",
    "STATIC_CENTROIDS",
    "normalize_location",
    "build_default_geocoder",
]
