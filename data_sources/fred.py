"""FRED (St. Louis Fed) — free API key, 120 requests/minute.

Fills tiles that yfinance/SARB/World Bank cannot, using stable Fed/ECB-sourced
series only (many OECD-sourced international series were discontinued on FRED
in 2024, so UK/EA yields are deliberately NOT sourced here). Activates when
FRED_API_KEY is present in Streamlit Secrets; otherwise callers fall back to
their named pending source. Macro series are cached for 6 hours — the manual
Refresh button does not clear them, so even heavy refreshing uses a handful of
calls per day against the 120/min limit.
"""
from __future__ import annotations

import os

import requests
import streamlit as st

# Deliberately conservative series map: native Fed/ECB releases only.
SERIES = {
    "us_policy": ("DFF", "Fed funds (effective) · FRED"),
    "us_10y": ("DGS10", "US 10Y constant maturity · FRED"),
    "ea_policy": ("ECBDFR", "ECB deposit facility rate · FRED"),
    "us_cpi_index": ("CPIAUCSL", "US CPI-U index · BLS via FRED"),
    "us_unemp": ("UNRATE", "US unemployment rate (U-3) · BLS via FRED"),
    "ea_hicp_index": ("CP0000EZ19M086NEST", "EA HICP index · Eurostat via FRED"),
}

# OECD "Main Economic Indicators" international 10Y government bond yields
# (monthly). Some OECD-sourced FRED series were discontinued in 2024, so these
# are accessed ONLY through latest_fresh()/history() with a staleness guard:
# if the newest observation is older than the freshness window, we return None
# (honest blank) rather than a stale value. Verify live before trusting.
SERIES_INTL_10Y = {
    "cn_10y": ("IRLTLT01CNM156N", "China 10Y govt bond · OECD MEI via FRED"),
    "uk_10y": ("IRLTLT01GBM156N", "UK 10Y govt bond · OECD MEI via FRED"),
    "jp_10y": ("IRLTLT01JPM156N", "Japan 10Y govt bond · OECD MEI via FRED"),
    "in_10y": ("IRLTLT01INM156N", "India 10Y govt bond · OECD MEI via FRED"),
    "za_10y": ("IRLTLT01ZAM156N", "South Africa 10Y govt bond · OECD MEI via FRED"),
}
_ALL_SERIES = {**SERIES, **SERIES_INTL_10Y}

# US Treasury constant-maturity (CMT) par yield curve, full tenor set, daily,
# sourced by FRED from the Fed H.15 release (same figures Treasury publishes).
# Ordered short → long so the curve plots left-to-right.
US_CURVE = [
    ("1M", "DGS1MO"), ("3M", "DGS3MO"), ("6M", "DGS6MO"),
    ("1Y", "DGS1"), ("2Y", "DGS2"), ("3Y", "DGS3"), ("5Y", "DGS5"),
    ("7Y", "DGS7"), ("10Y", "DGS10"), ("20Y", "DGS20"), ("30Y", "DGS30"),
]


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def us_yield_curve() -> list[dict] | None:
    """Latest par yield per tenor: [{'tenor','years','yield','date'}], short→long.
    One FRED call per tenor (cached 6h). Returns None if FRED is off; skips any
    tenor that fails so a partial curve still renders."""
    if not enabled():
        return None
    _TEN_YEARS = {"1M": 1/12, "3M": 0.25, "6M": 0.5, "1Y": 1, "2Y": 2,
                  "3Y": 3, "5Y": 5, "7Y": 7, "10Y": 10, "20Y": 20, "30Y": 30}
    out = []
    for tenor, sid in US_CURVE:
        try:
            r = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": sid, "api_key": _key(),
                        "file_type": "json", "sort_order": "desc", "limit": 5},
                timeout=15)
            r.raise_for_status()
            for obs in r.json().get("observations", []):
                if obs.get("value") not in (".", "", None):
                    out.append({"tenor": tenor, "years": _TEN_YEARS[tenor],
                                "yield": float(obs["value"]),
                                "date": obs.get("date", "")})
                    break
        except Exception:
            continue
    return out or None


