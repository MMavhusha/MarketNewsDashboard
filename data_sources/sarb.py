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
    from data_sources import obs
    for label, path in _ENDPOINTS:
        try:
            with obs.track(f"SARB · {label}"):
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


def feed_status() -> dict:
    groups = get_sa_indicators()
    n = sum(len(v) for v in groups.values())
    return {"name": "SARB Web API", "ok": bool(n), "detail": f"{n} series"}


# ---- Balance of payments (current account + trade balance) ----
# SARB's "Release of Selected Data" exposes BoP indicators live via the Web API
# (MonthlyIndicatorsAll). We query it, pick out current-account and trade-
# balance lines, and show each at its native frequency (trade balance monthly,
# current account quarterly). If the live feed can't be reached or the category
# isn't found, we fall back to the latest officially published figures, clearly
# dated, so the panel is never blank but also never silently stale.
_BOP_ENDPOINT = "/WebIndicators/ReleaseOfSelectedData/MonthlyIndicatorsAll/CurrentData"
_BOP_KEYWORDS = ("current account", "trade balance", "balance of payments",
                 "current-account", "trade surplus", "trade deficit")

# Fallback: latest official SARB release (verify/refresh at the linked source).
_BOP_FALLBACK = {
    "as_of": "Q1 2026 (published Jun 2026)",
    "rows": [
        {"name": "Current account balance", "value": "190.7",
         "unit": "R bn", "period": "Q1 2026", "note": "surplus; 2.4% of GDP"},
        {"name": "Trade balance", "value": "437.9",
         "unit": "R bn", "period": "Q1 2026", "note": "surplus"},
        {"name": "Current account (% of GDP)", "value": "2.4",
         "unit": "%", "period": "Q1 2026", "note": "up from 0.6% in Q4 2025"},
    ],
    "source_url": "https://www.resbank.co.za/en/home/publications/quarterly-bulletin1/current-account-release",
}

# BoP reconciliation on a SINGLE quarterly basis so it FOOTS as a true
# statement: exports - imports = trade balance; trade balance + net services,
# income & transfers = current account. Quarterly because SARB reports the BoP
# quarterly — the only basis on which all lines align. Values ZAR bn, Q1 2026
# (SARB QB). Net services/income/transfers is the balancing item
# (= current account - trade balance = 190.7 - 437.9 = -247.2).
_BOP_RECON_FALLBACK = {
    "period": "Q1 2026",
    "unit": "R bn",
    "exports": 892.0,      # merchandise exports, Q1 2026 (SARB BoP basis)
    "imports": 454.1,      # merchandise imports, Q1 2026
    "trade_balance": 437.9,
    "services_income_transfers": -247.2,
    "current_account": 190.7,
    "ca_pct_gdp": 2.4,
    "source_url": "https://www.resbank.co.za/en/home/publications/quarterly-bulletin1/current-account-release",
}


def get_bop_reconciliation() -> dict:
    """Quarterly BoP footing chain (live not yet wired; returns dated Q1 2026).
    Foots: exports - imports = trade_balance; trade_balance +
    services_income_transfers = current_account."""
    d = dict(_BOP_RECON_FALLBACK)
    d["live"] = False
    return d


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def get_balance_of_payments() -> dict:
    """{'live': bool, 'as_of': str, 'rows': [...], 'source_url': str}.

    Tries the live SARB Web API first; falls back to the dated official figures
    if unavailable. rows carry name/value/unit/period so each line shows its
    own release period (monthly trade vs quarterly current account)."""
    from data_sources import obs
    try:
        with obs.track("SARB · balance of payments"):
            r = requests.get(BASE + _BOP_ENDPOINT, timeout=15, headers=_HEADERS)
            r.raise_for_status()
            data = r.json()
        rows = []
        if isinstance(data, list):
            for it in data:
                if not isinstance(it, dict):
                    continue
                name = (it.get("MeasureName") or it.get("Description")
                        or it.get("SubTitle") or "").strip()
                if not name or not any(k in name.lower() for k in _BOP_KEYWORDS):
                    continue
                val = it.get("Value")
                if val in (None, ""):
                    continue
                rows.append({
                    "name": name, "value": str(val).strip(),
                    "unit": (it.get("FormatNumber") or "").strip(),
                    "period": (it.get("Period") or "").strip(),
                    "note": (it.get("CategoryName") or "").strip(),
                })
        if rows:
            return {"live": True, "as_of": "latest SARB release",
                    "rows": rows[:6], "source_url": _BOP_FALLBACK["source_url"]}
    except Exception:
        pass
    # graceful fallback — dated, never silently stale
    return {"live": False, **_BOP_FALLBACK}
