"""Cross-page instrument alert state.

Answers one question for any page that shows an instrument: does this
instrument currently have an active alert, and of what kind? Two sources:

  * shock alerts  — an instrument breached a price threshold (markets)
  * watchlist     — a keyword the team added matches this instrument's name

Pages call `for_instrument(name)` and render a small badge + click-through to
the Alerts page. This keeps ONE alert state surfaced everywhere the instrument
appears, rather than duplicating alert cards onto every page.
"""
from __future__ import annotations

import streamlit as st


def _shock_by_instrument() -> dict[str, str]:
    """{instrument name: highest severity} from active, non-dismissed shock
    alerts. Cached per rerun via session to avoid refetching per instrument."""
    cache = st.session_state.get("_alert_shock_map")
    if cache is not None:
        return cache
    out: dict[str, str] = {}
    try:
        from data_sources import markets
        dismissed = st.session_state.get("dismissed_alerts", set())
        rank = {"Critical": 2, "Warning": 1}
        for a in markets.get_shock_alerts():
            if a["title"] in dismissed:
                continue
            name, sev = a.get("assets", ""), a.get("severity", "Warning")
            if name and rank.get(sev, 0) >= rank.get(out.get(name, ""), 0):
                out[name] = sev
    except Exception:
        pass
    st.session_state["_alert_shock_map"] = out
    return out


def for_instrument(name: str) -> dict | None:
    """Active alert state for an instrument, or None. Shape:
    {'shock': 'Critical'|'Warning'|None, 'watch': [terms], 'label': str}."""
    if not name:
        return None
    shock = _shock_by_instrument().get(name)
    watch_terms = []
    try:
        from data_sources import watchlist as wl, news
        for term in wl.terms():
            # a watchlist keyword covers this instrument if it fuzzy-matches
            # the instrument's display name (e.g. 'Gold' -> Gold, 'zar'->USD/ZAR)
            if news.fuzzy_match(term, name):
                watch_terms.append(term)
    except Exception:
        pass
    if not shock and not watch_terms:
        return None
    parts = []
    if shock:
        parts.append(f"{shock} shock alert")
    if watch_terms:
        parts.append("on watchlist")
    return {"shock": shock, "watch": watch_terms, "label": " · ".join(parts)}


def clear_cache() -> None:
    st.session_state.pop("_alert_shock_map", None)
