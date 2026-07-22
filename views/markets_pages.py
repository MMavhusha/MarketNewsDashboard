"""Market pages: Commodities, Currencies, Regional Macro — master-detail
layout (select an instrument, see its full analytical panel)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components import charts, ui
from data_sources import fred, macro, markets, sarb


# ---------------------------------------------------------------- helpers
def _pct(a: float, b: float) -> float | None:
    return (a / b - 1.0) * 100 if b else None


def _detail_panel(q, unit: str, key: str, note: str = ""):
    """Aladdin-style instrument panel: header, KPI row, 1Y chart."""
    if not q.ok:
        ui.empty_state(f"{q.name}: source temporarily unavailable — retries at "
                       "next refresh.")
        return
    chg_html = (f'<span class="dh-chg {ui.chg_cls(q.change_pct)}">'
                f'{"▲" if (q.change or 0) > 0 else "▼" if (q.change or 0) < 0 else "•"} '
                f'{q.fmt.format(abs(q.change))} ({q.change_pct:+.2f}%)</span>'
                if q.change_pct is not None else "")
    st.markdown(
        f'<div class="detail-head"><span class="dh-name">{ui.esc(q.name)}'
        f'{ui.alert_badge(q.name)}</span>'
        f'<span class="dh-price num">{q.fmt.format(q.price)}</span>{chg_html}'
        f'<span class="dh-meta">{ui.esc(unit)} · {ui.esc(q.asof or "")}</span></div>',
        unsafe_allow_html=True)
    ui.alert_badge_button(q.name, key=f"albtn_{key}")

    rng = st.pills("Range", ["1M", "6M", "1Y", "5Y"], default="1Y",
                   key=f"rng_{key}", label_visibility="collapsed") or "1Y"
    hist = markets.get_history(q.ticker,
                               {"1M": "1mo", "6M": "6mo",
                                "1Y": "1y", "5Y": "5y"}[rng])
    k1, k2, k3, k4 = st.columns(4)
    m1 = _pct(q.spark[-1], q.spark[0]) if len(q.spark) > 1 else None
    rchg = (_pct(float(hist.iloc[-1]), float(hist.iloc[0]))
            if len(hist) > 1 else None)
    kpis = [("1M change", f"{m1:+.2f}%" if m1 is not None else "—",
             ui.chg_cls(m1)),
            (f"{rng} high", q.fmt.format(float(hist.max())) if len(hist) else "—", ""),
            (f"{rng} low", q.fmt.format(float(hist.min())) if len(hist) else "—", ""),
            (f"{rng} change", f"{rchg:+.2f}%" if rchg is not None else "—",
             ui.chg_cls(rchg))]
    for col, (label, val, cls) in zip((k1, k2, k3, k4), kpis):
        with col:
            st.markdown(f'<div class="kpi"><div class="k-label">{label}</div>'
                        f'<div class="k-val num {cls}">{val}</div></div>',
                        unsafe_allow_html=True)
    ui.legend("Range-aware KPIs · observed closes · yfinance")
    if len(hist):
        st.plotly_chart(charts.line_chart(hist, "", y_title=unit, height=320),
                        use_container_width=True, config={"displayModeBar": False},
                        key=f"{key}_{rng}")
    if note:
        st.caption(note)


# ---------------------------------------------------------------- pages
def page_commodities():
    quotes = markets.get_commodities()
    units = {n: u for n, _t, u, _m in markets.COMMODITIES}
    names = [q.name for q in quotes]

    pick = st.pills("Instrument", names, default=names[0], key="cmd_pick",
                    label_visibility="collapsed") or names[0]
    q = next(x for x in quotes if x.name == pick)
    _detail_panel(q, units.get(pick, ""), key="cmd_chart")

    ui.section("Impact on South Africa's Balance of Payments",
               "Presented as a trade statement \u00b7 price move over the chosen window")
    st.caption("Read like a trade statement: each commodity's annual trade "
               "value (USD bn) with its live price move, subtotalled by exports "
               "and imports. Values are annual from the OEC 2024 SA trade "
               "profile / World Bank WITS (no free per-commodity live series "
               "exists); price moves are live. A move matters to the balance of "
               "payments in proportion to the value shown.")

    win = st.pills("Price-move window", ["1D", "1M", "3M", "12M"],
                   default="1M", key="bop_win", label_visibility="collapsed") or "1M"
    _win_days = {"1D": 1, "1M": 30, "3M": 91, "12M": 365}[win]

    live = {x.name: x for x in quotes}
    alias = {"Iron Ore": "Iron Ore (CME TSI)", "Coal": "Coal API2 Rotterdam (proxy)"}
    tickers = [tk for _n, tk, *_ in macro.SA_BOP_EXPOSURES]
    hist = markets.get_history_batch(tickers, "2y")
    totals = macro.SA_TRADE_TOTALS_2024

    def _move_cell(name, tk, side):
        x = live.get(name) or live.get(alias.get(name, ""))
        s = hist.get(tk)
        mv = (x.change_pct if (x and x.ok) else None) if win == "1D" \
            else (_pct_back(s, _win_days) if s is not None else None)
        if mv is None:
            return '<span class="bops-na">n/a</span>', None
        return f'<span class="num {ui.chg_cls(mv)}">{mv:+.2f}%</span>', mv

    def _stmt_row(name, note, val_bn, move_html):
        val = (f'${val_bn:,.1f}bn' if val_bn is not None
               else '<span class="bops-na">n/a</span>')
        sub = f'<span class="bops-note">{ui.esc(note)}</span>' if note else ""
        return (f'<div class="bops-row"><span class="bops-item">{ui.esc(name)}{sub}</span>'
                f'<span class="bops-val num">{val}</span>'
                f'<span class="bops-move">{move_html}</span></div>')

    def _stmt_total(label, total_bn):
        return (f'<div class="bops-row bops-total"><span class="bops-item">{ui.esc(label)}</span>'
                f'<span class="bops-val num">${total_bn:,.1f}bn</span>'
                f'<span class="bops-move"></span></div>')

    exports = [e for e in macro.SA_BOP_EXPOSURES if e[2] == "Export"]
    imports = [e for e in macro.SA_BOP_EXPOSURES if e[2] == "Import"]

    body = ('<div class="bops"><div class="bops-row bops-head">'
            '<span class="bops-item">Commodity</span>'
            '<span class="bops-val">Trade value (annual)</span>'
            f'<span class="bops-move">Price {win}</span></div>')
    # Exports section
    body += '<div class="bops-sec">Exports</div>'
    exp_tracked = 0.0
    for name, tk, side, role, val_bn, val_note, band in exports:
        mh, _ = _move_cell(name, tk, side)
        body += _stmt_row(name, val_note, val_bn, mh)
        if val_bn:
            exp_tracked += val_bn
    body += _stmt_total("Total tracked exports", exp_tracked)
    body += (f'<div class="bops-memo">of ${totals["exports"]:,.0f}bn total SA '
             f'merchandise exports (tracked here \u2248 '
             f'{exp_tracked/totals["exports"]*100:.0f}%)</div>')
    # Imports section
    body += '<div class="bops-sec">Imports</div>'
    imp_tracked = 0.0
    for name, tk, side, role, val_bn, val_note, band in imports:
        mh, _ = _move_cell(name, tk, side)
        body += _stmt_row(name, val_note, val_bn, mh)
        if val_bn:
            imp_tracked += val_bn
    body += _stmt_total("Total tracked imports", imp_tracked)
    body += (f'<div class="bops-memo">of ${totals["imports"]:,.0f}bn total SA '
             f'merchandise imports (tracked here \u2248 '
             f'{imp_tracked/totals["imports"]*100:.0f}%)</div>')
    body += '</div>'
    st.markdown(body, unsafe_allow_html=True)
    ui.legend("Exports lift the trade balance, imports subtract from it. The "
              "actual current-account impact of any price move also depends on "
              "traded volumes and the USD/ZAR rate, which are not modelled here.")


_FX_WINDOWS = ["1D", "1W", "1M", "6M", "YTD"]


def _pct_back(s, days):
    """% change of last close vs last close on/before `days` ago."""
    if s is None or len(s) < 2:
        return None
    past = s[s.index <= s.index[-1] - pd.Timedelta(days=days)]
    return _pct(float(s.iloc[-1]), float(past.iloc[-1])) if len(past) else None


def _fx_returns(quotes):
    """{pair: {window: %}} from published daily closes. 1D uses the quote's
    change vs prior close for consistency with every other page. Histories are
    fetched in ONE batched call rather than per-pair."""
    hist = markets.get_history_batch([q.ticker for q in quotes], "2y")
    out = {}
    for q in quotes:
        s = hist.get(q.ticker)
        s = s if s is not None and len(s) > 2 else None
        ytd = None
        if s is not None:
            prior = s[s.index.year < s.index[-1].year]
            if len(prior):
                ytd = _pct(float(s.iloc[-1]), float(prior.iloc[-1]))
        out[q.name] = {
            "1D": round(q.change_pct, 2) if q.change_pct is not None else None,
            "1W": _pct_back(s, 7), "1M": _pct_back(s, 30),
            "6M": _pct_back(s, 182), "YTD": ytd,
        }
    return out


def _heat_cell(v):
    if v is None:
        return '<span class="fh-cell rg-na">n/a</span>'
    a = min(abs(v) / 8.0, 1.0) * 0.22  # full tint at an 8% move
    rgb = "30,128,82" if v >= 0 else "176,33,44"
    return (f'<span class="fh-cell num" style="background:rgba({rgb},{a:.3f});">'
            f"{v:+.2f}%</span>")


def page_currencies():
    quotes = markets.get_fx()
    names = [q.name for q in quotes]

    pick = st.pills("Pair", names, default="USD/ZAR" if "USD/ZAR" in names else names[0],
                    key="fx_pick", label_visibility="collapsed") or names[0]
    q = next(x for x in quotes if x.name == pick)
    movers = sorted((x for x in quotes if x.ok and x.change_pct is not None),
                    key=lambda x: abs(x.change_pct), reverse=True)
    note = ""
    if movers:
        top = movers[0]
        direction = "strengthened" if top.change_pct > 0 else "weakened"
        note = (f"Largest move in the tracked set: {top.name} {direction} "
                f"{top.change_pct:+.2f}% (as at {top.asof or 'latest close'}). "
                f"For narrative context, see stories tagged FX under Market News.")
    _detail_panel(q, "Rate", key="fx_chart", note=note)

    ok_q = [x for x in quotes if x.ok]
    asof = next((x.asof for x in ok_q if x.asof), "latest close")
    rets = _fx_returns(ok_q)

    lc1, lc2 = st.columns([3, 2])
    with lc1:
        ui.section("Performance ladder",
                   "Pairs ranked by observed move over the window")
    with lc2:
        lwin = st.pills("Window", _FX_WINDOWS, default="1D",
                        key="fx_ladder_win",
                        label_visibility="collapsed") or "1D"
    items = [(n, r[lwin]) for n, r in rets.items() if r.get(lwin) is not None]
    if items:
        st.plotly_chart(charts.perf_ladder(items),
                        use_container_width=True,
                        config={"displayModeBar": False}, key="fx_ladder")
    else:
        ui.empty_state("No history available for this window yet.")
    ui.legend(f"As at {asof} · quote convention: a rise in USD/XXX = USD "
              "strength (quoted-currency weakness); a rise in EUR/USD, "
              "GBP/USD, AUD/USD = USD weakness · DXY = dollar index")

    ui.section("Multi-horizon returns",
               "ZAR pairs pinned first · shading scales with magnitude")
    ordered = ([n for n in rets if "ZAR" in n]
               + [n for n in rets if "ZAR" not in n])
    body = "".join(
        f'<div class="fh-row" tabindex="0"><span class="fx-pair">{ui.esc(n)}</span>'
        + "".join(_heat_cell(rets[n].get(w)) for w in _FX_WINDOWS)
        + "</div>"
        for n in ordered)
    st.markdown(
        '<div class="fx-table"><div class="fh-hd"><span>Pair</span>'
        + "".join(f'<span class="rg-num">{w} %</span>' for w in _FX_WINDOWS)
        + f"</div>{body}</div>", unsafe_allow_html=True)
    ui.legend("1D vs prior close · 1W/1M/6M vs last close on or before the "
              "lookback date · YTD vs final close of the prior year · "
              "computed from published daily closes (yfinance) · n/a = "
              "insufficient history")


def _sarb_find(*keywords):
    """First SARB series whose name contains any keyword (case-insensitive)."""
    for rows in sarb.get_sa_indicators().values():
        for r in rows:
            n = r["name"].lower()
            if any(k in n for k in keywords):
                return r
    return None


def _sarb_repo():
    """The live API labels this series 'SARB policy rate' (confirmed from the
    deployed tiles); older docs use 'Repurchase rate'/'repo' — match all."""
    groups = sarb.get_sa_indicators()
    for rows in groups.values():
        for r in rows:
            n = r["name"].lower()
            if "policy rate" in n or "repurchase" in n or "repo" in n:
                return r
    return {"_reachable": bool(groups)} if groups else None


_PENDING = {
    "Policy Rate (%)": "Central bank release / Trading Economics (key)",
    "Manufacturing PMI": "S&P Global / Trading Economics (key)",
    "10Y Government Yield (%)": "Trading Economics / Bloomberg (key)",
}

# Regions whose 10Y yield can be filled from OECD monthly series on FRED
# (freshness-guarded in _region_rows). US uses its own daily DGS10 above;
# SA prefers the live SARB R2035 bond and only falls here if that's absent.
_FRED_10Y_REGION = {
    "United Kingdom": "uk_10y",
    "Japan": "jp_10y",
    "India": "in_10y",
    "China": "cn_10y",
}


def _hist_deltas(s, days=(30, 91, 365)):
    """1M/3M/12M change in the series' own units — pure arithmetic on
    published observations. None where the lookback exceeds history."""
    if s is None or len(s) < 2:
        return (None, None, None)
    latest_ts, latest = s.index[-1], float(s.iloc[-1])
    out = []
    for d in days:
        past = s[s.index <= latest_ts - pd.Timedelta(days=d)]
        out.append(round(latest - float(past.iloc[-1]), 4) if len(past) else None)
    return tuple(out)


def _period_month(s):
    return s.index[-1].strftime("%b %Y") if s is not None and len(s) else "—"


def _fmt_date(v):
    """Normalise any source date to a single 'DD Mon YYYY' form; '—' if none
    or if the value is a descriptive period rather than a real date."""
    if not v or v == "—":
        return "—"
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d %b %Y", "%b %Y", "%Y-%m"):
        try:
            dt = pd.to_datetime(str(v), format=fmt, errors="raise")
            return dt.strftime("%d %b %Y") if fmt in ("%Y-%m-%d", "%Y/%m/%d",
                                                      "%d %b %Y") else dt.strftime("%b %Y")
        except (ValueError, TypeError):
            continue
    try:
        return pd.to_datetime(str(v)).strftime("%d %b %Y")
    except (ValueError, TypeError):
        return "—"


def _region_rows(region, matrix):
    """Reference-pack rows for one region: dicts with ind/source/latest/fmt/
    period/hist. Returns (rows, promoted_sarb_names)."""
    promoted: set = set()
    rows = []

    def add(ind, latest, fmt, source, period, hist=None, release="—",
            metric=None):
        # release = actual publication date when the source gives one (SARB,
        # FRED monthly obs); '—' when only a measured period is published
        # (World Bank annual). period = the measured period label.
        # metric = canonical grouping key for the metric-first view (defaults
        # to ind; FX/Commodity override it so all regions group together while
        # keeping their instrument-specific ind label).
        rows.append({"ind": ind, "latest": latest, "fmt": fmt, "source": source,
                     "period": period, "hist": hist, "release": release,
                     "metric": metric or ind})

    # GDP (World Bank annual — pack cadence is quarterly; deltas need history)
    cell = matrix.get("GDP Growth (YoY %)", {}).get(region)
    add("GDP Growth (YoY %)", cell[1] if cell else None, "{:,.2f}",
        "World Bank (annual)" if cell else "World Bank unreachable",
        f"{cell[0]} annual" if cell else "—")

    # CPI YoY — prefer monthly sources where they exist
    if region == "South Africa":
        cpi = _sarb_find("cpi")
        if cpi:
            promoted.add(cpi["name"])
            add("Inflation, CPI (YoY %)", ui.num_or_none(cpi["value"]), "{:,.2f}",
                "SARB (monthly)", cpi["date"], release=cpi["date"])
        else:
            cell = matrix.get("Inflation, CPI (YoY %)", {}).get(region)
            add("Inflation, CPI (YoY %)", cell[1] if cell else None, "{:,.2f}",
                "World Bank (annual)" if cell else "World Bank unreachable",
                f"{cell[0]} annual" if cell else "—")
    elif region in ("United States", "Euro Area") and fred.enabled():
        key = "us_cpi_index" if region == "United States" else "ea_hicp_index"
        s = fred.history(key, 3, yoy=True)
        lbl = ("YoY from published BLS CPI-U index · FRED"
               if region == "United States"
               else "YoY from published Eurostat HICP index · FRED")
        add("Inflation, CPI (YoY %)",
            float(s.iloc[-1]) if s is not None else None, "{:,.2f}",
            lbl if s is not None else "FRED unreachable",
            _period_month(s), s,
            release=s.index[-1].strftime("%b %Y") if s is not None else "—")
    else:
        cell = matrix.get("Inflation, CPI (YoY %)", {}).get(region)
        add("Inflation, CPI (YoY %)", cell[1] if cell else None, "{:,.2f}",
            "World Bank (annual)" if cell else "World Bank unreachable",
            f"{cell[0]} annual" if cell else "—")

    # Policy rate
    if region == "South Africa":
        repo = _sarb_repo()
        if repo is not None and "_reachable" in repo:
            repo = None
        if repo:
            promoted.add(repo["name"])
        add("Policy Rate (%)", ui.num_or_none(repo["value"]) if repo else None,
            "{:,.2f}", "SARB Web API" if repo else _PENDING["Policy Rate (%)"],
            repo["date"] if repo else "—",
            release=repo["date"] if repo else "—")
    elif region in ("United States", "Euro Area") and fred.enabled():
        key = "us_policy" if region == "United States" else "ea_policy"
        s = fred.history(key, 3)
        add("Policy Rate (%)", float(s.iloc[-1]) if s is not None else None,
            "{:,.2f}",
            fred.SERIES[key][1] if s is not None else "FRED unreachable",
            _period_month(s), s,
            release=s.index[-1].strftime("%b %Y") if s is not None else "—")
    else:
        add("Policy Rate (%)", None, "{:,.2f}", _PENDING["Policy Rate (%)"], "—")

    # Unemployment
    if region == "United States" and fred.enabled():
        s = fred.history("us_unemp", 3)
        add("Unemployment Rate (%)",
            float(s.iloc[-1]) if s is not None else None, "{:,.2f}",
            fred.SERIES["us_unemp"][1] if s is not None else "FRED unreachable",
            _period_month(s), s,
            release=s.index[-1].strftime("%b %Y") if s is not None else "—")
    else:
        cell = matrix.get("Unemployment Rate (%)", {}).get(region)
        add("Unemployment Rate (%)", cell[1] if cell else None, "{:,.2f}",
            "World Bank (annual)" if cell else "World Bank unreachable",
            f"{cell[0]} annual" if cell else "—")

    # 10Y yield
    if region == "South Africa":
        r209 = _sarb_find("r2035", "r209", "2036")
        if r209:
            promoted.add(r209["name"])
            add("10Y Government Yield (%)", ui.num_or_none(r209["value"]),
                "{:,.2f}", f'{r209["name"]} · SARB', r209["date"],
                release=r209["date"])
        else:
            add("10Y Government Yield (%)", None, "{:,.2f}",
                _PENDING["10Y Government Yield (%)"], "—")
    elif region == "United States" and fred.enabled():
        s = fred.history("us_10y", 3)
        add("10Y Government Yield (%)",
            float(s.iloc[-1]) if s is not None else None, "{:,.2f}",
            fred.SERIES["us_10y"][1] if s is not None else "FRED unreachable",
            _period_month(s), s,
            release=s.index[-1].strftime("%b %Y") if s is not None else "—")
    elif region in _FRED_10Y_REGION and fred.enabled():
        # OECD monthly 10Y via FRED, freshness-guarded: a discontinued series
        # returns None here rather than a stale value, so the cell stays an
        # honest "pending" instead of showing an out-of-date number.
        row = fred.latest_fresh(_FRED_10Y_REGION[region])
        if row:
            add("10Y Government Yield (%)", ui.num_or_none(row["value"]),
                "{:,.2f}", row["label"], row["date"], release=row["date"])
        else:
            add("10Y Government Yield (%)", None, "{:,.2f}",
                _PENDING["10Y Government Yield (%)"], "—")
    else:
        add("10Y Government Yield (%)", None, "{:,.2f}",
            _PENDING["10Y Government Yield (%)"], "—")

    # FX is intentionally NOT a Regional Macro metric — the Currencies page
    # carries every pair with a full detail panel and return ladder.

    # PMI (no free source — proprietary press releases)
    add("Manufacturing PMI", None, "{:,.1f}", _PENDING["Manufacturing PMI"], "—")
    return rows, promoted


def _fmt_delta(v, fmt):
    if v is None:
        return '<span class="rg-na">n/a*</span>'
    return f'<span class="num">{"+" if v >= 0 else "\u2212"}{fmt.format(abs(v))}</span>'


def _metric_row_html(region, r):
    """One region's cell-set for a metric comparison table (country-major)."""
    d1, d3, d12 = _hist_deltas(r["hist"])
    latest = (f'<span class="num">{r["fmt"].format(r["latest"])}</span>'
              if r["latest"] is not None else '<span class="rg-na">n/a</span>')
    rel = _fmt_date(r.get("release", "—"))
    return (
        f'<div class="rg-row" tabindex="0"><span><span class="rg-ind">{ui.esc(region)}'
        f'</span><span class="rg-src">{ui.esc(r["source"])}</span></span>'
        f'<span class="rg-num">{latest}</span>'
        f'<span class="rg-num rg-mut">{ui.esc(rel)}</span>'
        f'<span class="rg-num rg-mut">{ui.esc(r["period"])}</span>'
        f'<span class="rg-num">{_fmt_delta(d1, r["fmt"])}</span>'
        f'<span class="rg-num">{_fmt_delta(d3, r["fmt"])}</span>'
        f'<span class="rg-num">{_fmt_delta(d12, r["fmt"])}</span></div>')


