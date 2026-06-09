from pathlib import Path

import pytest

from aeroapply.config import Profile, Settings, load_profile
from aeroapply.sourcing.bouncer import SourcingBouncer

ROOT = Path(__file__).resolve().parent.parent
EXAMPLE = ROOT / "config" / "profile.example.yaml"
PERSONAS = sorted((ROOT / "config" / "profiles").glob("*.yaml"))


def test_settings_defaults():
    s = Settings()
    assert s.min_ats_score == 0.90
    assert s.min_agent_confidence == 0.95
    assert s.wip_limit == 5
    assert s.database_url.startswith("postgresql")


def test_example_profile_loads_and_validates():
    p = load_profile(EXAMPLE)
    assert isinstance(p, Profile)
    # The committed example is the FICTIONAL "Alex Example" persona (PII boundary).
    assert p.operator.name == "Alex Example"
    assert p.search_profile.salary_floor == 100000
    assert any("Product Manager" in t.title for t in p.target_roles)


def test_ranking_weights_sum_to_one():
    p = load_profile(EXAMPLE)
    w = p.ranking_weights
    total = w.title + w.location + w.recency + w.competition + w.urgency
    assert abs(total - 1.0) < 1e-9


def test_profile_builds_working_bouncer_config():
    p = load_profile(EXAMPLE)
    bc = p.to_bouncer_config()
    assert bc.min_salary_floor == 100000
    assert bc.home_coords == (39.7817, -89.6501)  # the fictional Springfield anchor
    bouncer = SourcingBouncer(bc)
    keep, _ = bouncer.should_keep(
        {"title": "Product Manager", "remote_mode": "remote", "description": ""}
    )
    assert keep is True


@pytest.mark.parametrize("path", PERSONAS, ids=lambda p: p.stem)
def test_committed_test_personas_load_and_validate(path: Path):
    """Every fixture persona in config/profiles/ must parse, validate, and build a bouncer."""
    p = load_profile(path)
    assert isinstance(p, Profile)
    assert p.operator.primary_email.endswith("@example.com")  # fictional only
    SourcingBouncer(p.to_bouncer_config())  # regexes compile


def test_personas_exist():
    assert len(PERSONAS) >= 3, "expected the committed fictional personas in config/profiles/"
