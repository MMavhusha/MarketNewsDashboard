"""Economic calendar.

Primary (free, no key): Forex Factory public weekly JSON feeds
(cdn-nfs.faireconomy.media) — this week + next week; fields: title, country
(currency code), date, impact, forecast, previous. Covers major currencies
only (no ZAR/INR events).

Optional upgrade: TE_API_KEY in Streamlit Secrets switches to Trading
Economics for full country coverage incl. South Africa and India.

If nothing is reachable, the UI shows an explicit notice — never placeholder
events.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import requests
import streamlit as st

FF_FEEDS = [  # primary host + mirror, this week + next week
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
    "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://cdn-nfs.faireconomy.media/ff_calendar_nextweek.json",
]

_CCY_LABEL = {
    "USD": "United States", "EUR": "Euro Area", "GBP": "United Kingdom",
    "JPY": "Japan", "CNY": "China", "AUD": "Australia", "CAD": "Canada",
    "CHF": "Switzerland", "NZD": "New Zealand",
}

_TE_IMPORTANCE = {1: "Low", 2: "Medium", 3: "High"}

TE_WATCH = {"united states", "south africa", "euro area", "china", "india",
            "united kingdom", "japan", "germany", "france"}


def _te_key() -> str | None:
    try:
        return st.secrets.get("TE_API_KEY")
    except FileNotFoundError:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_forexfactory() -> list[dict]:
    out, seen = [], set()
    for url in FF_FEEDS:
        name = url.rsplit("/", 1)[-1]
        if name in seen:
            continue
        try:
            r = requests.get(url, timeout=12,
                             headers={"User-Agent": "Mozilla/5.0"})
            r.raise_for_status()
            seen.add(name)
            for x in r.json():
                when = x.get("date") or ""
                out.append({
                    "country": _CCY_LABEL.get(x.get("country"), x.get("country") or "—"),
                    "event": (x.get("title") or "").strip(),
                    "date": when[:16].replace("T", " "),
                    "_dt": when,
                    "expected": x.get("forecast") or "—",
                    "previous": x.get("previous") or "—",
                    "importance": (x.get("impact") or "Low").title(),
                    "source": "Forex Factory (public feed)",
                })
        except Exception:
            continue
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def _fetch_trading_economics(key: str, days_ahead: int) -> list[dict]:
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
            if country.lower() not in TE_WATCH:
                continue
            out.append({
                "country": country,
                "event": (x.get("Event") or "").strip(),
                "date": (x.get("Date") or "")[:16].replace("T", " "),
                "_dt": x.get("Date") or "",
                "expected": x.get("Forecast") or "—",
                "previous": x.get("Previous") or "—",
                "importance": _TE_IMPORTANCE.get(x.get("Importance"), "Low"),
                "source": x.get("Source") or "Trading Economics",
            })
        return out
    except Exception:
        return []


def get_calendar(days_ahead: int = 7) -> list[dict]:
    key = _te_key()
    rows = (_fetch_trading_economics(key, days_ahead) if key
            else _fetch_forexfactory())
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days_ahead)

    def keep(e):
        try:
            dt = datetime.fromisoformat(e["_dt"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return now - timedelta(hours=12) <= dt <= horizon
        except Exception:
            return True

    rows = [e for e in rows if keep(e)]
    rows.sort(key=lambda e: e["date"])
    return rows


def provider_label() -> str:
    return ("Trading Economics (full coverage)" if _te_key()
            else "Forex Factory public feed — majors only (USD, EUR, GBP, JPY, "
                 "CNY, AUD, CAD, CHF, NZD); SA/India events need a TE key")


def has_full_access() -> bool:
    return _te_key() is not None
