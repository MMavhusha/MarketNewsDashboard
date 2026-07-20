"""Audit trail for AI classification calls.

Every ACTUAL model invocation (cache hits never reach here) is recorded with
what was sent and what came back. Persisted to data/ai_audit.json via the
repo store when GITHUB_TOKEN is configured — each entry is then a git commit,
which makes the trail tamper-evident. Session-only fallback otherwise.
Capped to the most recent 500 entries. Recording is best-effort and never
interrupts classification.
"""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

from data_sources import notes_store

_PATH = "data/ai_audit.json"
_CAP = 500


def record(event: dict) -> None:
    event = {"when": datetime.now(ZoneInfo("Africa/Johannesburg")).strftime(
        "%Y-%m-%d %H:%M:%S SAST"), **event}
    try:
        if notes_store.enabled():
            log, sha = notes_store.load_json(_PATH, [])
            log.insert(0, event)
            notes_store.save_json(_PATH, log[:_CAP], sha,
                                  "app", "ai classification call")
        else:
            st.session_state.setdefault("_ai_audit", []).insert(0, event)
    except Exception:
        try:  # never let auditing break the app
            st.session_state.setdefault("_ai_audit", []).insert(0, event)
        except Exception:
            pass


def load() -> tuple[list, bool]:
    """(entries, durable). durable=False means session-only."""
    try:
        if notes_store.enabled():
            return notes_store.load_json(_PATH, [])[0], True
    except Exception:
        pass
    return st.session_state.get("_ai_audit", []), False
