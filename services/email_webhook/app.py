"""AeroApply inbound-email webhook service (FastAPI, deploy on Railway).

Two jobs:
  1. SYNCHRONOUS: an OTP/verification arrives while a Playwright thread is paused
     at a portal signup/login -> inject the code and resume the graph.
  2. ASYNCHRONOUS: a lifecycle email (interview/rejection/offer/questionnaire)
     arrives days later -> update application.status and forward to the operator.

Corrections vs. the common reference snippet:
  * `aupdate_state` is a method on the COMPILED GRAPH, not on the checkpointer.
  * Mailgun inbound posts MULTIPART FORM fields, not a JSON body -> parse with
    `await request.form()`.
  * SMTP forwarding runs in a BackgroundTask so the webhook returns 200 fast.

This is a STARTER. `get_graph()` and the classifier are wired to real
implementations in the execution-graph package; here they are clearly marked.

See: docs/LIFECYCLE_AND_EMAIL.md
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
from email.message import EmailMessage

import aiosmtplib
from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

app = FastAPI(title="AeroApply Inbound Email Service")

MAILGUN_SIGNING_KEY = os.environ.get("MAILGUN_SIGNING_KEY", "")
PRIMARY_EMAIL = os.environ.get("PRIMARY_EMAIL", "you@example.com")
AGENT_EMAIL = os.environ.get("AGENT_EMAIL", "you.agents@example.com")

OTP_RE = re.compile(r"\b\d{4,7}\b")
LIFECYCLE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("interview", ("interview", "schedule a call", "meet with", "availability")),
    ("questionnaire", ("assessment", "questionnaire", "skills test", "survey", "coding challenge")),
    ("offer", ("offer", "compensation package", "contract", "we'd like to extend")),
    ("rejection", ("unfortunately", "not moving forward", "other candidates",
                   "will not be proceeding")),
]
HIGH_PRIORITY = {"interview", "offer", "questionnaire"}


def verify_mailgun_signature(timestamp: str, token: str, signature: str) -> bool:
    digest = hmac.new(
        MAILGUN_SIGNING_KEY.encode(), (timestamp + token).encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(signature, digest)


def classify(subject: str, body: str) -> str | None:
    """Fast keyword classifier (starter).

    Production: route (subject, body) to the `email.classifier` node via the
    ModelRouter (local Llama / Haiku, structured output) for robust labeling.
    """
    text = f"{subject}\n{body}".lower()
    for label, keywords in LIFECYCLE_RULES:
        if any(k in text for k in keywords):
            return label
    return None


async def forward_to_primary(subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = AGENT_EMAIL
    msg["To"] = PRIMARY_EMAIL
    msg["Subject"] = f"[AeroApply] {subject}"
    msg.set_content(body)
    try:
        await aiosmtplib.send(
            msg,
            hostname=os.getenv("SMTP_HOST", "smtp.mailgun.org"),
            port=int(os.getenv("SMTP_PORT", "587")),
            username=os.getenv("SMTP_USER"),
            password=os.getenv("SMTP_PASSWORD"),
            start_tls=True,
        )
    except Exception as exc:  # pragma: no cover - best effort
        print(f"forward failed: {exc}")


# --- wiring stubs (implemented in src/aeroapply) --------------------------
async def get_graph():  # pragma: no cover - TODO
    """Return the compiled LangGraph app bound to the AsyncPostgresSaver."""
    raise NotImplementedError("wire to aeroapply.graph.build_execution_graph()")


async def match_application_by_domain(domain: str):  # pragma: no cover - TODO
    """Return (application_id, status, portal_type) for the active app on `domain`."""
    raise NotImplementedError("wire to aeroapply.db")


async def update_status(application_id: str, new_status: str) -> None:  # pragma: no cover - TODO
    raise NotImplementedError("wire to aeroapply.db")


@app.post("/v1/webhooks/inbound-email", status_code=200)
async def inbound_email(request: Request, background: BackgroundTasks) -> dict:
    form = await request.form()  # Mailgun posts multipart form fields, not JSON
    timestamp = str(form.get("timestamp", ""))
    token = str(form.get("token", ""))
    signature = str(form.get("signature", ""))
    if not verify_mailgun_signature(timestamp, token, signature):
        raise HTTPException(status_code=401, detail="invalid webhook signature")

    sender = str(form.get("sender", ""))
    subject = str(form.get("subject", ""))
    body = str(form.get("stripped-text") or form.get("body-plain") or "")
    domain = sender.split("@")[-1].lower() if "@" in sender else ""

    match = await match_application_by_domain(domain)
    if not match:
        return {"status": "ignored", "reason": "no active application for domain"}
    application_id, status, _portal_type = match
    config = {"configurable": {"thread_id": application_id}}

    # CASE A — OTP injection while the agent is mid-signup/login.
    otp = OTP_RE.search(f"{subject} {body}")
    if otp and status in {"submitting", "drafting"}:
        graph = await get_graph()
        await graph.aupdate_state(
            config,
            {"verification_code": otp.group(0)},
            as_node="account_node",  # attribute the edit to the account/credential node
        )
        return {"status": "ok", "action": "otp_injected", "thread_id": application_id}

    # CASE B — lifecycle status update.
    label = classify(subject, body)
    if label:
        await update_status(application_id, label)
        if label in HIGH_PRIORITY:
            background.add_task(forward_to_primary, subject, body)
        return {"status": "ok", "action": "status_updated", "new_status": label}

    return {"status": "ok", "action": "none"}
