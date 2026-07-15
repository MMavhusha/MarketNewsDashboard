"""Economic calendar via Trading Economics API.

Uses TE_API_KEY from Streamlit Secrets when present; otherwise attempts the
public guest key (which covers only a sample country set). If neither yields
data, the UI shows an explicit configuration notice — never placeholder
events.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

_IMPORTANCE = {1: "Low", 2: "Medium", 3: "High"}

WATCH_COUNTRIES = {"united states", "south africa", "euro area", "china",
                   "india", "united kingdom", "japan", "germany", "france"}


def _api_key() -> str:
    try:
        return st.secrets.get("TE_API_KEY", "guest:guest")
    except FileNotFoundError:
        return "guest:guest"


@st.cache_data(ttl=3600, show_spinner=False)
def get_calendar(days_ahead: int = 7, _key: str = "") -> list[dict]:
    key = _key or _api_key()
    start = datetime.now(timezone.utc).date()
    end = start + timedelta(days=days_ahead)
    url = (f"https://api.tradingeconomics.com/calendar"
           f"?d1={start.isoformat()}&d2={end.isoformat()}&c={key}&format=json")
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        rows = r.json()
        if not isinstance(rows, list):
            return []
        out = []
        for x in rows:
            country = (x.get("Country") or "").strip()
            if key != "guest:guest" and country.lower() not in WATCH_COUNTRIES:
                continue
            out.append({
                "country": country,
                "event": (x.get("Event") or "").strip(),
                "date": (x.get("Date") or "")[:16].replace("T", " "),
                "expected": x.get("Forecast") or "—",
                "previous": x.get("Previous") or "—",
                "importance": _IMPORTANCE.get(x.get("Importance"), "Low"),
                "source": x.get("Source") or "Trading Economics",
            })
        out.sort(key=lambda e: e["date"])
        return out
    except Exception:
        return []


def has_full_access() -> bool:
    return _api_key() != "guest:guest"
