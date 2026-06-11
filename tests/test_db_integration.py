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
    from aeroapply.sourcing.ranking import RankingPersona
    from aeroapply.sourcing.scheduler import rank_icebox

    profile = load_profile(EXAMPLE)
    persona = RankingPersona.from_profile(profile)
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

        scores = {aid: sj.execution_priority for aid, sj in rank_icebox(conn, user_id, profile.ranking_weights, persona)}
        assert scores[ai_id] > scores[ba_id]   # AI PM (title 1.0) outranks BA (0.6)

        repo.promote(conn, ba_id)               # manual_override -> +100 trump
        scores2 = {aid: sj.execution_priority for aid, sj in rank_icebox(conn, user_id, profile.ranking_weights, persona)}
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
    from aeroapply.sourcing.ranking import RankingPersona
    from aeroapply.sourcing.scheduler import snapshot_ranking_debug

    profile = load_profile(EXAMPLE)
    persona = RankingPersona.from_profile(profile)
    ai = NormalizedPosting(source_key="greenhouse", external_id="zz3", company="ZZTestCo",
                           title="ZZTEST AI Product Manager", remote_mode="remote", location="Remote")
    ba = NormalizedPosting(source_key="greenhouse", external_id="zz4", company="ZZTestCo",
                           title="ZZTEST Senior Business Analyst", remote_mode="remote", location="Remote")

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        repo.upsert_icebox(conn, user_id, [ai, ba])

        ranked = snapshot_ranking_debug(conn, user_id, profile.ranking_weights, persona)
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
    from aeroapply.sourcing.ranking import RankingPersona
    from aeroapply.sourcing.scheduler import snapshot_ranking_debug

    profile = load_profile(EXAMPLE)
    persona = RankingPersona.from_profile(profile)
    ai = NormalizedPosting(source_key="greenhouse", external_id="zz5", company="ZZTestCo",
                           title="ZZTEST AI Product Manager", remote_mode="remote", location="Remote")
    ba = NormalizedPosting(source_key="greenhouse", external_id="zz6", company="ZZTestCo",
                           title="ZZTEST Senior Business Analyst", remote_mode="remote", location="Remote")

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        repo.upsert_icebox(conn, user_id, [ai, ba])
        snapshot_ranking_debug(conn, user_id, profile.ranking_weights, persona)
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
    from aeroapply.sourcing.ranking import RankingPersona
    from aeroapply.ui.board import build_board, snapshot_row

    profile = load_profile(EXAMPLE)
    persona = RankingPersona.from_profile(profile)
    job = NormalizedPosting(source_key="greenhouse", external_id="zz8", company="ZZTestCo",
                            title="ZZTEST AI Product Manager", remote_mode="remote", location="Remote")

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        repo.upsert_icebox(conn, user_id, [job])

        rows = build_board(conn, user_id, profile.ranking_weights, persona)
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


# --- M2: WIP-scheduler promotion + checkpointed execution graph ---------------------
def test_promote_top_n_respects_wip_limit_and_audits():
    from aeroapply.config import load_profile
    from aeroapply.connectors.base import NormalizedPosting
    from aeroapply.db import repo
    from aeroapply.sourcing.ranking import RankingPersona
    from aeroapply.sourcing.scheduler import promote_top_n

    profile = load_profile(EXAMPLE)
    persona = RankingPersona.from_profile(profile)
    postings = [
        NormalizedPosting(source_key="greenhouse", external_id=f"zzq{i}", company="ZZQueueCo",
                          title=title, remote_mode="remote", location="Remote")
        for i, title in enumerate([
            "ZZTEST Product Manager",          # core 1.0 -> should win slot 1
            "ZZTEST Business Analyst",         # adjacent 0.6 -> slot 2
            "ZZTEST Operations Coordinator",   # baseline 0.3 -> stays in the Icebox
        ])
    ]

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        repo.upsert_icebox(conn, user_id, postings)

        promoted = promote_top_n(conn, user_id, profile.ranking_weights, persona, wip_limit=2)
        assert len(promoted) == 2

        rows = conn.execute(
            """SELECT a.id, j.title, a.wip_status, a.status, a.thread_id, a.ranking_debug
               FROM application a JOIN job j ON j.id = a.job_id
               WHERE j.company = 'ZZQueueCo'""",
        ).fetchall()
        by_title = {r[1]: r for r in rows}
        pm, ba, ops = (by_title[f"ZZTEST {t}"]
                       for t in ("Product Manager", "Business Analyst", "Operations Coordinator"))
        # top-2 by rank queued, with thread_id = application id and a ranking snapshot
        for row in (pm, ba):
            assert (row[2], row[3]) == ("queued", "queued")
            assert row[4] == str(row[0])
            assert row[5] and "execution_priority" in row[5]
        assert (ops[2], ops[3]) == ("icebox", "sourced")
        assert str(pm[0]) == promoted[0]  # best-ranked got the first slot

        # audit: one actor='system' queued event per promotion
        n_events = conn.execute(
            """SELECT count(*) FROM application_event
               WHERE event_type = %s AND actor = 'system'
                 AND application_id::text = ANY(%s)""",
            (repo.EVENT_QUEUED, promoted),
        ).fetchone()[0]
        assert n_events == 2

        # a second cycle has zero headroom -> promotes nothing (never exceeds the limit)
        assert promote_top_n(conn, user_id, profile.ranking_weights, persona, wip_limit=2) == []

        # freeing a slot (closed posting) restores exactly one slot of headroom
        repo.mark_closed_before_execution(conn, promoted[0])
        again = promote_top_n(conn, user_id, profile.ranking_weights, persona, wip_limit=2)
        assert len(again) == 1 and str(ops[0]) == again[0]
    finally:
        conn.rollback()
        conn.close()


