"""Streamlit Kanban-lite over the Icebox — read + Promote/Drop curation only.

Launched by `aeroapply ui`. Reads the Python-ranked Icebox (`ui.board.build_board` over
`ranking.rank_jobs` / `profile.ranking_weights`). Before each curation action it snapshots
that card's `ranking_debug` (so the label is paired with its ranker features), then writes
the human curation event via `db.repo` (Promote -> manual_override; Drop -> user_rejected).
There is deliberately NO submit / apply / credential code here. Spec: docs/UI_UX.md section 2.3.

A fresh connection is opened per Streamlit rerun (the script re-runs top-to-bottom on
every widget interaction); the DB / ranking remain the source of truth, so closing the
browser loses nothing.
"""

from __future__ import annotations

import psycopg
import streamlit as st

from aeroapply.config import RankingWeights, get_profile, get_settings
from aeroapply.db import repo
from aeroapply.ui.board import BoardRow, build_board, snapshot_row


def _render_card(conn: psycopg.Connection, row: BoardRow, weights: RankingWeights) -> None:
    comp = row.components
    with st.container(border=True):
        st.markdown(f"### {row.title or '(untitled role)'}")
        meta = " · ".join(p for p in (row.company, row.location, row.remote_mode) if p)
        st.caption(meta or "—")
        badge = " &nbsp; 🔝 **promoted**" if row.manual_override else ""
        st.markdown(f"**priority {row.execution_priority:.3f}**{badge}")
        st.caption(
            f"title {comp.get('title', 0):.2f} · location {comp.get('location', 0):.2f} · "
            f"recency {comp.get('recency', 0):.2f} · "
            f"competition {comp.get('competition', 0):.2f} · "
            f"urgency {comp.get('urgency', 0):.2f}"
        )
        promote_col, drop_col = st.columns(2)
        if promote_col.button(
            "Promote",
            key=f"promote-{row.application_id}",
            disabled=row.manual_override,
            use_container_width=True,
        ):
            snapshot_row(conn, row, weights)
            repo.promote(conn, row.application_id)
            conn.commit()
            st.rerun()
        if drop_col.button(
            "Drop",
            key=f"drop-{row.application_id}",
            use_container_width=True,
        ):
            snapshot_row(conn, row, weights)
            repo.drop(conn, row.application_id)
            conn.commit()
            st.rerun()


def main() -> None:
    st.set_page_config(page_title="AeroApply — Icebox", layout="wide")
    st.title("Icebox — Python-ranked backlog")
    st.caption(
        "Ordered by ranking.rank_jobs over profile.ranking_weights. "
        "Promote = manual_override (+100 trump); Drop = user_rejected."
    )

    settings = get_settings()
    profile = get_profile()
    conn = repo.connect(settings.database_url)
    try:
        user_id = repo.ensure_operator(conn, profile)
        conn.commit()
        board = build_board(conn, user_id, profile.ranking_weights)
        if not board:
            st.info("Icebox is empty — run `aeroapply source --board <token>` to fill it.")
            return
        st.write(f"**{len(board)}** job(s) in the Icebox")
        for row in board:
            _render_card(conn, row, profile.ranking_weights)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
