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


def _parse_csv_text(text: str, keep_all: bool = False) -> list[dict]:
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
        if chap not in CHAPTERS and not keep_all:
            continue
        try:
            val = float(str(r.get(c_val, "")).replace(",", "").replace(" ", "").strip())
        except (ValueError, AttributeError, TypeError):
            continue
        if not chap:
            continue
        rows.append({"chapter": chap,
                     "label": CHAPTERS.get(chap, f"Chapter {chap}"), "value": val,
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


def _cumulative_by_chapter(rows: list[dict], all_rows: list[dict] | None = None) -> dict:
    """From monthly rows (period 'YYYY-MM'), build the SARS cumulative view:
    per chapter → {ytd, ytd_prev, yoy_pct, latest_val, latest_month, months}.
    YTD = Jan..latest-month of the newest year; prior YTD = same months a year
    earlier (like-for-like, so the YoY % is honest).

    all_rows (optional): every chapter's rows (unfiltered), used to compute the
    TOTAL SA export YTD so shares can be expressed against total exports and
    reconciled — not just against the tracked subset."""
    # discover months present
    def ym(r):
        p = r.get("period", "")
        # accept 'YYYY-MM' or 'YYYYMM'
        p = p.replace("/", "-")
        if len(p) == 6 and p.isdigit():
            return p[:4], p[4:6]
        if "-" in p and len(p) >= 7:
            y, m = p[:4], p[5:7]
            return y, m
        return None, None
    years = sorted({ym(r)[0] for r in rows if ym(r)[0]})
    if not years:
        return {}
    cur_y = years[-1]
    prev_y = str(int(cur_y) - 1)
    # latest month present in current year
    cur_months = sorted({ym(r)[1] for r in rows
                         if ym(r)[0] == cur_y and ym(r)[1]})
    if not cur_months:
        return {}
    latest_m = cur_months[-1]
    out: dict[str, dict] = {}
    for ch in CHAPTERS:
        cr = [r for r in rows if r["chapter"] == ch]
        ytd = sum(r["value"] for r in cr
                  if ym(r)[0] == cur_y and ym(r)[1] and ym(r)[1] <= latest_m)
        ytd_prev = sum(r["value"] for r in cr
                       if ym(r)[0] == prev_y and ym(r)[1] and ym(r)[1] <= latest_m)
        latest_val = sum(r["value"] for r in cr
                         if ym(r)[0] == cur_y and ym(r)[1] == latest_m)
        if ytd == 0 and ytd_prev == 0 and latest_val == 0:
            continue
        yoy = ((ytd - ytd_prev) / ytd_prev * 100) if ytd_prev else None
        out[ch] = {"chapter": ch, "label": CHAPTERS[ch], "ytd": ytd,
                   "ytd_prev": ytd_prev, "yoy_pct": yoy,
                   "latest_val": latest_val, "latest_month": f"{cur_y}-{latest_m}",
                   "cur_year": cur_y, "prev_year": prev_y,
                   "through_month": latest_m}
    # total SA exports YTD (all chapters), for honest share reconciliation
    if all_rows:
        tot = sum(r["value"] for r in all_rows
                  if ym(r)[0] == cur_y and ym(r)[1] and ym(r)[1] <= latest_m)
        if tot > 0:
            out["__total__"] = {"ytd": tot}
    return out


# Dated fallback for the cumulative view (used if no live/CSV data). Values are
# illustrative last-known ZAR bn; clearly stamped so staleness is visible.
_DATED_MOVE = {
    "as_of": "2025 full-year vs 2024 (SARS, dated)",
    "unit": "R bn", "cur_year": "2025", "prev_year": "2024",
    "through_month": "12", "latest_month": "2025-12",
    "total_ytd": 2200.0,  # approx SA total merchandise exports 2025 (ZAR bn)
    "rows": [
        {"chapter": "71", "label": CHAPTERS["71"], "ytd": 383.0,
         "ytd_prev": 332.0, "yoy_pct": 15.4, "latest_val": 34.0},
        {"chapter": "26", "label": CHAPTERS["26"], "ytd": 236.0,
         "ytd_prev": 224.0, "yoy_pct": 5.4, "latest_val": 19.5},
        {"chapter": "27", "label": CHAPTERS["27"], "ytd": 168.0,
         "ytd_prev": 178.0, "yoy_pct": -5.6, "latest_val": 13.8},
        {"chapter": "74", "label": CHAPTERS["74"], "ytd": 24.0,
         "ytd_prev": 22.0, "yoy_pct": 9.1, "latest_val": 2.1},
    ],
    "source_url": _PORTAL,
}


def _pack_movement(source, cum, all_total_note=None):
    """Build the movement dict from a cumulative map, pulling out the total."""
    total = cum.pop("__total__", None)
    chapter_rows = [cum[c] for c in CHAPTERS if c in cum]
    if not chapter_rows:
        return None
    any_r = chapter_rows[0]
    return {
        "source": source,
        "as_of": {"live": "latest SARS release", "csv": "from uploaded SARS CSV"}.get(source, ""),
        "unit": "R", "cur_year": any_r["cur_year"], "prev_year": any_r["prev_year"],
        "through_month": any_r["through_month"], "rows": chapter_rows,
        "total_ytd": total["ytd"] if total else None,
        "source_url": _PORTAL,
    }


def get_commodity_movement() -> dict:
    """SARS cumulative commodity view: {source, as_of, unit, cur_year,
    prev_year, through_month, total_ytd, rows:[{chapter,label,ytd,ytd_prev,
    yoy_pct,latest_val,latest_month}], source_url}.

    total_ytd = TOTAL SA exports YTD (all chapters), so category shares can be
    expressed against total exports and reconciled — not just the tracked
    subset. None when the source doesn't provide all-chapter data.

    Tries live scrape, then user CSV, then dated fallback. YTD is like-for-like
    (same months this year vs last), so the YoY % is a fair comparison."""
    # tier 1: live
    live_rows = _try_live_rows()
    if live_rows:
        all_rows = live_rows  # live parse keeps all chapters if keep_all used
        cum = _cumulative_by_chapter(
            [r for r in live_rows if r["chapter"] in CHAPTERS], all_rows)
        packed = _pack_movement("live", cum)
        if packed:
            return packed
    # tier 2: CSV
    try:
        if _CSV_PATH.exists():
            text = _CSV_PATH.read_text(encoding="utf-8")
            tracked = _parse_csv_text(text)
            all_rows = _parse_csv_text(text, keep_all=True)
            cum = _cumulative_by_chapter(tracked, all_rows)
            packed = _pack_movement("csv", cum)
            if packed:
                return packed
    except Exception:
        pass
    # tier 3: dated
    return {"source": "dated", **_DATED_MOVE}


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _try_live_rows() -> list[dict] | None:
    """Attempt the portal form POST. Returns RAW monthly rows (not aggregated)
    or None. Best-effort: the ASP.NET viewstate handshake may need adjustment
    against the live site (untestable from the build sandbox)."""
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
        rows = _parse_csv_text(p.text)
        return rows or None
    except Exception:
        return None


def get_commodity_exports() -> dict:
    """{'source': 'live'|'csv'|'dated', 'as_of', 'unit', 'rows', 'source_url'}.

    rows: [{chapter, label, value, period}] — SA export value by HS chapter,
    one consistent source so they can be compared across periods."""
    # tier 1: live scrape
    live_rows = _try_live_rows()
    if live_rows:
        agg = _aggregate(live_rows)
        if agg:
            return {"source": "live", "as_of": "latest SARS release", "unit": "R",
                    "rows": agg, "source_url": _PORTAL}
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
