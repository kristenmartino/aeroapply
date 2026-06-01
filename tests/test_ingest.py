from aeroapply.connectors.base import NormalizedPosting
from aeroapply.sourcing.bouncer import SourcingBouncer
from aeroapply.sourcing.ingest import plan_ingest


def _posting(**kw):
    base = dict(
        source_key="greenhouse", external_id="x", company="Acme",
        title="AI Product Manager", remote_mode="remote", description="",
    )
    base.update(kw)
    return NormalizedPosting(**base)


def test_plan_ingest_drops_junk_keeps_good_and_dedupes():
    good = _posting(external_id="1", title="AI Product Manager")
    junk_title = _posting(external_id="2", title="Junior Analyst")              # seniority drop
    junk_legal = _posting(external_id="3", description="US Citizens only")       # clearance drop
    dup = _posting(external_id="4", title="AI Product Manager")                  # same fingerprint as good

    plan = plan_ingest([good, junk_title, junk_legal, dup], SourcingBouncer())

    assert plan.fetched == 4
    assert plan.kept == 1
    assert plan.deduped_in_batch == 1
    assert plan.dropped.get("drop: title/seniority regex") == 1
    assert plan.dropped.get("drop: legal/clearance blocker") == 1
    # nothing was written anywhere — plan_ingest is pure
    assert [p.external_id for p in plan.survivors] == ["1"]
