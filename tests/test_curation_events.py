"""Unit test for human-curation event payloads (#80) — pure, no DB."""

from aeroapply.db import repo
from aeroapply.db.repo import _curation_payload


def test_promote_payload_label_and_ranking_debug_passthrough():
    rd = {"components": {"title": 1.0}, "execution_priority": 0.67, "weights": {"title": 0.35}}
    payload = _curation_payload(repo.EVENT_PROMOTE, rd)
    assert payload == {"action": "promote", "label": "manual_override", "ranking_debug": rd}


def test_drop_payload_label_and_none_ranking_debug():
    payload = _curation_payload(repo.EVENT_DROP, None)
    assert payload == {"action": "drop", "label": "hard_negative", "ranking_debug": None}
