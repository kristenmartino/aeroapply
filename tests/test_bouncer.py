from datetime import UTC, datetime, timedelta

from aeroapply.sourcing.bouncer import SourcingBouncer


def test_parse_max_salary_handles_messy_bands():
    b = SourcingBouncer()
    assert b.parse_max_salary("$120k - $160,000") == 160000
    assert b.parse_max_salary("Up to 150K") == 150000
    assert b.parse_max_salary(None) == 0
    assert b.parse_max_salary("") == 0


def test_low_salary_is_dropped():
    b = SourcingBouncer()
    keep, _ = b.should_keep(
        {"title": "AI Product Manager", "description": "", "salary_text": "$80k-$100k", "remote_mode": "remote"}
    )
    assert keep is False


def test_unlisted_salary_passes_through():
    b = SourcingBouncer()
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
