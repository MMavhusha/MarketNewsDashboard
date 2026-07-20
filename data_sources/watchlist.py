"""Keyword watchlist model and matching.

A watched keyword is a standing, per-user alert: {term, scope} where scope is
'news', 'calendar' or 'both'. Adding one surfaces matching content as an alert
on Calendar & Alerts (alongside the auto shock alerts), with live match counts
and deep links into the exact Market News / calendar view. Persisted across
logins via app_state until removed.

Stored under session key 'news_watch_keywords'. Backward-compatible: legacy
entries were plain strings (implicitly scope 'both'); normalize() upgrades them
transparently so existing saved lists keep working.
"""
from __future__ import annotations

import streamlit as st

from data_sources import news

SCOPES = ("both", "news", "calendar")
_KEY = "news_watch_keywords"


def normalize(raw) -> list[dict]:
    """Coerce the stored list (strings or dicts, mixed) to [{term, scope}]."""
    out = []
    for item in raw or []:
        if isinstance(item, str):
            term = item.strip()
            if term:
                out.append({"term": term, "scope": "both"})
        elif isinstance(item, dict) and item.get("term"):
            scope = item.get("scope", "both")
            out.append({"term": str(item["term"]).strip(),
                        "scope": scope if scope in SCOPES else "both"})
    # de-dupe by lowercased term, keeping first
    seen, uniq = set(), []
    for k in out:
        low = k["term"].lower()
        if low not in seen:
            seen.add(low)
            uniq.append(k)
    return uniq


def get() -> list[dict]:
    return normalize(st.session_state.get(_KEY, []))


def set_list(keywords: list[dict]) -> None:
    st.session_state[_KEY] = keywords


def terms() -> list[str]:
    """Plain term strings — for the existing news/calendar flag matchers."""
    return [k["term"] for k in get()]


def news_terms() -> list[str]:
    """Terms that watch news (scope 'news' or 'both'). Use everywhere a news
    surface flags/filters, so the scope rule lives in one place."""
    return [k["term"] for k in get() if k["scope"] in ("both", "news")]


def calendar_terms() -> list[str]:
    """Terms that watch the calendar (scope 'calendar' or 'both')."""
    return [k["term"] for k in get() if k["scope"] in ("both", "calendar")]


def matches_news(item: dict, term: str) -> bool:
    return news.fuzzy_match(term, f'{item.get("title", "")} {item.get("summary", "")}')


def matches_event(e: dict, term: str) -> bool:
    return news.fuzzy_match(term, f'{e.get("event", "")} {e.get("country", "")}')


def news_matches(term: str, items: list[dict]) -> list[dict]:
    return [i for i in items if matches_news(i, term)]


def calendar_matches(term: str, events: list[dict]) -> list[dict]:
    return [e for e in events if matches_event(e, term)]
