"""AeroApply CLI. Read-only sourcing + the Streamlit Kanban-lite are wired up
(`source`, `rank`, `ui`); there is no apply/submit/credential path — by design for
this stage.

Every command accepts `--profile PATH` to run against an alternate operator profile
(e.g. the fictional test personas in `config/profiles/`); the default is the
gitignored `config/profile.yaml` (overridable via the PROFILE_PATH env var)."""

from __future__ import annotations

import argparse


def _resolve_profile(args: argparse.Namespace):
    """The profile precedence: --profile flag > PROFILE_PATH env > config/profile.yaml."""
    from aeroapply.config import get_profile, load_profile

    if getattr(args, "profile", None):
        return load_profile(args.profile)
    return get_profile()


def _cmd_source(args: argparse.Namespace) -> None:
    from aeroapply.config import get_settings
    from aeroapply.connectors.registry import get_connector
    from aeroapply.db import repo
    from aeroapply.sourcing.bouncer import SourcingBouncer
    from aeroapply.sourcing.geocoding import build_default_geocoder
    from aeroapply.sourcing.ingest import plan_ingest

    settings = get_settings()
    profile = _resolve_profile(args)
    connector = get_connector("greenhouse", board_token=args.board, company=args.company)
    bouncer = SourcingBouncer(profile.to_bouncer_config(), geocoder=build_default_geocoder())
    plan = plan_ingest(connector.fetch(), bouncer)
    with repo.connect(settings.database_url) as conn:
        user_id = repo.ensure_operator(conn, profile)
        counts = repo.upsert_icebox(conn, user_id, plan.survivors)
    print(f"fetched={plan.fetched} kept={plan.kept} deduped_in_batch={plan.deduped_in_batch}")
    print(f"dropped={plan.dropped}")
    print(
        f"jobs_inserted={counts.jobs_inserted} apps_inserted={counts.applications_inserted} "
        f"apps_deduped={counts.deduped}"
    )


def _cmd_rank(args: argparse.Namespace) -> None:
    from aeroapply.config import get_settings
    from aeroapply.db import repo
    from aeroapply.sourcing.ranking import RankingPersona
    from aeroapply.sourcing.scheduler import rank_icebox, snapshot_ranking_debug

    settings = get_settings()
    profile = _resolve_profile(args)
    persona = RankingPersona.from_profile(profile)
    with repo.connect(settings.database_url) as conn:
        user_id = repo.ensure_operator(conn, profile)
        if args.persist:
            # The with-block commits on exit (like _cmd_source).
            ranked = snapshot_ranking_debug(conn, user_id, profile.ranking_weights, persona)
        else:
            ranked = rank_icebox(conn, user_id, profile.ranking_weights, persona)
    for app_id, scored in ranked[: args.limit]:
        print(f"{scored.execution_priority:6.3f}  {app_id}  {scored.components}")
    print(f"({len(ranked)} icebox jobs)")
    if args.persist:
        print(f"persisted ranking_debug for {len(ranked)} icebox rows")


def _cmd_schedule(args: argparse.Namespace) -> None:
    from aeroapply.config import get_settings
    from aeroapply.db import repo
    from aeroapply.sourcing.ranking import RankingPersona
    from aeroapply.sourcing.scheduler import promote_top_n

    settings = get_settings()
    profile = _resolve_profile(args)
    persona = RankingPersona.from_profile(profile)
    with repo.connect(settings.database_url) as conn:
        user_id = repo.ensure_operator(conn, profile)
        promoted = promote_top_n(
            conn, user_id, profile.ranking_weights, persona,
            wip_limit=profile.scheduler.wip_limit,
        )
        in_flight = repo.count_in_flight(conn, user_id)
    for app_id in promoted:
        print(f"queued {app_id}")
    print(f"promoted={len(promoted)} in_flight={in_flight} wip_limit={profile.scheduler.wip_limit}")


