from pathlib import Path

from aeroapply.config import Profile, Settings, load_profile
from aeroapply.sourcing.bouncer import SourcingBouncer

EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "profile.example.yaml"


def test_settings_defaults():
    s = Settings()
    assert s.min_ats_score == 0.90
    assert s.min_agent_confidence == 0.95
    assert s.wip_limit == 5
    assert s.database_url.startswith("postgresql")


def test_example_profile_loads_and_validates():
    p = load_profile(EXAMPLE)
    assert isinstance(p, Profile)
    assert p.search_profile.salary_floor == 115000
    assert any("AI Product Manager" in t.title for t in p.target_roles)


def test_ranking_weights_sum_to_one():
    p = load_profile(EXAMPLE)
    w = p.ranking_weights
    total = w.title + w.location + w.recency + w.competition + w.urgency
    assert abs(total - 1.0) < 1e-9


def test_profile_builds_working_bouncer_config():
    p = load_profile(EXAMPLE)
    bc = p.to_bouncer_config()
    assert bc.min_salary_floor == 115000
    assert bc.home_coords == (26.9342, -80.0942)
    bouncer = SourcingBouncer(bc)
    keep, _ = bouncer.should_keep(
        {"title": "AI Product Manager", "remote_mode": "remote", "description": ""}
    )
    assert keep is True