def _key() -> str:
    try:
        v = st.secrets.get("FRED_API_KEY")
        if v:
            return v
    except FileNotFoundError:
        pass
    return os.environ.get("FRED_API_KEY", "")


def enabled() -> bool:
    return bool(_key())


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def latest(series_key: str) -> dict | None:
    """{'value': str, 'date': str, 'label': str} or None."""
    if not enabled() or series_key not in _ALL_SERIES:
        return None
    sid, label = _ALL_SERIES[series_key]
    from data_sources import obs as _obs
    try:
        with _obs.track(f"FRED · {label}"):
            r = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": sid, "api_key": _key(), "file_type": "json",
                        "sort_order": "desc", "limit": 5},
                timeout=15)
            r.raise_for_status()
            rows = r.json().get("observations", [])
        for obs in rows:
            if obs.get("value") not in (".", "", None):
                return {"value": f"{float(obs['value']):,.2f}",
                        "date": obs.get("date", ""), "label": label}
    except Exception:
        return None
    return None


def latest_fresh(series_key: str, max_age_days: int = 120) -> dict | None:
    """Like latest(), but returns None if the newest observation is older than
    max_age_days. This is the ONLY safe way to read the OECD international
    series: several were discontinued on FRED in 2024, and a discontinued
    series still returns its last (stale) value — worse than an honest blank.
    Monthly series lag ~6-8 weeks, so 120 days tolerates a normal publication
    gap while still catching a series that has genuinely stopped updating.
    """
    row = latest(series_key)
    if not row or not row.get("date"):
        return None
    try:
        import datetime as _dt
        obs_date = _dt.date.fromisoformat(row["date"])
        if (_dt.date.today() - obs_date).days > max_age_days:
            return None  # stale → treat as unavailable
    except Exception:
        return None
    return row


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def history(series_key: str, years: int = 3, yoy: bool = False):
    """Monthly pd.Series over `years`, or None on failure/no key.

    yoy=True converts a *published* index into YoY % change — pure arithmetic
    on official observations (labelled at the call site), never estimation.
    """
    if not enabled() or series_key not in SERIES:
        return None
    import datetime as dt

    import pandas as pd
    sid, _ = SERIES[series_key]
    from data_sources import obs as _obs
    lookback = int((years + (1 if yoy else 0)) * 365.25) + 45
    start = dt.date.today() - dt.timedelta(days=lookback)
    try:
        with _obs.track(f"FRED history · {sid}"):
            r = requests.get(
                "https://api.stlouisfed.org/fred/series/observations",
                params={"series_id": sid, "api_key": _key(), "file_type": "json",
                        "observation_start": start.isoformat()},
                timeout=20)
            r.raise_for_status()
            payload = r.json().get("observations", [])
        obs = {pd.Timestamp(o["date"]): float(o["value"])
               for o in payload
               if o.get("value") not in (".", "", None)}
        if not obs:
            return None
        s = pd.Series(obs).sort_index()
        s = s.resample("MS").last().dropna()  # monthly cadence, as in the pack
        if yoy:
            s = (s.pct_change(12, fill_method=None) * 100).dropna()
        s = s[s.index >= pd.Timestamp.today() - pd.DateOffset(years=years)]
        return s if len(s) > 2 else None
    except Exception:
        return None


def feed_status() -> dict:
    if not enabled():
        return {"name": "FRED (US/EA rates)", "ok": False,
                "detail": "off — add FRED_API_KEY (free) to enable"}
    probe = latest("us_policy")
    return {"name": "FRED (US/EA rates)", "ok": probe is not None,
            "detail": (f"Fed funds {probe['value']} · {probe['date']}"
                       if probe else "key set but API unreachable")}
