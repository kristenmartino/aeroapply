"""verify_open (#32) — the execution graph's FIRST node, the stale-queue guard.

HTTP-pings the posting's `portal_url` before any frontier token is spent. A dead
posting (404/410, or a closed-marker phrase in the body) routes the application to
`closed_before_execution` and the scheduler pulls the next job (Brief §5.1).

Failure posture: network errors and ambiguous responses treat the posting as OPEN —
wasting one drafting run is cheaper than silently skipping a live role. Only positive
evidence of closure closes it.
"""

from __future__ import annotations

import re
from typing import Any

import httpx

from aeroapply.graph.state import OUTCOME_CLOSED, ExecutionState, NodeFn

# Phrases ATS job pages render once a posting is gone (checked case-insensitively).
CLOSED_MARKERS = re.compile(
    r"(no longer accepting applications|job is no longer available|"
    r"position has been filled|posting has closed|this job has closed)",
    re.IGNORECASE,
)
CLOSED_STATUS = {404, 410}

def make_verify_open(client: httpx.Client | None = None, *, timeout: float = 10.0) -> NodeFn:
    """Build the node. Pass an `httpx.Client` (e.g. MockTransport in tests) to inject IO."""

    def verify_open(state: ExecutionState) -> dict[str, Any]:
        url = state.get("portal_url")
        if not url:
            # Nothing to verify — proceed; the submit path will face reality later.
            return {"verify_status_code": None}
        http = client or httpx.Client(follow_redirects=True, timeout=timeout)
        owns_client = client is None
        try:
            resp = http.get(url)
        except httpx.HTTPError as exc:
            # Transient network trouble is NOT evidence of closure.
            return {"verify_status_code": None, "debug": {"verify_open_error": str(exc)}}
        finally:
            if owns_client:
                http.close()
        if resp.status_code in CLOSED_STATUS or CLOSED_MARKERS.search(resp.text or ""):
            return {"verify_status_code": resp.status_code, "outcome": OUTCOME_CLOSED}
        return {"verify_status_code": resp.status_code}

    return verify_open


__all__ = ["make_verify_open", "CLOSED_MARKERS", "CLOSED_STATUS"]
