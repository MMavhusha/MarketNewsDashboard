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

# Central bank per region + official statistics/release site. Only SARB exposes
# a rich free API (surfaced live below); for the others we link to the source
# rather than fabricate an equivalent feed — their headline series already
# appear in the metric tabs above.
CENTRAL_BANKS = {
    "South Africa": ("South African Reserve Bank (SARB)", "https://www.resbank.co.za"),
    "United States": ("US Federal Reserve", "https://www.federalreserve.gov/data.htm"),
    "Euro Area": ("European Central Bank (ECB)", "https://data.ecb.europa.eu"),
    "United Kingdom": ("Bank of England", "https://www.bankofengland.co.uk/statistics"),
    "China": ("People's Bank of China (PBoC)", "http://www.pbc.gov.cn/en/3688006/index.html"),
    "India": ("Reserve Bank of India (RBI)", "https://www.rbi.org.in/Scripts/Statistics.aspx"),
    "Japan": ("Bank of Japan (BOJ)", "https://www.boj.or.jp/en/statistics/index.htm"),
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
# Structural mapping of South Africa's main commodity trade exposures. Price
# moves shown alongside are LIVE; the trade values here are REAL published
# figures from the OEC 2024 SA trade profile (oec.world), cross-checked against
# World Bank WITS commodity-chapter data. They are ANNUAL, VALUE-BASED (USD).
# There is no free per-commodity, per-period API — customs data is monthly PDF
# only — but shares change slowly, so an annual structural figure is the right
# tool for "is this big enough to move the BoP".
#
# We store the commodity's trade value and the relevant total, and DERIVE the
# percentage from them at render time, so the displayed share always reconciles
# with the two values the user can see (value / total = %). This makes the
# figure self-checking rather than a separate number that could drift.
#
# SA_TRADE_TOTALS_2024: denominators (USD bn, OEC 2024 / WITS).
SA_TRADE_TOTALS_2024 = {"exports": 151.0, "imports": 107.0}
# Fields: (name, ticker, side, role_note, value_usd_bn, value_label, band)
#   value_usd_bn = None where only a chapter-level figure exists (shown as text).
SA_BOP_EXPOSURES = [
    ("Platinum", "PL=F", "Export",
     "PGMs (platinum, palladium, rhodium) — SA supplies the majority of world PGM output.",
     15.8, "platinum line; PGM group larger", "Major"),
    ("Gold", "GC=F", "Export",
     "SA's single largest export line by value; a major source of foreign receipts.",
     29.0, None, "Major"),
    ("Coal", "MTF=F", "Export",
     "Key bulk export via Richards Bay; MTF=F tracks API2 (Rotterdam) as a "
     "liquid free proxy — SA coal prices nearer API4/Richards Bay.",
     7.75, None, "Moderate"),
    ("Iron Ore", "TIO=F", "Export",
     "Significant bulk export; earnings highly sensitive to Chinese steel demand.",
     6.69, None, "Moderate"),
    ("Copper", "HG=F", "Export",
     "Not a top-10 SA export line; read as a resource-sector / risk-appetite bellwether.",
     None, "not a top-10 export line (<$1.5bn)", "Minor"),
    ("Brent Crude Oil", "BZ=F", "Import",
     "SA imports nearly all its crude oil; mineral fuels are the dominant import group.",
     22.0, "mineral fuels chapter; crude the largest single line", "Major"),
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
