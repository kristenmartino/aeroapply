"""DB/migration integration tests. Run only when RUN_DB_TESTS is set (CI, or local
against the Docker container). Each test that writes uses a transaction it rolls
back, so it leaves no residue.
"""

import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_DB_TESTS"),
    reason="set RUN_DB_TESTS=1 and DATABASE_URL to run DB integration tests",
)

EXAMPLE = Path(__file__).resolve().parent.parent / "config" / "profile.example.yaml"


def _connect():
    import psycopg

    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url)


def test_schema_applied_with_pgvector():
    with _connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        assert cur.fetchone() is not None, "vector extension missing"

        cur.execute(
            "SELECT format_type(atttypid, atttypmod) FROM pg_attribute "
            "WHERE attrelid = 'resume_chunk'::regclass AND attname = 'embedding'"
        )
        assert cur.fetchone()[0] == "vector(1536)"

        cur.execute("SELECT indexdef FROM pg_indexes WHERE indexname = 'idx_resume_chunk_embed'")
        assert "hnsw" in cur.fetchone()[0].lower()

        cur.execute("SELECT 1 FROM pg_views WHERE viewname = 'v_icebox_ranked'")
        assert cur.fetchone() is not None, "v_icebox_ranked view missing"


def test_ingest_rank_promote_drop_roundtrip():
    from aeroapply.config import load_profile
    from aeroapply.connectors.base import NormalizedPosting
    from aeroapply.db import repo
    from aeroapply.sourcing.scheduler import rank_icebox

    profile = load_profile(EXAMPLE)
    ai = NormalizedPosting(source_key="greenhouse", external_id="zz1", company="ZZTestCo",
                           title="ZZTEST AI Product Manager", remote_mode="remote", location="Remote")
    ba = NormalizedPosting(source_key="greenhouse", external_id="zz2", company="ZZTestCo",
                           title="ZZTEST Senior Business Analyst", remote_mode="remote", location="Remote")

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)

        c1 = repo.upsert_icebox(conn, user_id, [ai, ba])
        assert c1.applications_inserted == 2

        c2 = repo.upsert_icebox(conn, user_id, [ai, ba])  # idempotent re-source
        assert c2.applications_inserted == 0 and c2.deduped == 2

        icebox = repo.fetch_icebox(conn, user_id)
        by_title = {job["title"]: aid for aid, job, _ in icebox}
        ai_id, ba_id = by_title[ai.title], by_title[ba.title]
        assert all(job["company"] == "ZZTestCo" for _, job, _ in icebox)  # display field for Kanban-lite

        scores = {aid: sj.execution_priority for aid, sj in rank_icebox(conn, user_id, profile.ranking_weights)}
        assert scores[ai_id] > scores[ba_id]   # AI PM (title 1.0) outranks BA (0.6)

        repo.promote(conn, ba_id)               # manual_override -> +100 trump
        scores2 = {aid: sj.execution_priority for aid, sj in rank_icebox(conn, user_id, profile.ranking_weights)}
        assert scores2[ba_id] > scores2[ai_id]

        repo.drop(conn, ai_id)                  # status='user_rejected' -> leaves the Icebox
        remaining = {job["title"] for _, job, _ in repo.fetch_icebox(conn, user_id)}
        assert ai.title not in remaining and ba.title in remaining
    finally:
        conn.rollback()
        conn.close()


def test_snapshot_ranking_debug_persists_components():
    from aeroapply.config import load_profile
    from aeroapply.connectors.base import NormalizedPosting
    from aeroapply.db import repo
    from aeroapply.sourcing.scheduler import snapshot_ranking_debug

    profile = load_profile(EXAMPLE)
    ai = NormalizedPosting(source_key="greenhouse", external_id="zz3", company="ZZTestCo",
                           title="ZZTEST AI Product Manager", remote_mode="remote", location="Remote")
    ba = NormalizedPosting(source_key="greenhouse", external_id="zz4", company="ZZTestCo",
                           title="ZZTEST Senior Business Analyst", remote_mode="remote", location="Remote")

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        repo.upsert_icebox(conn, user_id, [ai, ba])

        ranked = snapshot_ranking_debug(conn, user_id, profile.ranking_weights)
        # No commit: the same connection reads its own uncommitted writes, so the
        # finally: conn.rollback() cleans up all inserted rows (DB-test isolation).

        by_scored = {aid: sj for aid, sj in ranked}
        for app_id, scored in ranked:
            row = conn.execute(
                "SELECT ranking_debug FROM application WHERE id = %s", (app_id,)
            ).fetchone()
            stored = row[0]
            assert stored is not None
            for key, value in scored.components.items():
                assert stored["components"][key] == pytest.approx(value)
            assert stored["execution_priority"] == pytest.approx(scored.execution_priority)
            assert stored["weights"]["title"] == pytest.approx(profile.ranking_weights.title)
        assert set(by_scored) == {aid for aid, _ in ranked}
    finally:
        conn.rollback()
        conn.close()


