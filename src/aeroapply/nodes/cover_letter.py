"""cover_letter (#38) — draft a cover letter when the operator opts in.

Runs after the tailoring loop, so it can ground the letter in the *tailored* résumé and
the job. Model is injected (node `cover_letter` → drafting class via the router), so it's
unit-tested with fakes and no API key. When disabled (operator preference `never`, or the
driver passes `enabled=False`) the node is a pass-through — no tokens spent.

Honesty (Brief §13.1): the prompt forbids inventing experience, employers, titles, or
skills not in the tailored résumé — the letter reframes truth, it never manufactures it.
"""

from __future__ import annotations

from typing import Any

from aeroapply.graph.state import ExecutionState, NodeFn
from aeroapply.nodes.tailor import ModelFactory, _content

COVER_LETTER_PROMPT = """\
Write a concise, specific cover letter (3-4 short paragraphs) for this job, grounded
ONLY in the candidate's tailored résumé below.

NON-NEGOTIABLE HONESTY RULES:
- Never claim experience, employers, titles, tools, or skills not present in the résumé.
- No clichés or filler; reference concrete, résumé-supported accomplishments.

JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION:
{job_description}

CANDIDATE'S TAILORED RÉSUMÉ:
{resume}

Return ONLY the cover letter text, no salutation placeholders like [Hiring Manager]."""


def make_cover_letter(model_factory: ModelFactory, *, enabled: bool) -> NodeFn:
    """Build the node. `enabled=False` makes it a no-op pass-through (no model call)."""

    def cover_letter(state: ExecutionState) -> dict[str, Any]:
        if not enabled:
            return {}
        prompt = COVER_LETTER_PROMPT.format(
            job_title=state.get("job_title", ""),
            company=state.get("company", ""),
            job_description=state.get("job_description", ""),
            resume=state.get("draft_resume_text") or state.get("resume_text", ""),
        )
        text = _content(model_factory("cover_letter").invoke(prompt))
        return {"cover_letter": text}

    return cover_letter


__all__ = ["make_cover_letter", "COVER_LETTER_PROMPT"]
