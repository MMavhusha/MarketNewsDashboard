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
from zoneinfo import ZoneInfo

SAST = ZoneInfo('Africa/Johannesburg')

import requests
import streamlit as st

# this week + next week. No mirror host exists — cdn-nfs.faireconomy.media
# does not resolve; nextweek here 404s upstream until FF publishes it (seen
# to lag until Fri/weekend), which feed_status() reports as partial coverage
# rather than failure.
FF_FEEDS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",
]

_CCY_LABEL = {
    "USD": "United States", "EUR": "Euro Area", "GBP": "United Kingdom",
    "JPY": "Japan", "CNY": "China", "AUD": "Australia", "CAD": "Canada",
    "CHF": "Switzerland", "NZD": "New Zealand",
}

# The regions this dashboard covers. Events outside these are never shipped
# to the calendar — a SA PM does not need Australian or Swiss data prints.
OUR_REGIONS = {"South Africa", "United States", "Euro Area",
               "United Kingdom", "China", "India", "Japan"}

# Exchange calendars (pandas-market-calendars) per region — fully automatic,
# no manual upkeep. XJSE = Johannesburg; covers all SA public holidays.
_EXCHANGE_CAL = {
    "South Africa": ("XJSE", "JSE"), "United States": ("NYSE", "NYSE"),
    "Euro Area": ("XETR", "Xetra"), "United Kingdom": ("LSE", "LSE"),
    "China": ("XSHG", "Shanghai SE"), "India": ("NSE", "NSE"),
    "Japan": ("XTKS", "Tokyo SE"),
}



def _nice(dt_iso: str) -> tuple[str, str]:
    """(day header 'Mon 14 Jul', time '22:00 SAST') from an ISO string."""
    try:
        dt = datetime.fromisoformat(dt_iso.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        loc = dt.astimezone(SAST)
        return loc.strftime("%a %d %b"), loc.strftime("%H:%M SAST")
    except Exception:
        return dt_iso[:10], dt_iso[11:16]

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
    from data_sources import obs
    for url in FF_FEEDS:
        name = url.rsplit("/", 1)[-1]
        if name in seen:
            continue
        try:
            with obs.track(f"Forex Factory · {name}"):
                r = requests.get(url, timeout=12,
                                 headers={"User-Agent": "Mozilla/5.0"})
                r.raise_for_status()
                payload = r.json()
            seen.add(name)
            for x in payload:
                when = x.get("date") or ""
                day, tm = _nice(when)
                out.append({
                    "country": _CCY_LABEL.get(x.get("country"), x.get("country") or "—"),
                    "event": (x.get("title") or "").strip(),
                    "date": when[:16].replace("T", " "),
                    "day": day, "time": tm,
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
            day, tm = _nice(x.get("Date") or "")
            out.append({
                "country": country,
                "event": (x.get("Event") or "").strip(),
                "date": (x.get("Date") or "")[:16].replace("T", " "),
                "day": day, "time": tm,
                "_dt": x.get("Date") or "",
                "expected": x.get("Forecast") or "—",
                "previous": x.get("Previous") or "—",
                "importance": _TE_IMPORTANCE.get(x.get("Importance"), "Low"),
                "source": x.get("Source") or "Trading Economics",
            })
        return out
    except Exception:
        return []


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _market_holidays(days_ahead: int) -> list[dict]:
    """Market closures across all covered regions, as calendar rows. Fully
    automatic via pandas-market-calendars — no keys, no manual dates. A
    closure is a weekday in range with no trading session on that exchange."""
    try:
        import pandas as pd
        import pandas_market_calendars as mcal
    except Exception:
        return []
    start = datetime.now(SAST).date()
    end = start + timedelta(days=days_ahead)
    out = []
    for region, (code, venue) in _EXCHANGE_CAL.items():
        try:
            cal = mcal.get_calendar(code)
            sched = cal.schedule(start_date=start.isoformat(),
                                 end_date=end.isoformat())
            trading = set(sched.index.date)
            for d in pd.bdate_range(start, end):
                if d.date() not in trading:
                    name = ""
                    try:  # label the holiday where the calendar names it
                        h = cal.holidays().holidays
                        name = str(h.get(pd.Timestamp(d.date()), "") or "")
                    except Exception:
                        pass
                    iso = f"{d.date().isoformat()}T00:00:00+02:00"
                    out.append({
                        "country": region,
                        "event": f"{venue} closed" + (f" — {name}" if name else ""),
                        "date": d.date().isoformat() + " 00:00",
                        "day": d.strftime("%a %d %b"), "time": "—",
                        "_dt": iso, "expected": "—", "previous": "—",
                        "importance": "High",  # a closed market halts execution
                        "is_holiday": True,
                        "source": "pandas-market-calendars",
                    })
        except Exception:
            continue
    return out


def get_calendar(days_ahead: int = 7) -> list[dict]:
    key = _te_key()
    rows = (_fetch_trading_economics(key, days_ahead) if key
            else _fetch_forexfactory())
    rows = rows + _curated_za() + _market_holidays(days_ahead)
    # Ship ONLY our covered regions — no Australian/Canadian/Swiss/NZ prints.
    rows = [e for e in rows if e.get("country") in OUR_REGIONS]
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=days_ahead)

    def keep(e):
        try:
            dt = datetime.fromisoformat(e["_dt"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if e.get("is_holiday"):  # all-day fact: keep today-or-future
                return now.date() <= dt.date() <= horizon.date()
            return now - timedelta(hours=12) <= dt <= horizon
        except Exception:
            return True

    rows = [e for e in rows if keep(e)]
    rows.sort(key=lambda e: e["date"])
    return rows


def provider_label() -> str:
    base = ("Trading Economics (full coverage)" if _te_key()
            else "Forex Factory public feed — major-currency data releases")
    return (base + " · market holidays for all covered regions via "
            "pandas-market-calendars · filtered to SA, US, Euro Area, UK, "
            "China, India, Japan")


def has_full_access() -> bool:
    return _te_key() is not None


def feed_status() -> dict:
    rows = _fetch_forexfactory()
    now = datetime.now(timezone.utc)
    has_next_week = False
    for e in rows:
        try:
            dt = datetime.fromisoformat(e["_dt"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt - now > timedelta(days=6):
                has_next_week = True
                break
        except Exception:
            continue
    span = "this + next week" if has_next_week else "this week only — next week feed not yet published upstream"
    level = "error" if not rows else ("ok" if has_next_week else "warn")
    return {"name": "Forex Factory calendar", "ok": bool(rows), "level": level,
            "detail": f"{len(rows)} events ({span})"}


def _curated_za() -> list[dict]:
    """Team-curated SA events (SARB MPC, Stats SA releases) from
    data/za_calendar.json in the repo — the app never invents dates.
    Format: [{"date": "2026-07-23T15:00:00+02:00", "country": "South Africa",
              "event": "SARB MPC rate decision", "importance": "High",
              "source": "SARB (curated)"}]"""
    import json as _json
    from pathlib import Path
    f = Path(__file__).resolve().parents[1] / "data" / "za_calendar.json"
    try:
        rows = _json.loads(f.read_text())
    except Exception:
        return []
    out = []
    for x in rows:
        when = x.get("date", "")
        day, tm = _nice(when)
        out.append({"country": x.get("country", "South Africa"),
                    "event": x.get("event", ""), "date": when[:16].replace("T", " "),
                    "day": day, "time": tm, "_dt": when,
                    "expected": x.get("expected", "—"),
                    "previous": x.get("previous", "—"),
                    "importance": x.get("importance", "High"),
                    "source": x.get("source", "RisCura curated")})
    return out
