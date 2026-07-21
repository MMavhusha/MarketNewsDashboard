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
    "Japan": "JPN",
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
    "Japan": ("USD/JPY", "USDJPY=X"),
}


@st.cache_data(ttl=86400, show_spinner=False)
def wb_series(country: str, indicator: str, years: int = 12) -> list[tuple[int, float]]:
    """Returns [(year, value)] ascending; [] on failure."""
    url = (f"https://api.worldbank.org/v2/country/{country}/indicator/{indicator}"
           f"?format=json&per_page={years}")
    from data_sources import obs
    try:
        with obs.track(f"World Bank · {country}/{indicator}"):
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
# Structural mapping of South Africa's main commodity trade exposures. The
# price moves shown alongside are LIVE data; everything here is well-documented
# structural context. The `share` strings are INDICATIVE magnitudes from
# published SARS/SARB trade composition (there is no free per-commodity BoP
# API — these are approximate, for interpretation only, not live figures).
# Fields: (name, ticker, side, role_note, share_note, effect_up)
#   effect_up = what a PRICE RISE does to SA's external position.
SA_BOP_EXPOSURES = [
    ("Platinum", "PL=F", "Export",
     "PGMs (platinum, palladium, rhodium) are among SA's largest merchandise export earners.",
     "PGM group \u2248 12-18% of merchandise exports (indicative, SARS composition)",
     "improves the trade surplus and tends to support the rand"),
    ("Gold", "GC=F", "Export",
     "A major export; SA is a significant producer and gold rallies lift export receipts.",
     "Gold \u2248 12-16% of merchandise exports (indicative)",
     "raises export receipts, supporting the current account and the rand"),
    ("Coal", "MTF=F", "Export",
     "Key bulk export shipped mainly via Richards Bay Coal Terminal.",
     "Coal \u2248 4-7% of merchandise exports (indicative)",
     "lifts bulk export revenue, a modest current-account positive"),
    ("Iron Ore", "TIO=F", "Export",
     "Significant bulk export; earnings are highly sensitive to Chinese steel demand.",
     "Iron ore \u2248 4-6% of merchandise exports (indicative)",
     "increases export revenue; a China-demand-driven price fall does the reverse"),
    ("Copper", "HG=F", "Export",
     "Smaller direct SA export, but a bellwether for the broader resource basket and risk appetite.",
     "Small direct share; read as a resource-sector signal",
     "signals resource-sector strength; limited direct BoP effect on its own"),
    ("Brent Crude Oil", "BZ=F", "Import",
     "SA imports nearly all of its crude oil, so oil is the dominant commodity IMPORT.",
     "Crude + refined petroleum among the largest single import lines (indicative)",
     "widens the import bill, pressuring the trade balance and the current account"),
]


# Signature commodity per region, as paired in the reference macro pack
# (Japan–Iron Ore, SA–Gold, Eurozone–Brent, US–WTI, China–Copper). UK and
# India are not paired in the pack: assigned by market convention (UK→Brent
# North Sea benchmark; India→Gold, largest consumer market).
REGION_COMMODITY = {
    "South Africa": ("Gold Spot (COMEX proxy)", "GC=F", "$/oz", 1.0),
    "United States": ("WTI Crude Oil", "CL=F", "$/bbl", 1.0),
    "Euro Area": ("Brent Crude Oil", "BZ=F", "$/bbl", 1.0),
    "United Kingdom": ("Brent Crude Oil", "BZ=F", "$/bbl", 1.0),
    "China": ("Copper (COMEX conv., $/t)", "HG=F", "$/tonne", 2204.62),
    "India": ("Gold Spot (COMEX proxy)", "GC=F", "$/oz", 1.0),
    "Japan": ("Iron Ore 62% Fe CFR (CME TSI)", "TIO=F", "$/tonne", 1.0),
}

# 10Y government bond per region, as in the pack's yields tab. Only series
# with a free reliable source are charted; the rest name their target source.
REGION_10Y = {
    "United States": ("US 10Y Treasury", "^TNX", 0.1, "CBOE via yfinance"),
    "Euro Area": ("Germany 10Y Bund", None, None, "Trading Economics / ECB (key)"),
    "United Kingdom": ("UK 10Y Gilt", None, None, "Trading Economics / BoE (key)"),
    "China": ("China 10Y CGB", None, None, "Trading Economics (key)"),
    "India": ("India 10Y G-Sec", None, None, "Trading Economics (key)"),
    "Japan": ("Japan 10Y JGB", None, None, "Trading Economics (key)"),
    "South Africa": ("SA 10Y benchmark", "SARB_LATEST", None,
                     "SARB latest yield · history needs a key source"),
}

# Policy rate & CPI YoY 3-year monthly histories, charted per region in the
# reference pack. Only series with a free reliable source are charted (FRED,
# key present); the rest name their target source — no estimation, ever.
# Entry: (chart label, fred history key or None, yoy transform?, source note)
REGION_POLICY_HIST = {
    "United States": ("Central Bank Policy Rate (%)", "us_policy", False,
                      "Fed funds effective, monthly · FRED"),
    "Euro Area": ("Central Bank Policy Rate (%)", "ea_policy", False,
                  "ECB deposit facility, monthly · FRED"),
    "South Africa": ("Central Bank Policy Rate (%)", None, False,
                     "latest live above (SARB) · history: Trading Economics (key)"),
    "United Kingdom": ("Central Bank Policy Rate (%)", None, False,
                       "BoE Bank Rate · Trading Economics (key)"),
    "China": ("Central Bank Policy Rate (%)", None, False,
              "PBoC LPR · Trading Economics (key)"),
    "India": ("Central Bank Policy Rate (%)", None, False,
              "RBI repo · Trading Economics (key)"),
    "Japan": ("Central Bank Policy Rate (%)", None, False,
              "BoJ policy rate · Trading Economics (key)"),
}
REGION_CPI_HIST = {
    "United States": ("Annual Inflation Rate — CPI YoY (%)", "us_cpi_index", True,
                      "YoY computed from published BLS CPI-U index · FRED"),
    "Euro Area": ("Annual Inflation Rate — HICP YoY (%)", "ea_hicp_index", True,
                  "YoY computed from published Eurostat HICP index · FRED"),
    "South Africa": ("Annual Inflation Rate — CPI YoY (%)", None, True,
                     "latest monthly above (SARB) · history: Stats SA / Trading Economics (key)"),
    "United Kingdom": ("Annual Inflation Rate — CPI YoY (%)", None, True,
                       "ONS · Trading Economics (key)"),
    "China": ("Annual Inflation Rate — CPI YoY (%)", None, True,
              "NBS · Trading Economics (key)"),
    "India": ("Annual Inflation Rate — CPI YoY (%)", None, True,
              "MOSPI · Trading Economics (key)"),
    "Japan": ("Annual Inflation Rate — CPI YoY (%)", None, True,
              "Statistics Bureau of Japan · Trading Economics (key)"),
}