def test_execution_graph_checkpoint_resume_across_processes():
    """Kill/resume durability (#30): interrupt before the critic, then resume on a FRESH
    graph instance (new fakes — simulating a restarted worker). The generator must not
    run again; the run completes from the checkpoint."""
    import uuid

    import httpx

    from aeroapply.graph.checkpoint import postgres_checkpointer
    from aeroapply.graph.execution import build_execution_graph, initial_state
    from aeroapply.graph.state import OUTCOME_TAILORED

    class FakeModel:
        def __init__(self, replies):
            self.replies = list(replies)
            self.prompts = []

        def invoke(self, prompt):
            self.prompts.append(prompt)
            return type("Msg", (), {"content": self.replies.pop(0)})()

    variants = [{"id": "v1", "profile_name": "Core track - base", "role_focus": "Product Manager",
                 "raw_text": "BASE", "is_default": True}]
    app_row = {
        "application_id": f"zztest-{uuid.uuid4()}", "job_title": "Product Manager",
        "company": "ZZCkptCo", "job_description": "keywords", "job_location": "Remote",
        "portal_url": "https://boards.example.com/jobs/9", "portal_type": "greenhouse",
    }
    ok = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, text="open")))
    config = {"configurable": {"thread_id": app_row["application_id"]}}

    with postgres_checkpointer(os.environ["DATABASE_URL"]) as saver:
        # "process 1": runs verify -> select -> generate, then halts before the critic
        gen1, crit1 = FakeModel(["draft v1"]), FakeModel([])
        g1 = build_execution_graph(
            variants, model_factory=lambda n: gen1 if n == "tailor.generator" else crit1,
            http_client=ok, checkpointer=saver, interrupt_before=["critic"],
        )
        partial = g1.invoke(initial_state(app_row), config=config)
        assert partial["draft_resume_text"] == "draft v1" and crit1.prompts == []

        # "process 2": brand-new graph + fakes, same thread -> resumes FROM the checkpoint
        gen2 = FakeModel([])  # would raise if the generator re-ran
        crit2 = FakeModel(['{"ats_score": 0.95, "gaps": []}'])
        g2 = build_execution_graph(
            variants, model_factory=lambda n: gen2 if n == "tailor.generator" else crit2,
            http_client=ok, checkpointer=saver,
        )
        final = g2.invoke(None, config=config)

    assert final["outcome"] == OUTCOME_TAILORED
    assert final["ats_score"] == 0.95
    assert final["draft_resume_text"] == "draft v1"  # carried across the "restart"
    assert gen2.prompts == [] and len(crit2.prompts) == 1  # no re-spent generator tokens


