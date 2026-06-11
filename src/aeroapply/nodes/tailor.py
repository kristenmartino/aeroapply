"""The Generator <-> ATS-Critic cyclic tailoring loop (#35-#37) — the runtime peer review.

Generator (drafting class, `tailor.generator`) rewrites the base resume against the
job description; the ATS-Critic (critique class, `tailor.critic`, temperature 0)
scores keyword coverage 0..1 and lists gaps. `critic_route` loops `revise` until the
score clears the threshold or the max-iteration cap fires — the cap is the cost
circuit-breaker the roadmap requires asserting in tests.

Honesty guard (Brief §13.1): the Generator prompt forbids inventing employers,
titles, dates, degrees, certifications, or skills not present in the base resume —
tailoring rephrases and reorders truth, it never manufactures it.

Models are injected as a factory `node_name -> chat model` (default: the
ModelRouter), so unit tests run with deterministic fakes and zero API keys.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from aeroapply.graph.state import OUTCOME_TAILORED, ExecutionState, NodeFn

ModelFactory = Callable[[str], Any]  # node name -> chat model with .invoke() -> .content

DEFAULT_ATS_THRESHOLD = 0.90
DEFAULT_MAX_ITERATIONS = 4  # cost circuit-breaker: hard cap on Generator calls per app

GENERATOR_PROMPT = """\
You are tailoring a resume for a specific job posting.

NON-NEGOTIABLE HONESTY RULES:
- Never invent employers, job titles, dates, degrees, certifications, tools, or skills
  that are not in the base resume. You may rephrase, reorder, emphasize, and quantify
  only what is already there.
- If the job asks for something the base resume does not support, leave it unaddressed.

JOB TITLE: {job_title}
COMPANY: {company}
JOB DESCRIPTION:
{job_description}

BASE RESUME:
{resume_text}

{gaps_section}
Rewrite the resume to maximize legitimate ATS keyword coverage for this posting.
Return ONLY the full tailored resume text, no commentary."""

CRITIC_PROMPT = """\
You are a strict ATS keyword-coverage critic. Compare the tailored resume to the job
description and score coverage of the posting's important keywords/skills.

JOB DESCRIPTION:
{job_description}

TAILORED RESUME:
{draft}

Respond with ONLY a JSON object, no prose:
{{"ats_score": <float 0.0-1.0>, "gaps": ["<missing keyword or weakly-covered area>", ...]}}"""


def _content(response: Any) -> str:
    """Normalize a chat-model response (AIMessage or str) to text."""
    content = getattr(response, "content", response)
    if isinstance(content, list):  # some providers return content blocks
        content = " ".join(
            c.get("text", "") if isinstance(c, dict) else str(c) for c in content
        )
    return str(content)


def parse_critic_response(text: str) -> tuple[float, list[str]]:
    """Extract (ats_score, gaps) from the critic's reply; resilient to stray prose.

    Unparseable output scores 0.0 with a diagnostic gap — the loop then revises (or the
    cap fires); it must never crash the graph or loop forever on a malformed reply.
    """
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            score = max(0.0, min(1.0, float(data.get("ats_score", 0.0))))
            gaps = [str(g) for g in data.get("gaps", []) if str(g).strip()]
            return score, gaps
        except (ValueError, TypeError):
            pass
    return 0.0, [f"critic returned unparseable output: {text[:200]!r}"]


def make_generate(model_factory: ModelFactory) -> NodeFn:
    def generate(state: ExecutionState) -> dict[str, Any]:
        gaps = state.get("critic_gaps") or []
        gaps_section = (
            "PREVIOUS CRITIC FEEDBACK — address these gaps truthfully:\n- "
            + "\n- ".join(gaps) + "\n\n"
            if gaps
            else ""
        )
        prompt = GENERATOR_PROMPT.format(
            job_title=state.get("job_title", ""),
            company=state.get("company", ""),
            job_description=state.get("job_description", ""),
            resume_text=state.get("resume_text", ""),
            gaps_section=gaps_section,
        )
        draft = _content(model_factory("tailor.generator").invoke(prompt))
        return {
            "draft_resume_text": draft,
            "iterations": int(state.get("iterations", 0)) + 1,
        }

    return generate


def make_critic(model_factory: ModelFactory) -> NodeFn:
    def critic(state: ExecutionState) -> dict[str, Any]:
        prompt = CRITIC_PROMPT.format(
            job_description=state.get("job_description", ""),
            draft=state.get("draft_resume_text", ""),
        )
        score, gaps = parse_critic_response(
            _content(model_factory("tailor.critic").invoke(prompt))
        )
        return {"ats_score": score, "critic_gaps": gaps}

    return critic


def critic_route(state: ExecutionState) -> str:
    """'accept' on threshold or cap, else 'revise' — the loop's only exit conditions."""
    threshold = float(state.get("ats_threshold", DEFAULT_ATS_THRESHOLD))
    cap = int(state.get("max_iterations", DEFAULT_MAX_ITERATIONS))
    if float(state.get("ats_score", 0.0)) >= threshold:
        return "accept"
    if int(state.get("iterations", 0)) >= cap:
        return "accept"  # cap fired: keep the best effort; quality gate judges it later
    return "revise"


def finalize(state: ExecutionState) -> dict[str, Any]:
    """Terminal bookkeeping after the critic accepts (threshold or cap)."""
    return {"outcome": OUTCOME_TAILORED}


__all__ = [
    "ModelFactory",
    "make_generate",
    "make_critic",
    "critic_route",
    "finalize",
    "parse_critic_response",
    "DEFAULT_ATS_THRESHOLD",
    "DEFAULT_MAX_ITERATIONS",
    "GENERATOR_PROMPT",
    "CRITIC_PROMPT",
]