def test_curation_events_carry_label_and_ranking_context():
    from aeroapply.config import load_profile
    from aeroapply.connectors.base import NormalizedPosting
    from aeroapply.db import repo
    from aeroapply.sourcing.scheduler import snapshot_ranking_debug

    profile = load_profile(EXAMPLE)
    ai = NormalizedPosting(source_key="greenhouse", external_id="zz5", company="ZZTestCo",
                           title="ZZTEST AI Product Manager", remote_mode="remote", location="Remote")
    ba = NormalizedPosting(source_key="greenhouse", external_id="zz6", company="ZZTestCo",
                           title="ZZTEST Senior Business Analyst", remote_mode="remote", location="Remote")

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        repo.upsert_icebox(conn, user_id, [ai, ba])
        snapshot_ranking_debug(conn, user_id, profile.ranking_weights)
        by_title = {job["title"]: aid for aid, job, _ in repo.fetch_icebox(conn, user_id)}

        repo.promote(conn, by_title[ai.title])
        repo.drop(conn, by_title[ba.title])

        def latest_event(app_id):
            return conn.execute(
                """SELECT event_type, actor, payload FROM application_event
                   WHERE application_id = %s ORDER BY created_at DESC LIMIT 1""",
                (app_id,),
            ).fetchone()

        et, actor, payload = latest_event(by_title[ai.title])
        assert (et, actor) == ("promote", "human")
        assert payload["action"] == "promote" and payload["label"] == "manual_override"
        # the human label is paired with the ranker features visible at decision time
        assert payload["ranking_debug"]["components"]["title"] == pytest.approx(1.0)
        assert payload["ranking_debug_present"] is True

        et2, actor2, payload2 = latest_event(by_title[ba.title])
        assert (et2, actor2) == ("drop", "human")
        assert payload2["action"] == "drop" and payload2["label"] == "hard_negative"
        assert payload2["ranking_debug"] is not None
        assert payload2["ranking_debug_present"] is True
    finally:
        conn.rollback()
        conn.close()


def test_curation_event_without_snapshot_flags_missing():
    # The real Kanban path: Promote/Drop with no prior `rank --persist` snapshot, so the
    # label is recorded WITHOUT ranker features and ranking_debug_present is False.
    from aeroapply.config import load_profile
    from aeroapply.connectors.base import NormalizedPosting
    from aeroapply.db import repo

    profile = load_profile(EXAMPLE)
    job = NormalizedPosting(source_key="greenhouse", external_id="zz7", company="ZZTestCo",
                            title="ZZTEST AI Product Manager", remote_mode="remote", location="Remote")

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        repo.upsert_icebox(conn, user_id, [job])
        app_id = next(aid for aid, j, _ in repo.fetch_icebox(conn, user_id) if j["title"] == job.title)

        repo.promote(conn, app_id)  # no snapshot taken first

        payload = conn.execute(
            """SELECT payload FROM application_event
               WHERE application_id = %s ORDER BY created_at DESC LIMIT 1""",
            (app_id,),
        ).fetchone()[0]
        assert payload["action"] == "promote" and payload["label"] == "manual_override"
        assert payload["ranking_debug"] is None
        assert payload["ranking_debug_present"] is False
    finally:
        conn.rollback()
        conn.close()


def test_kanban_autosnapshot_makes_curation_paired():
    # Mirrors the Kanban UI path: snapshot_row (now wired before Promote/Drop) means a
    # bare curation action — no prior `rank --persist` — still lands ranking_debug_present=True.
    from aeroapply.config import load_profile
    from aeroapply.connectors.base import NormalizedPosting
    from aeroapply.db import repo
    from aeroapply.ui.board import build_board, snapshot_row

    profile = load_profile(EXAMPLE)
    job = NormalizedPosting(source_key="greenhouse", external_id="zz8", company="ZZTestCo",
                            title="ZZTEST AI Product Manager", remote_mode="remote", location="Remote")

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        repo.upsert_icebox(conn, user_id, [job])

        rows = build_board(conn, user_id, profile.ranking_weights)
        row = rows[0]
        snapshot_row(conn, row, profile.ranking_weights)  # what the Kanban does pre-Promote
        repo.promote(conn, row.application_id)

        payload = conn.execute(
            """SELECT payload FROM application_event
               WHERE application_id = %s ORDER BY created_at DESC LIMIT 1""",
            (row.application_id,),
        ).fetchone()[0]
        assert payload["action"] == "promote" and payload["label"] == "manual_override"
        assert payload["ranking_debug_present"] is True
        for key, value in row.components.items():
            assert payload["ranking_debug"]["components"][key] == pytest.approx(value)
    finally:
        conn.rollback()
        conn.close()
