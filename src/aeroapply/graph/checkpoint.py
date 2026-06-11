"""Postgres checkpointer wiring (#30).

`langgraph-checkpoint-postgres` persists every super-step, keyed by
`thread_id = application_id`, so a killed worker resumes mid-tailoring-loop without
re-spending Generator tokens. `setup()` creates the `checkpoints*` tables on first
use (the Alembic schema deliberately does NOT hand-write them — Brief §4).

Sync (`PostgresSaver` + `graph.invoke`) to match the repo's sync DAL; the async pool
migration is tracked under #14.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from langgraph.checkpoint.postgres import PostgresSaver


@contextmanager
def postgres_checkpointer(database_url: str) -> Iterator[PostgresSaver]:
    """Yield a ready PostgresSaver (tables created if missing)."""
    url = database_url.replace("postgresql+psycopg://", "postgresql://")
    with PostgresSaver.from_conn_string(url) as saver:
        saver.setup()
        yield saver


__all__ = ["postgres_checkpointer"]