# --- M2: resume embeddings + pgvector retrieval (#34) -------------------------------
def test_index_and_retrieve_resume_chunks_roundtrip():
    """Store chunks with embeddings, then cosine-retrieve: the chunk matching the query
    ranks first. Uses the deterministic HashEmbedder so order is reproducible in CI."""
    from aeroapply.config import load_profile
    from aeroapply.db import repo
    from aeroapply.embeddings import HashEmbedder

    profile = load_profile(EXAMPLE)
    embedder = HashEmbedder(dim=1536)  # matches the vector(1536) schema

    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        # a resume_variant to attach chunks to
        rv = conn.execute(
            """INSERT INTO resume_variant (user_id, profile_name, role_focus, raw_text)
               VALUES (%s, 'ZZTEST base', 'Product Manager', 'unused') RETURNING id""",
            (user_id,),
        ).fetchone()[0]

        chunks = [
            ("Skills", "python kubernetes airflow data pipelines"),
            ("Experience", "retail sales associate cashier customer service"),
            ("Summary", "product manager roadmap stakeholder analytics"),
        ]
        embeddings = embedder.embed([t for _s, t in chunks])
        n = repo.index_resume_chunks(conn, str(rv), chunks, embeddings)
        assert n == 3

        # query closest to the first chunk -> it ranks first
        q = embedder.embed(["python airflow data pipelines"])[0]
        hits = repo.retrieve_resume_chunks(conn, str(rv), q, k=3)
        assert len(hits) == 3
        assert hits[0][0] == "python kubernetes airflow data pipelines"
        assert hits[0][1] <= hits[1][1] <= hits[2][1]  # distances ascending

        # re-index is idempotent (delete-then-insert), not duplicative
        repo.index_resume_chunks(conn, str(rv), chunks, embeddings)
        count = conn.execute(
            "SELECT count(*) FROM resume_chunk WHERE resume_id = %s", (str(rv),)
        ).fetchone()[0]
        assert count == 3
    finally:
        conn.rollback()
        conn.close()


def test_work_path_grounds_generator_from_indexed_chunks():
    """End-to-end driver slice: index a resume, queue a real application, then
    run_application with a real DB-backed retriever (HashEmbedder) + fake models. Proves
    make_db_retriever wires retrieve_resume_chunks AND that the outcome persists — the
    retrieved chunk reaches the generator prompt and status flips to 'drafting'."""
    import httpx

    from aeroapply.config import load_profile
    from aeroapply.connectors.base import NormalizedPosting
    from aeroapply.db import repo
    from aeroapply.embeddings import HashEmbedder
    from aeroapply.graph.execution import make_db_retriever, run_application
    from aeroapply.graph.state import OUTCOME_TAILORED

    class FakeModel:
        def __init__(self, replies):
            self.replies, self.prompts = list(replies), []

        def invoke(self, prompt):
            self.prompts.append(prompt)
            return type("M", (), {"content": self.replies.pop(0)})()

    profile = load_profile(EXAMPLE)
    embedder = HashEmbedder(dim=1536)
    conn = repo.connect(os.environ["DATABASE_URL"])
    try:
        user_id = repo.ensure_operator(conn, profile)
        rv = conn.execute(
            """INSERT INTO resume_variant (user_id, profile_name, role_focus, raw_text)
               VALUES (%s, 'ZZTEST PM base', 'Product Manager', 'base') RETURNING id""",
            (user_id,),
        ).fetchone()[0]
        chunks = [("Experience", "shipped a machine learning roadmap for analytics")]
        repo.index_resume_chunks(conn, str(rv), chunks, embedder.embed([chunks[0][1]]))

        # a REAL job + application row (UUID id), so persist_outcome can UPDATE it
        posting = NormalizedPosting(
            source_key="greenhouse", external_id="zzwork1", company="ZZWorkCo",
            title="ZZTEST Product Manager", remote_mode="remote", location="Remote",
            description="machine learning analytics roadmap",
        )
        repo.upsert_icebox(conn, user_id, [posting])
        app_id = next(aid for aid, job, _ in repo.fetch_icebox(conn, user_id)
                      if job["title"] == "ZZTEST Product Manager")

        variants = [{"id": str(rv), "profile_name": "ZZTEST PM base",
                     "role_focus": "Product Manager", "raw_text": "base", "is_default": True}]
        app_row = {
            "application_id": app_id, "job_title": "Product Manager",
            "company": "ZZWorkCo", "job_description": "machine learning analytics roadmap",
            "job_location": "Remote", "portal_url": None, "portal_type": "greenhouse",
        }
        gen = FakeModel(["tailored draft"])
        crit = FakeModel(['{"ats_score": 0.95, "gaps": []}'])
        retriever = make_db_retriever(conn, embedder, k=3)

        final = run_application(
            conn, app_row, variants,
            model_factory=lambda n: gen if n == "tailor.generator" else crit,
            http_client=httpx.Client(transport=httpx.MockTransport(
                lambda r: httpx.Response(200, text="open"))),
            retriever=retriever,
        )

        assert final["outcome"] == OUTCOME_TAILORED
        assert "machine learning roadmap for analytics" in gen.prompts[0]
        assert "MOST-RELEVANT EXPERIENCE" in gen.prompts[0]
        # outcome persisted: status -> drafting, ats_score + tailored text stored
        row = conn.execute(
            "SELECT status, wip_status, ats_score, tailored_resume_text FROM application WHERE id = %s",
            (app_id,),
        ).fetchone()
        assert row[0] == "drafting" and row[1] == "active"
        assert float(row[2]) == 0.95 and row[3] == "tailored draft"
    finally:
        conn.rollback()
        conn.close()