def _metric_grid(metric, by_region):
    """Comparison table for ONE metric across every region (country-major),
    mirroring the reference pack: Country | Latest | Release | Period | deltas.
    by_region: {region: {metric_name: row}}."""
    body = ""
    for region in macro.REGIONS:
        r = by_region.get(region, {}).get(metric)
        if r is None:
            continue
        body += _metric_row_html(region, r)
    st.markdown(
        '<div class="fx-table"><div class="rg-hd"><span>Country</span>'
        '<span class="rg-num">Latest</span><span class="rg-num">Release</span>'
        '<span class="rg-num">Period</span><span class="rg-num">1M \u0394</span>'
        '<span class="rg-num">3M \u0394</span><span class="rg-num">12M \u0394</span>'
        '</div>' + body + '</div>', unsafe_allow_html=True)


def _metric_compare_chart(metric, by_region):
    """Country-overlay of the chosen metric, rescalable to a selected window
    (1M/6M/12M/2Y/3Y). Each country is a line; the window trims every series to
    the same date cutoff so they stay comparable."""
    import pandas as pd
    series_full = {}
    for region in macro.REGIONS:
        r = by_region.get(region, {}).get(metric)
        if r is not None and r["hist"] is not None and len(r["hist"]) > 2:
            series_full[region] = r["hist"]
    if not series_full:
        ui.empty_state(f"{metric}: history source pending for all regions "
                       "\u2014 the overlay fills as free sources land.")
        return

    win = st.pills("Comparison window", ["1M", "6M", "12M", "2Y", "3Y"],
                   default="12M", key=f"cmp_win_{metric}",
                   label_visibility="collapsed") or "12M"
    _days = {"1M": 30, "6M": 182, "12M": 365, "2Y": 730, "3Y": 1095}[win]

    # Trim each series to the window by date cutoff (works for monthly and
    # daily series alike). Keep a series only if it still has >1 point in-window.
    series = {}
    for name, s in series_full.items():
        cutoff = s.index[-1] - pd.Timedelta(days=_days)
        w = s[s.index >= cutoff]
        if len(w) > 1:
            series[name] = w
    if not series:
        ui.empty_state(f"No region has enough history for a {win} overlay of "
                       f"{metric}. Try a longer window.")
        return

    unit = "%" if "%" in metric else ""
    st.plotly_chart(
        charts.pack_multi_history(series, f"{metric} \u2014 last {win}",
                                  height=300, y_title=unit),
        use_container_width=True, config={"displayModeBar": False})
    notes = []
    if len(series) < len(macro.REGIONS):
        missing = [r for r in macro.REGIONS if r not in series]
        notes.append("no in-window history for: " + ", ".join(missing))
    st.caption(("Overlay of " + ", ".join(series.keys()) + " over the last "
                + win + (". " + notes[0] if notes else ".")))


