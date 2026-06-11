from datetime import UTC, datetime, timedelta

from aeroapply.sourcing.bouncer import (
    DROP_OUTSIDE_RADIUS,
    DROP_UNRESOLVABLE_LOCATION,
    BouncerConfig,
    SourcingBouncer,
)
from aeroapply.sourcing.geocoding import Geocoder

# Tampa anchor, 40-mi fence — for the geocoding geo-gate tests below.
_TAMPA_CFG = BouncerConfig(home_coords=(27.9506, -82.4572), max_commute_miles=40)


def test_parse_max_salary_handles_messy_bands():
    b = SourcingBouncer()
    assert b.parse_max_salary("$120k - $160,000") == 160000
    assert b.parse_max_salary("Up to 150K") == 150000
    assert b.parse_max_salary(None) == 0
    assert b.parse_max_salary("") == 0


def test_low_salary_is_dropped():
    # The default floor is 0 (off) — gates only fire when a profile configures one.
    b = SourcingBouncer(BouncerConfig(min_salary_floor=120_000))
    keep, _ = b.should_keep(
        {"title": "AI Product Manager", "description": "", "salary_text": "$80k-$100k", "remote_mode": "remote"}
    )
    assert keep is False


def test_unlisted_salary_passes_through():
    b = SourcingBouncer(BouncerConfig(min_salary_floor=120_000))
    keep, _ = b.should_keep(
        {"title": "AI Product Manager", "description": "Great role", "remote_mode": "remote"}
    )
    assert keep is True


def test_title_regex_drop():
    b = SourcingBouncer()
    keep, reason = b.should_keep(
        {"title": "Junior Product Manager", "description": "", "remote_mode": "remote"}
    )
    assert keep is False and "title" in reason


def test_legal_blocker_drop():
    b = SourcingBouncer()
    keep, _ = b.should_keep(
        {"title": "AI Product Manager", "description": "US Citizens only", "remote_mode": "remote"}
    )
    assert keep is False


def test_ghost_job_drop():
    b = SourcingBouncer()
    old = datetime.now(UTC) - timedelta(days=60)
    keep, _ = b.should_keep(
        {"title": "AI Product Manager", "description": "", "remote_mode": "remote", "posted_at": old}
    )
    assert keep is False


# --- geo gate with geocoding (#89) -----------------------------------------
def test_geocoded_hybrid_within_radius_is_kept():
    b = SourcingBouncer(_TAMPA_CFG, geocoder=Geocoder())
    keep, reason = b.should_keep(
        {"title": "AI Product Manager", "description": "",
         "remote_mode": "hybrid", "location": "St. Petersburg, FL"}  # ~20 mi from Tampa
    )
    assert keep is True and reason == "keep"


def test_geocoded_onsite_outside_radius_is_dropped_with_radius_reason():
    b = SourcingBouncer(_TAMPA_CFG, geocoder=Geocoder())
    keep, reason = b.should_keep(
        {"title": "AI Product Manager", "description": "",
         "remote_mode": "onsite", "location": "Seattle, WA"}  # far from Tampa
    )
    assert keep is False and reason == DROP_OUTSIDE_RADIUS


def test_unresolvable_location_drops_with_distinct_reason():
    b = SourcingBouncer(_TAMPA_CFG, geocoder=Geocoder())
    keep, reason = b.should_keep(
        {"title": "AI Product Manager", "description": "",
         "remote_mode": "onsite", "location": "Nowhereville, ZZ"}
    )
    assert keep is False and reason == DROP_UNRESOLVABLE_LOCATION


def test_no_geocoder_keeps_prior_safe_drop_for_missing_coords():
    # Without a geocoder, a non-remote posting lacking coords still drops "to be safe".
    b = SourcingBouncer(_TAMPA_CFG)
    keep, reason = b.should_keep(
        {"title": "AI Product Manager", "description": "",
         "remote_mode": "onsite", "location": "St. Petersburg, FL"}
    )
    assert keep is False and reason == DROP_OUTSIDE_RADIUS


def test_remote_posting_skips_geocoding_entirely():
    # A geocoder that would explode proves remote short-circuits before any lookup.
    def boom(_: str):
        raise AssertionError("remote must not geocode")

    b = SourcingBouncer(_TAMPA_CFG, geocoder=Geocoder(static={}, fallback=boom))
    keep, reason = b.should_keep(
        {"title": "AI Product Manager", "description": "",
         "remote_mode": "remote", "location": "anywhere"}
    )
    assert keep is True and reason == "keep"
