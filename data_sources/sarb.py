"""South African Reserve Bank public Web API (free, no key).

Base: https://custom.resbank.co.za/SarbWebApi/
Used endpoints (JSON): home-page rates (repo, prime, CPI/PPI, FX) and the
Economic & Financial Data for SA (SDDS) sections. Field names vary across
endpoints, so parsing is tolerant. All values displayed with SARB attribution
and their published value dates — no derivation.
"""
from __future__ import annotations

import requests
import streamlit as st

BASE = "https://custom.resbank.co.za/SarbWebApi"

_ENDPOINTS = [
    ("Key rates & prices", "/WebIndicators/HomePageRates"),
    ("Market rates", "/WebIndicators/CurrentMarketRates"),
    ("Prices (SDDS)", "/WebIndicators/EconFinDataForSA/GetPricesData"),
    ("Real sector (SDDS)", "/WebIndicators/EconFinDataForSA/GetRealSectorData"),
]

_HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def _row(item: dict) -> dict | None:
    name = (item.get("Name") or item.get("MeasureName")
            or item.get("PageTitle") or "").strip()
    value = item.get("Value", item.get("TheValue"))
    if not name or value in (None, ""):
        return None
    date = (item.get("Date") or item.get("ValueDate")
            or item.get("LastPeriod") or "")
    return {
        "name": name,
        "value": value,
        "date": str(date)[:10],
        "unit": (item.get("UnitOfMeasure") or "").strip(),
        "agency": (item.get("PublishingAgency") or "SARB").strip() or "SARB",
        "section": (item.get("SectionName") or "").strip(),
    }


@st.cache_data(ttl=3600, show_spinner=False)
def get_sa_indicators() -> dict[str, list[dict]]:
    """{group label: [rows]} — only groups that returned data."""
    out: dict[str, list[dict]] = {}
    for label, path in _ENDPOINTS:
        try:
            r = requests.get(BASE + path, timeout=15, headers=_HEADERS)
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, list):
                continue
            rows = [x for x in (_row(i) for i in data if isinstance(i, dict)) if x]
            if rows:
                out[label] = rows[:14]
        except Exception:
            continue
    return out