def _sa_specific_detail(promoted):
    """SA-only SARB series (prime, M3, credit, etc.) that do not fit the
    cross-country metric frame. Metal prices and FX are excluded (they live
    on Commodities/Currencies)."""
    groups = sarb.get_sa_indicators()
    if groups:
        ui.section("Live SARB releases",
                   "SA-specific series not shown on Commodities or "
                   "Currencies · SARB Web API")
        # Drop series that duplicate the Commodities page (metal
        # prices) and the Currencies page (FX rates) — those are
        # shown there with live charts. Keep only SA-unique
        # monetary/real-sector data (prime, M3, credit, etc.).
        def _dup(name: str) -> bool:
            n = name.lower()
            price_dup = any(k in n for k in (
                "gold", "platinum", "palladium", "brent", "oil",
                "rhodium"))
            fx_dup = (("exchange rate" in n or "per us" in n
                       or "per dollar" in n or "/us$" in n
                       or "rand per" in n or "us$" in n
                       or "euro" in n or "pound" in n or "yen" in n)
                      and "real effective" not in n)
            return price_dup or fx_dup
        key_rows = groups.get("Key rates & prices") or next(iter(groups.values()))
        pool = [r for rows in groups.values() for r in rows]
        fresh = [r for r in key_rows
                 if r["name"] not in promoted and not _dup(r["name"])]
        for r in pool:  # backfill with other SA-unique series
            if len(fresh) >= 8:
                break
            if (r["name"] not in promoted and r not in fresh
                    and not _dup(r["name"])):
                fresh.append(r)
        tiles = fresh[:8]
        if not tiles:
            ui.empty_state("No SA-unique series available right now "
                           "(prices and FX are on Commodities and "
                           "Currencies).")
        tcols = st.columns(4)
        for i, r in enumerate(tiles):
            with tcols[i % 4]:
                st.markdown(
                    f'<div class="kpi" style="margin-bottom:10px;">'
                    f'<div class="k-label" title="{ui.esc(r["name"])}">{ui.esc(r["name"][:34])}</div>'
                    f'<div class="k-val num">{ui.esc(r["value"])}'
                    f'<span style="font-size:11px;font-weight:400;color:#909288;"> {ui.esc(r["unit"])}</span></div>'
                    f'<div class="k-sub">{ui.esc(r["agency"])} · {ui.esc(r["date"])}</div></div>',
                    unsafe_allow_html=True)
        shown = {r["name"] for r in tiles} | promoted
        # "All published series" also excludes the duplicates now
        n_other = sum(1 for rows in groups.values() for r in rows
                      if r["name"] not in shown and not _dup(r["name"]))
        if n_other:
            with st.expander(f"All SA-unique series ({n_other})"):
                for glabel, rows in groups.items():
                    for r in rows:
                        if r["name"] in shown or _dup(r["name"]):
                            continue
                        st.markdown(
                            f'<div class="cal-row"><span class="cty" style="width:340px;">{ui.esc(r["name"])}</span>'
                            f'<span class="ev">{ui.esc(glabel)} · {ui.esc(r["agency"])} · {ui.esc(r["date"])}</span>'
                            f'<span class="cal-val num">{ui.esc(r["value"])} {ui.esc(r["unit"])}</span></div>',
                            unsafe_allow_html=True)
        st.caption("Metal prices are on Commodities; exchange rates "
                   "on Currencies \u2014 excluded here to avoid "
                   "duplication.")


