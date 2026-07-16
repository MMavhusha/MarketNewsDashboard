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
}


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
    if not enabled() or series_key not in SERIES:
        return None
    sid, label = SERIES[series_key]
    try:
        r = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={"series_id": sid, "api_key": _key(), "file_type": "json",
                    "sort_order": "desc", "limit": 5},
            timeout=15)
        r.raise_for_status()
        for obs in r.json().get("observations", []):
            if obs.get("value") not in (".", "", None):
                return {"value": f"{float(obs['value']):,.2f}",
                        "date": obs.get("date", ""), "label": label}
    except Exception:
        return None
    return None


def feed_status() -> dict:
    if not enabled():
        return {"name": "FRED (US/EA rates)", "ok": False,
                "detail": "off — add FRED_API_KEY (free) to enable"}
    probe = latest("us_policy")
    return {"name": "FRED (US/EA rates)", "ok": probe is not None,
            "detail": (f"Fed funds {probe['value']} · {probe['date']}"
                       if probe else "key set but API unreachable")}