def _cmd_index(args: argparse.Namespace) -> None:
    from aeroapply.config import get_settings
    from aeroapply.db import repo
    from aeroapply.embeddings import build_default_embedder, chunk_resume, validate_dim

    settings = get_settings()
    profile = _resolve_profile(args)
    embedder = build_default_embedder(settings.embedding_model, settings.embedding_dim)
    validate_dim(embedder, settings.embedding_dim)
    with repo.connect(settings.database_url) as conn:
        user_id = repo.ensure_operator(conn, profile)
        variants = repo.fetch_resume_variants(conn, user_id)
        if not variants:
            print("no resume_variant rows — load a base resume first")
            return
        total = 0
        for v in variants:
            chunks = chunk_resume(v["raw_text"])
            if not chunks:
                continue
            embeddings = embedder.embed([text for _section, text in chunks])
            n = repo.index_resume_chunks(conn, v["id"], chunks, embeddings)
            total += n
            print(f"indexed {n:3d} chunks  {v['profile_name']}")
    print(f"done: {total} chunks across {len(variants)} variant(s)")


def _cmd_work(args: argparse.Namespace) -> None:
    from aeroapply.config import get_settings
    from aeroapply.db import repo
    from aeroapply.embeddings import build_default_embedder, validate_dim
    from aeroapply.graph.checkpoint import postgres_checkpointer
    from aeroapply.graph.execution import make_db_retriever, run_application

    settings = get_settings()
    profile = _resolve_profile(args)
    with repo.connect(settings.database_url) as conn:
        user_id = repo.ensure_operator(conn, profile)
        app_row = repo.fetch_next_queued(conn, user_id)
        if app_row is None:
            print("queue is empty — run `aeroapply schedule` first")
            return
        variants = repo.fetch_resume_variants(conn, user_id)
        retriever = None
        if not args.no_retrieval:
            embedder = build_default_embedder(settings.embedding_model, settings.embedding_dim)
            validate_dim(embedder, settings.embedding_dim)
            retriever = make_db_retriever(conn, embedder)
        with postgres_checkpointer(settings.database_url) as saver:
            final = run_application(
                conn, app_row, variants,
                retriever=retriever,
                checkpointer=saver,
                ats_threshold=settings.min_ats_score,
                max_iterations=settings.max_tailor_iterations,
            )
    print(
        f"{app_row['application_id']}  outcome={final.get('outcome')} "
        f"ats_score={final.get('ats_score')} iterations={final.get('iterations')}"
    )


def _cmd_ui(args: argparse.Namespace) -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    page = Path(__file__).parent / "ui" / "kanban.py"
    env = os.environ.copy()
    if getattr(args, "profile", None):
        env["PROFILE_PATH"] = args.profile  # Settings.profile_path picks this up
    subprocess.run([sys.executable, "-m", "streamlit", "run", str(page)], check=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(prog="aeroapply", description="AeroApply daemon CLI")
    sub = parser.add_subparsers(dest="command")

    def add_profile_arg(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--profile",
            default=None,
            metavar="PATH",
            help="operator profile YAML (default config/profile.yaml; "
            "test personas live in config/profiles/)",
        )

    p_source = sub.add_parser("source", help="read-only ingest a Greenhouse board into the Icebox")
    p_source.add_argument("--board", required=True, help="Greenhouse board token (company slug)")
    p_source.add_argument("--company", default=None, help="display name (defaults to the token)")
    add_profile_arg(p_source)
    p_source.set_defaults(func=_cmd_source)

    p_rank = sub.add_parser("rank", help="print the Python-ranked Icebox")
    p_rank.add_argument("--limit", type=int, default=20)
    p_rank.add_argument("--persist", action="store_true",
                        help="snapshot ranking_debug for the Icebox (writes); default is read-only")
    add_profile_arg(p_rank)
    p_rank.set_defaults(func=_cmd_rank)

    p_sched = sub.add_parser(
        "schedule", help="one WIP-scheduler cycle: promote top-N Icebox jobs to the queue"
    )
    add_profile_arg(p_sched)
    p_sched.set_defaults(func=_cmd_schedule)

    p_index = sub.add_parser(
        "index", help="chunk + embed the operator's resume variants into resume_chunk (#34)"
    )
    add_profile_arg(p_index)
    p_index.set_defaults(func=_cmd_index)

    p_work = sub.add_parser(
        "work",
        help="run the next queued application through the graph (needs model API keys)",
    )
    p_work.add_argument("--no-retrieval", action="store_true",
                        help="skip resume-chunk grounding (use the full base resume)")
    add_profile_arg(p_work)
    p_work.set_defaults(func=_cmd_work)

    p_ui = sub.add_parser("ui", help="launch the Streamlit Kanban-lite over the Icebox")
    add_profile_arg(p_ui)
    p_ui.set_defaults(func=_cmd_ui)

    args = parser.parse_args()
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return
    func(args)


if __name__ == "__main__":
    main()