def page_regional_macro():
    st.caption("Navigate by indicator: pick a metric below to compare every "
               "region side by side. Live free sources fill what they can "
               "(World Bank, SARB, FRED, yfinance); the rest shows its named "
               "target source. No estimation is performed.")

    matrix = macro.wb_latest_matrix()
    # Compute every region's rows ONCE, then pivot by canonical metric key.
    by_region = {}
    promoted_sa = set()
    for region in macro.REGIONS:
        rows, promoted = _region_rows(region, matrix)
        by_region[region] = {r["metric"]: r for r in rows}
        if region == "South Africa":
            promoted_sa = promoted
    # Metric order = the reference-pack row order (canonical keys).
    any_region = next(iter(macro.REGIONS))
    metric_order = [r["metric"] for r in _region_rows(any_region, matrix)[0]]

    # Short tab labels for the metrics.
    label_map = {
        "GDP Growth (YoY %)": "GDP",
        "Inflation, CPI (YoY %)": "Inflation",
        "Policy Rate (%)": "Policy Rate",
        "Unemployment Rate (%)": "Unemployment",
        "10Y Government Yield (%)": "10Y Yield",
        "Manufacturing PMI": "PMI",
    }
    short_labels = [label_map.get(m, m) for m in metric_order]

    tabs = st.tabs(short_labels)
    for tab, metric in zip(tabs, metric_order):
        with tab:
            title = label_map.get(metric, metric)
            ui.section(title,
                       "All regions \u00b7 same indicator \u00b7 reference-pack layout")
            _metric_grid(metric, by_region)
            ui.legend("Release = publication date where the source provides "
                      "one, else \u2014 \u00b7 Period = the measured period "
                      "\u00b7 \u0394 in the indicator's own units, arithmetic "
                      "on published observations \u00b7 n/a = source pending "
                      "(BIS / Eurostat / Bundesbank queued)")
            ui.section("Cross-country comparison",
                       "Overlay of all regions \u00b7 pick a window below")
            _metric_compare_chart(metric, by_region)

    # Central bank detail, per region. Only SARB has a rich free API (shown
    # live in a collapsed dropdown); other central banks are linked, since
    # their headline series already appear in the metric tabs above and there
    # is no free per-CB release feed to reproduce here.
    st.divider()
    ui.section("Central bank detail",
               "SARB releases live \u00b7 others linked to source")
    for region in macro.REGIONS:
        cb = macro.CENTRAL_BANKS.get(region)
        if not cb:
            continue
        cb_name, cb_url = cb
        if region == "South Africa":
            with st.expander(f"{region} \u2014 {cb_name} live releases"):
                _sa_specific_detail(promoted_sa)
        elif region == "United States":
            with st.expander(f"{region} \u2014 {cb_name} · Treasury yield curve"):
                curve = fred.us_yield_curve()
                if curve:
                    st.plotly_chart(
                        charts.yield_curve(
                            curve, f"US Treasury par yield curve \u00b7 {curve[0]['date']}"),
                        use_container_width=True,
                        config={"displayModeBar": False})
                    inv = curve[-1]["yield"] < curve[0]["yield"]
                    tips = ("Short end above long end \u2014 the curve is "
                            "inverted (often read as a recession signal)." if inv
                            else "Upward-sloping \u2014 longer yields exceed "
                            "short, the normal shape.")
                    st.caption("Constant-maturity par yields, 1M\u201330Y, from "
                               "FRED (Fed H.15, same figures Treasury publishes). "
                               + tips + " Full releases: "
                               f"[{cb_url}]({cb_url})")
                else:
                    st.markdown(
                        "Headline series (policy rate, 10Y, CPI) are in the "
                        "tabs above. Full releases: "
                        f'<a href="{ui.esc(cb_url)}" target="_blank">{ui.esc(cb_url)}</a>',
                        unsafe_allow_html=True)
        else:
            st.markdown(
                f'<div class="cb-row"><span class="cb-name">{ui.esc(region)} '
                f'\u00b7 {ui.esc(cb_name)}</span>'
                f'<span class="cb-note">Headline series (policy rate, 10Y, CPI) '
                f'are in the tabs above. Full releases: '
                f'<a href="{ui.esc(cb_url)}" target="_blank">{ui.esc(cb_url)}</a>'
                f'</span></div>', unsafe_allow_html=True)
    st.caption("Only SARB publishes a rich free statistics API, so its series "
               "are shown live. Other central banks are linked to their "
               "official statistics portals rather than reproduced, to avoid "
               "duplicating the metric tabs or showing stand-in data.")
