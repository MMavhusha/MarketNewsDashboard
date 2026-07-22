"""SARS merchandise trade statistics — per-commodity export values.

Source of truth: SARS Trade Statistics data-download portal
(https://tools.sars.gov.za/tradestatsportal/data_download.aspx). This is the
authoritative SA customs data — official, free, per HS chapter, monthly AND
annual, in ZAR, one consistent product definition. It is the single source
that lets us show export composition as a real period-over-period movement
(same source / currency / definitions across every column).

Three-tier sourcing, each honest about which it used:
  1. LIVE  — replicate the portal's form POST and parse the returned rows.
             (ASP.NET viewstate form; fragile and untestable from the build
             sandbox, so it may need tuning on first deploy.)
  2. CSV   — read a file the user downloaded from that same portal and dropped
             in data/sars_trade.csv. Robust; real SARS data; monthly human step.
  3. DATED — fall back to the last figures we recorded, clearly stamped, so the
             panel is never blank but never silently stale either.

The commodities we track map to SARS HS chapters:
  Ch 26 Ores (iron ore, manganese, chrome) · Ch 27 Crude/Coal/Petroleum
  Ch 71 Gold, Platinum, Precious metals    · Ch 74 Copper
Chapter-level is coarser than the 4-digit lines elsewhere in the app, but it is
the level SARS exposes cleanly and it is internally consistent — which is the
whole point of using one source for a movement statement.
"""
from __future__ import annotations

import csv
import io
from pathlib import Path

import requests
import streamlit as st

_PORTAL = "https://tools.sars.gov.za/tradestatsportal/data_download.aspx"
_CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "sars_trade.csv"

# HS chapters we surface, with the friendly label used in the panel.
CHAPTERS = {
    "26": "Ores (iron ore, manganese, chrome)",
    "27": "Coal, crude & petroleum",
    "71": "Gold, platinum & precious metals",
    "74": "Copper",
}

# Dated fallback — last recorded SARS annual chapter values (ZAR bn, 2025).
# Update when refreshing; the panel shows this stamp so staleness is visible.
_DATED = {
    "as_of": "2025 (annual, SARS)",
    "unit": "R bn",
    "rows": [
        {"chapter": "71", "label": CHAPTERS["71"], "value": 383.0, "period": "2025"},
        {"chapter": "26", "label": CHAPTERS["26"], "value": 236.0, "period": "2025"},
        {"chapter": "27", "label": CHAPTERS["27"], "value": 168.0, "period": "2025"},
        {"chapter": "74", "label": CHAPTERS["74"], "value": 24.0, "period": "2025"},
    ],
    "source_url": _PORTAL,
}


def _parse_csv_text(text: str) -> list[dict]:
    """Parse a SARS-portal CSV export into chapter rows. Expects columns that
    include a chapter identifier, a period (YearMonth or CalendarYear) and a
    CustomsValue. Tolerant of column-name variations."""
    rows: list[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return rows
    # locate columns case-insensitively
    cols = {c.lower().strip(): c for c in reader.fieldnames}

    def col(*cands):
        for c in cands:
            if c in cols:
                return cols[c]
        return None

    c_chap = col("chapter")  # bare "71" column — preferred, no comma issues
    c_chap_desc = col("chapterandddescription", "chapteranddescription")
    c_val = col("customsvalue", "value", "customs_value")
    c_per = col("yearmonth", "calendaryear", "period")
    c_type = col("tradetype", "trade_type")
    if not (c_val and (c_chap or c_chap_desc)):
        return rows
    for r in reader:
        # exports only, if a trade-type column exists
        if c_type and "export" not in str(r.get(c_type, "")).lower():
            continue
        # prefer the bare Chapter column; else take leading digits of the
        # combined description (robust even if unquoted commas shifted fields)
        if c_chap and str(r.get(c_chap, "")).strip():
            chap = str(r.get(c_chap, "")).strip().split()[0]
        else:
            chap_raw = str(r.get(c_chap_desc, "")).strip()
            chap = chap_raw.split("-")[0].strip().split()[0] if chap_raw else ""
        if chap not in CHAPTERS:
            continue
        try:
            val = float(str(r.get(c_val, "")).replace(",", "").replace(" ", "").strip())
        except (ValueError, AttributeError, TypeError):
            continue
        rows.append({"chapter": chap, "label": CHAPTERS[chap], "value": val,
                     "period": str(r.get(c_per, "")).strip()})
    return rows


def _aggregate(rows: list[dict]) -> list[dict]:
    """Sum values per chapter (a CSV may hold many months/tariff lines)."""
    agg: dict[str, dict] = {}
    for r in rows:
        a = agg.setdefault(r["chapter"], {"chapter": r["chapter"],
                                          "label": r["label"], "value": 0.0,
                                          "period": r["period"]})
        a["value"] += r["value"]
    # order by our chapter list
    return [agg[c] for c in CHAPTERS if c in agg]


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _try_live() -> list[dict] | None:
    """Attempt the portal form POST. Returns rows or None. Best-effort: the
    ASP.NET viewstate handshake may need adjustment against the live site."""
    try:
        s = requests.Session()
        # 1) GET to obtain viewstate tokens
        g = s.get(_PORTAL, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        g.raise_for_status()
        import re
        def _tok(name):
            m = re.search(rf'id="{name}" value="([^"]*)"', g.text)
            return m.group(1) if m else ""
        payload = {
            "__VIEWSTATE": _tok("__VIEWSTATE"),
            "__VIEWSTATEGENERATOR": _tok("__VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": _tok("__EVENTVALIDATION"),
            # field names are best-effort; real names confirmed on deploy
            "TradeType": "Exports",
        }
        p = s.post(_PORTAL, data=payload, timeout=25,
                   headers={"User-Agent": "Mozilla/5.0"})
        p.raise_for_status()
        # portal returns CSV-like content on download; try to parse
        rows = _parse_csv_text(p.text)
        return _aggregate(rows) or None
    except Exception:
        return None


def get_commodity_exports() -> dict:
    """{'source': 'live'|'csv'|'dated', 'as_of', 'unit', 'rows', 'source_url'}.

    rows: [{chapter, label, value, period}] — SA export value by HS chapter,
    one consistent source so they can be compared across periods."""
    # tier 1: live scrape
    live = _try_live()
    if live:
        return {"source": "live", "as_of": "latest SARS release", "unit": "R",
                "rows": live, "source_url": _PORTAL}
    # tier 2: user-provided CSV from the same portal
    try:
        if _CSV_PATH.exists():
            rows = _aggregate(_parse_csv_text(_CSV_PATH.read_text(encoding="utf-8")))
            if rows:
                return {"source": "csv", "as_of": "from uploaded SARS CSV",
                        "unit": "R", "rows": rows, "source_url": _PORTAL}
    except Exception:
        pass
    # tier 3: dated fallback
    return {"source": "dated", **_DATED}
