"""Unit test for human-curation event payloads (#80) — pure, no DB."""

from aeroapply.db import repo
from aeroapply.db.repo import _curation_payload


def test_promote_payload_label_and_present_flag_when_snapshotted():
    rd = {"components": {"title": 1.0}, "execution_priority": 0.67, "weights": {"title": 0.35}}
    payload = _curation_payload(repo.EVENT_PROMOTE, rd)
    assert payload == {
        "action": "promote", "label": "manual_override",
        "ranking_debug": rd, "ranking_debug_present": True,
    }


def test_drop_payload_flags_missing_snapshot():
    # A bare Kanban Drop with no prior `rank --persist` snapshot carries no features.
    payload = _curation_payload(repo.EVENT_DROP, None)
    assert payload == {
        "action": "drop", "label": "hard_negative",
        "ranking_debug": None, "ranking_debug_present": False,
    }
