"""DB/migration integration test. Runs only when RUN_DB_TESTS is set (CI, or local
against the Docker container). Proves `alembic upgrade head` produced real pgvector
structures — not just that the Python imports.
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.getenv("RUN_DB_TESTS"),
    reason="set RUN_DB_TESTS=1 and DATABASE_URL to run DB integration tests",
)


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
