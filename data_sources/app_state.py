"""Team-shared app state (watchlist, alert thresholds, saved articles),
persisted to data/app_state.json in the repo via the same store as editorial
notes. Because the app has one shared login, this state is deliberately
team-level; per-person state arrives with OIDC identity. Session-only
fallback when no GITHUB_TOKEN is configured."""
from __future__ import annotations

import streamlit as st

from data_sources import notes_store

_PATH = "data/app_state.json"
_DEFAULT = {"watchlist": ["USD/ZAR", "Brent Crude", "Gold"],
            "alert_thresholds": None, "saved_articles": []}


def enabled() -> bool:
    return notes_store.enabled()


def ensure_loaded():
    """Pull shared state into the session once per session."""
    if st.session_state.get("_state_loaded"):
        return
    st.session_state["_state_loaded"] = True
    if not enabled():
        return
    try:
        obj, sha = notes_store.load_json(_PATH, dict(_DEFAULT))
        st.session_state["_state_sha"] = sha
        st.session_state["watchlist"] = obj.get("watchlist",
                                                _DEFAULT["watchlist"])
        st.session_state["saved_articles"] = obj.get("saved_articles", [])
        if obj.get("alert_thresholds"):
            st.session_state["alert_thresholds"] = {
                k: tuple(v) for k, v in obj["alert_thresholds"].items()}
    except Exception:
        pass  # session defaults stand; feed-status panel shows the store state


def persist(action: str):
    """Best-effort save of the shared trio; conflicts resolve by reload."""
    if not enabled():
        return
    obj = {"watchlist": st.session_state.get("watchlist", _DEFAULT["watchlist"]),
           "alert_thresholds": st.session_state.get("alert_thresholds"),
           "saved_articles": st.session_state.get("saved_articles", [])[:40]}
    try:
        st.session_state["_state_sha"] = notes_store.save_json(
            _PATH, obj, st.session_state.get("_state_sha"),
            st.session_state.get("note_author", ""), action)
    except notes_store.Conflict:
        st.session_state["_state_loaded"] = False
        ensure_loaded()
        st.toast("Shared settings changed elsewhere — reloaded latest.")
    except Exception:
        st.toast("Could not save shared settings (store unreachable).")
