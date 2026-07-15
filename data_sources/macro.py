"""Regional macro data.

Free tier: World Bank Open Data API (no key) for cross-country comparison of
GDP growth, inflation and unemployment (annual). Central-bank policy rates,
PMI and 10Y yields require a keyed/premium provider (Trading Economics,
central bank feeds, Bloomberg) — the registry below maps each indicator to
its target premium source per the product spec, so upgrading is a drop-in.
"""
from __future__ import annotations

import requests
import streamlit as st

REGIONS = {
    "South Africa": "ZAF",
    "United States": "USA",
    "Euro Area": "EMU",
    "United Kingdom": "GBR",
    "China": "CHN",
    "India": "IND",
}

WB_INDICATORS = {
    "GDP Growth (YoY %)": "NY.GDP.MKTP.KD.ZG",
    "Inflation, CPI (YoY %)": "FP.CPI.TOTL.ZG",
    "Unemployment Rate (%)": "SL.UEM.TOTL.ZS",
}

# Indicator -> (free source now, target premium source)
PROVIDER_REGISTRY = {
    "GDP Growth (YoY %)": ("World Bank / IMF WEO", "IMF / Trading Economics"),
    "Inflation, CPI (YoY %)": ("World Bank + SARB Web API (SA)", "Trading Economics / national stats"),
    "Unemployment Rate (%)": ("World Bank / ILO", "Trading Economics / national stats"),
    "Policy Rate (%)": ("SARB Web API (SA, live) — other regions key required", "Central bank releases (Fed, ECB, SARB, BoE, PBoC, RBI)"),
    "Manufacturing PMI": ("— key required —", "Trading Economics / S&P Global"),
    "10Y Government Yield (%)": ("— key required —", "Trading Economics / Bloomberg"),
    "FX vs USD": ("yfinance", "RiscFlash / Bloomberg"),
    "Commodities": ("yfinance", "RiscFlash / Bloomberg"),
    "News": ("Public RSS (Reuters/CNBC/MarketWatch/Moneyweb)", "Bloomberg / Reuters / J.P. Morgan research"),
}

REGION_FX = {
    "South Africa": ("USD/ZAR", "USDZAR=X"),
    "United States": ("DXY Index", "DX-Y.NYB"),
    "Euro Area": ("EUR/USD", "EURUSD=X"),
    "United Kingdom": ("GBP/USD", "GBPUSD=X"),
    "China": ("USD/CNY", "USDCNY=X"),
    "India": ("USD/INR", "USDINR=X"),
}


@st.cache_data(ttl=86400, show_spinner=False)
def wb_series(country: str, indicator: str, years: int = 12) -> list[tuple[int, float]]:
    """Returns [(year, value)] ascending; [] on failure."""
    url = (f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
           f"?format=json&per_page={years}")
    try:
        r = requests.get(url, timeout=12)
        r.raise_for_status()
        payload = r.json()
        rows = payload[1] if isinstance(payload, list) and len(payload) > 1 else []
        out = [(int(x["date"]), float(x["value"])) for x in (rows or [])
               if x.get("value") is not None]
        return sorted(out)
    except Exception:
        return []


@st.cache_data(ttl=86400, show_spinner=False)
def wb_latest_matrix() -> dict:
    """{indicator: {region: (year, value)}} — latest available per country."""
    matrix: dict = {}
    for ind_label, code in WB_INDICATORS.items():
        matrix[ind_label] = {}
        for region, iso in REGIONS.items():
            series = wb_series(iso, code)
            matrix[ind_label][region] = series[-1] if series else None
    return matrix


# ---------------------------------------------------------- SA BoP context
# Qualitative mapping of South Africa's main trade exposures (structural,
# well-documented composition of SA trade: PGMs, gold, coal, iron ore as key
# exports; crude oil as the dominant commodity import). Displayed alongside
# live prices — the price moves are data; the exposure mapping is context.
SA_BOP_EXPOSURES = [
    ("Platinum", "PL=F", "Export", "PGMs are among SA's largest export earners; higher prices support the trade balance."),
    ("Gold", "GC=F", "Export", "A major export; rallies typically improve export receipts and support the rand."),
    ("Coal", "MTF=F", "Export", "Key bulk export (Richards Bay); price strength lifts export revenue."),
    ("Iron Ore", "TIO=F", "Export", "Significant bulk export; sensitive to Chinese steel demand."),
    ("Copper", "HG=F", "Export", "Smaller direct exposure but a bellwether for the broader resource basket."),
    ("Brent Crude Oil", "BZ=F", "Import", "SA imports nearly all crude; higher Brent widens the import bill and pressures the current account."),
]
