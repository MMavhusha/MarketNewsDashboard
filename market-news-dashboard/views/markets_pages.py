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
        f'<div class="detail-head"><span class="dh-name">{ui.esc(q.name)}</span>'
        f'<span class="dh-price num">{q.fmt.format(q.price)}</span>{chg_html}'
        f'<span class="dh-meta">{ui.esc(unit)} · {ui.esc(q.asof or "")}</span></div>',
        unsafe_allow_html=True)

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
               "Structural trade exposure × latest price moves")
    st.caption("Exposure mapping reflects the well-documented composition of SA trade "
               "(PGMs, gold, coal and iron ore as key exports; crude oil as the "
               "dominant commodity import). Net BoP effect in a given period depends "
               "on volumes and the rand.")
    live = {x.name: x for x in quotes}
    alias = {"Iron Ore": "Iron Ore (SGX proxy)", "Coal": "Coal (Newcastle proxy)"}
    for name, tk, side, note in macro.SA_BOP_EXPOSURES:
        x = live.get(name) or live.get(alias.get(name, ""))
        chg = (f'<span class="num {ui.chg_cls(x.change_pct)}">{x.change_pct:+.2f}%</span>'
               if x and x.ok and x.change_pct is not None
               else '<span style="color:#909288;">n/a</span>')
        kind = "green" if side == "Export" else "red"
        st.markdown(
            f'<div class="cal-row"><span class="cty">{ui.esc(name)}</span>'
            f'<span class="ev">{ui.badge(side, kind)} {ui.esc(note)}</span>'
            f'<span class="cal-val">{chg}</span></div>',
            unsafe_allow_html=True)


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

    ui.section("All pairs at a glance",
               "Neutral mini-trends · open any pair via the pills above")
    ok_q = [x for x in quotes if x.ok]
    asof = next((x.asof for x in ok_q if x.asof), "latest close")
    p1, p2 = st.columns([1, 1.4])
    win = p1.pills("Trend window", ["1M", "6M", "1Y"], default="1M",
                   key="fx_grid_win", label_visibility="collapsed") or "1M"
    order = p2.pills("Sort", ["Pair", f"{win} %", "1D %"], default="Pair",
                     key="fx_grid_sort", label_visibility="collapsed") or "Pair"
    if win == "1M":
        trends = {x.name: (x.spark if len(x.spark) > 2 else None) for x in ok_q}
    else:
        per = {"6M": "6mo", "1Y": "1y"}[win]
        trends = {}
        for x in ok_q:
            h = markets.get_history(x.ticker, per)
            trends[x.name] = [float(v) for v in h.tolist()] if len(h) > 2 else None

    rows = []
    for x in ok_q:
        t = trends.get(x.name)
        wchg = _pct(t[-1], t[0]) if t else None
        rows.append((x, t, wchg))
    if order == "Pair":
        rows.sort(key=lambda r: r[0].name)
    elif order == "1D %":
        rows.sort(key=lambda r: (r[0].change_pct is None,
                                 -(r[0].change_pct or 0)))
    else:
        rows.sort(key=lambda r: (r[2] is None, -(r[2] or 0)))

    def _num(v, cls=True):
        if v is None:
            return '<span style="color:#909288;">n/a</span>'
        c = f' {ui.chg_cls(v)}' if cls else ""
        return f'<span class="num{c}">{v:+.2f}%</span>'

    body = "".join(
        f'<div class="fx-row"><span class="fx-pair">{ui.esc(x.name)}</span>'
        f'<span class="fx-spark">'
        + (ui.spark_svg(t, dot=("#1E8052" if (wchg or 0) >= 0 else "#B0212C"))
           if t else '<span style="color:#C9CBC4;font-size:11px;">no history</span>')
        + f'</span><span class="fx-num num">{x.fmt.format(x.price)}</span>'
        f'<span class="fx-num">{_num(wchg)}</span>'
        f'<span class="fx-num">{_num(x.change_pct)}</span></div>'
        for x, t, wchg in rows)
    st.markdown(
        f'<div class="fx-table"><div class="fx-hd"><span>Pair</span>'
        f'<span>{win} trend</span><span class="fx-num">Last</span>'
        f'<span class="fx-num">{win} %</span><span class="fx-num">1D %</span>'
        f'</div>{body}</div>',
        unsafe_allow_html=True)
    ui.legend(f"As at {asof} · {win} % = change over the trend window · "
              "1D % vs prior close · sparklines each on their own scale, "
              "endpoint dot = window direction")


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


def _fx_series(ticker):
    h = markets.get_history(ticker, "2y")
    return h if len(h) > 2 else None


def _period_month(s):
    return s.index[-1].strftime("%b %Y") if s is not None and len(s) else "—"


def _region_rows(region, matrix):
    """Reference-pack rows for one region: dicts with ind/source/latest/fmt/
    period/hist. Returns (rows, promoted_sarb_names)."""
    promoted: set = set()
    rows = []

    def add(ind, latest, fmt, source, period, hist=None):
        rows.append({"ind": ind, "latest": latest, "fmt": fmt, "source": source,
                     "period": period, "hist": hist})

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
                "SARB (monthly)", cpi["date"])
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
            _period_month(s), s)
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
            repo["date"] if repo else "—")
    elif region in ("United States", "Euro Area") and fred.enabled():
        key = "us_policy" if region == "United States" else "ea_policy"
        s = fred.history(key, 3)
        add("Policy Rate (%)", float(s.iloc[-1]) if s is not None else None,
            "{:,.2f}",
            fred.SERIES[key][1] if s is not None else "FRED unreachable",
            _period_month(s), s)
    else:
        add("Policy Rate (%)", None, "{:,.2f}", _PENDING["Policy Rate (%)"], "—")

    # Unemployment
    if region == "United States" and fred.enabled():
        s = fred.history("us_unemp", 3)
        add("Unemployment Rate (%)",
            float(s.iloc[-1]) if s is not None else None, "{:,.2f}",
            fred.SERIES["us_unemp"][1] if s is not None else "FRED unreachable",
            _period_month(s), s)
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
                "{:,.2f}", f'{r209["name"]} · SARB', r209["date"])
        else:
            add("10Y Government Yield (%)", None, "{:,.2f}",
                _PENDING["10Y Government Yield (%)"], "—")
    elif region == "United States" and fred.enabled():
        s = fred.history("us_10y", 3)
        add("10Y Government Yield (%)",
            float(s.iloc[-1]) if s is not None else None, "{:,.2f}",
            fred.SERIES["us_10y"][1] if s is not None else "FRED unreachable",
            _period_month(s), s)
    else:
        add("10Y Government Yield (%)", None, "{:,.2f}",
            _PENDING["10Y Government Yield (%)"], "—")

    # FX vs USD (full history free via yfinance for every region)
    fx_name, fx_tk = macro.REGION_FX[region]
    s = _fx_series(fx_tk)
    q = markets.get_quotes([(fx_name, fx_tk)])[0]
    add(f"FX — {fx_name}", float(s.iloc[-1]) if s is not None
        else (float(q.price) if q.ok else None),
        "{:,.4f}", "yfinance (daily close)",
        s.index[-1].strftime("%d %b %Y") if s is not None
        else (q.asof or "—"), s)

    # PMI (no free source — proprietary press releases)
    add("Manufacturing PMI", None, "{:,.1f}", _PENDING["Manufacturing PMI"], "—")
    return rows, promoted


def _fmt_delta(v, fmt):
    if v is None:
        return '<span class="rg-na">n/a*</span>'
    return f'<span class="num">{"+" if v >= 0 else "−"}{fmt.format(abs(v))}</span>'


def _pack_grid(rows, key_prefix=""):
    body = ""
    for r in rows:
        d1, d3, d12 = _hist_deltas(r["hist"])
        latest = (f'<span class="num">{r["fmt"].format(r["latest"])}</span>'
                  if r["latest"] is not None else '<span class="rg-na">n/a</span>')
        body += (
            f'<div class="rg-row"><span><span class="rg-ind">{ui.esc(r["ind"])}'
            f'</span><span class="rg-src">{ui.esc(r["source"])}</span></span>'
            f'<span class="rg-num">{latest}</span>'
            f'<span class="rg-num rg-mut">—</span>'
            f'<span class="rg-num rg-mut">{ui.esc(r["period"])}</span>'
            f'<span class="rg-num">{_fmt_delta(d1, r["fmt"])}</span>'
            f'<span class="rg-num">{_fmt_delta(d3, r["fmt"])}</span>'
            f'<span class="rg-num">{_fmt_delta(d12, r["fmt"])}</span></div>')
    st.markdown(
        '<div class="fx-table"><div class="rg-hd"><span>Indicator</span>'
        '<span class="rg-num">Latest</span><span class="rg-num">Release</span>'
        '<span class="rg-num">Period</span><span class="rg-num">1M Δ</span>'
        '<span class="rg-num">3M Δ</span><span class="rg-num">12M Δ</span>'
        f'</div>{body}</div>', unsafe_allow_html=True)


def _comparison_table(ind, matrix):
    """Opt-in cross-region view: ONE indicator across all regions."""
    body = ""
    for region in macro.REGIONS:
        rows, _ = _region_rows(region, matrix)
        row = next((r for r in rows if r["ind"] == ind
                    or (ind == "FX vs USD" and r["ind"].startswith("FX"))), None)
        if row is None:
            continue
        d1, d3, d12 = _hist_deltas(row["hist"])
        latest = (f'<span class="num">{row["fmt"].format(row["latest"])}</span>'
                  if row["latest"] is not None
                  else '<span class="rg-na">n/a</span>')
        body += (
            f'<div class="rg-row"><span><span class="rg-ind">{ui.esc(region)}'
            f'</span><span class="rg-src">{ui.esc(row["source"])}</span></span>'
            f'<span class="rg-num">{latest}</span>'
            f'<span class="rg-num rg-mut">—</span>'
            f'<span class="rg-num rg-mut">{ui.esc(row["period"])}</span>'
            f'<span class="rg-num">{_fmt_delta(d1, row["fmt"])}</span>'
            f'<span class="rg-num">{_fmt_delta(d3, row["fmt"])}</span>'
            f'<span class="rg-num">{_fmt_delta(d12, row["fmt"])}</span></div>')
    st.markdown(
        '<div class="fx-table"><div class="rg-hd"><span>Region</span>'
        '<span class="rg-num">Latest</span><span class="rg-num">Release</span>'
        '<span class="rg-num">Period</span><span class="rg-num">1M Δ</span>'
        '<span class="rg-num">3M Δ</span><span class="rg-num">12M Δ</span>'
        f'</div>{body}</div>', unsafe_allow_html=True)


_CMP_INDICATORS = ["GDP Growth (YoY %)", "Inflation, CPI (YoY %)",
                   "Policy Rate (%)", "Unemployment Rate (%)",
                   "10Y Government Yield (%)", "FX vs USD",
                   "Manufacturing PMI"]


def page_regional_macro():
    st.caption("Indicator set mirrors the macro pack. Live free sources fill what "
               "they can (World Bank, SARB, yfinance); the rest shows its named "
               "target source. No estimation is performed.")

    matrix = macro.wb_latest_matrix()
    tabs = st.tabs(list(macro.REGIONS.keys()))
    for tab, (region, iso) in zip(tabs, macro.REGIONS.items()):
        with tab:
            rows, promoted = _region_rows(region, matrix)
            gh1, gh2 = st.columns([5, 1.3])
            with gh1:
                ui.section("At a glance",
                           "Reference-pack format · this region only")
            with gh2:
                with st.popover("Compare regions", use_container_width=True):
                    ind = st.selectbox("Indicator", _CMP_INDICATORS,
                                       key=f"cmp_ind_{region}")
                    if st.toggle("Load comparison", key=f"cmp_on_{region}"):
                        _comparison_table(ind, matrix)
                    else:
                        st.caption("Opt-in: toggles a cross-region view of "
                                   "one indicator at a time.")
            _pack_grid(rows)
            ui.legend("Period = the measured period · Release dates aren't "
                      "published by the current free APIs (shown — until a "
                      "richer source lands) · Δ in the indicator's own units, "
                      "arithmetic on published observations · n/a* = history "
                      "source pending (BIS / Eurostat / Bundesbank queued)")
            ui.section("3-year historical charts",
                       "Signature commodity · 10Y bond · policy rate · CPI YoY")
            h1, h2 = st.columns(2, gap="large")
            cname, ctk, cunit, cmult = macro.REGION_COMMODITY[region]
            with h1:
                hist = markets.get_history(ctk, "3y")
                if len(hist) > 2:
                    series = hist * cmult if cmult != 1.0 else hist
                    st.plotly_chart(
                        charts.line_chart(series, f"{region} — {cname}",
                                          y_title=cunit, height=300),
                        use_container_width=True,
                        config={"displayModeBar": False},
                        key=f"rc_{region}")
                else:
                    ui.empty_state(f"{cname}: history unavailable from the "
                                   "free proxy right now.")
            bname, btk, bscale, bsrc = macro.REGION_10Y[region]
            with h2:
                if btk == "^TNX":
                    hist = markets.get_history(btk, "3y")
                    if len(hist) > 2:
                        st.plotly_chart(
                            charts.line_chart(hist * bscale,
                                              f"{region} — {bname}",
                                              y_title="%", height=300),
                            use_container_width=True,
                            config={"displayModeBar": False},
                            key=f"rb_{region}")
                    else:
                        ui.empty_state(f"{bname}: yfinance unreachable.")
                elif btk == "SARB_LATEST":
                    r = _sarb_find("r2035", "r209", "2036")
                    if r:
                        st.markdown(
                            f'<div class="kpi"><div class="k-label">{ui.esc(bname)}'
                            f' — latest</div><div class="k-val num">{ui.esc(r["value"])}'
                            f'<span style="font-size:11px;font-weight:400;'
                            f'color:#909288;"> %</span></div>'
                            f'<div class="k-sub">{ui.esc(r["name"])} · '
                            f'{ui.esc(r["date"])} · SARB · a 3Y yield history '
                            f'needs a keyed source</div></div>',
                            unsafe_allow_html=True)
                    else:
                        ui.empty_state("SA benchmark yield not published under "
                                       "a recognised series name.")
                else:
                    st.markdown(
                        f'<div class="metric-block"><div class="metric-label">'
                        f'{ui.esc(bname)}</div><div class="metric-pending">'
                        f'Source: {ui.esc(bsrc)}</div></div>',
                        unsafe_allow_html=True)

            fx_name, fx_tk = macro.REGION_FX[region]
            q = markets.get_quotes([(fx_name, fx_tk)])[0]
            with cols[2]:
                st.markdown(ui.market_card_html(q), unsafe_allow_html=True)

            h3, h4 = st.columns(2, gap="large")
            pending: list[str] = []
            for hcol, registry, kind in ((h3, macro.REGION_POLICY_HIST, "pol"),
                                         (h4, macro.REGION_CPI_HIST, "cpi")):
                label, fkey, yoy, src = registry[region]
                with hcol:
                    s = (fred.history(fkey, 3, yoy=yoy)
                         if fkey and fred.enabled() else None)
                    if s is not None:
                        st.plotly_chart(
                            charts.pack_history(s, f"{region} — {label}",
                                                height=300),
                            use_container_width=True,
                            config={"displayModeBar": False},
                            key=f"r{kind}_{region}")
                        st.caption(src)
                    else:
                        pending.append(
                            f"<b>{ui.esc(label)}</b>: {ui.esc(src)}"
                            + (" — unreachable right now" if fkey else ""))
            if pending:
                st.markdown(
                    '<div class="metric-block"><div class="metric-label">'
                    '3Y monthly histories — source pending</div>'
                    '<div class="metric-pending">' + " · ".join(pending)
                    + "</div></div>",
                    unsafe_allow_html=True)

            if region == "South Africa":
                groups = sarb.get_sa_indicators()
                if groups:
                    ui.section("Live SARB releases", "SARB public Web API · no key")
                    key_rows = groups.get("Key rates & prices") or next(iter(groups.values()))
                    pool = [r for rows in groups.values() for r in rows]
                    fresh = [r for r in key_rows if r["name"] not in promoted]
                    for r in pool:  # backfill slots freed by promoted series
                        if len(fresh) >= 8:
                            break
                        if r["name"] not in promoted and r not in fresh:
                            fresh.append(r)
                    tiles = fresh[:8]
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
                    n_other = sum(1 for rows in groups.values() for r in rows
                                  if r["name"] not in shown)
                    if n_other:
                        with st.expander(f"All published series ({n_other})"):
                            for glabel, rows in groups.items():
                                for r in rows:
                                    if r["name"] in shown:
                                        continue
                                    st.markdown(
                                        f'<div class="cal-row"><span class="cty" style="width:340px;">{ui.esc(r["name"])}</span>'
                                        f'<span class="ev">{ui.esc(glabel)} · {ui.esc(r["agency"])} · {ui.esc(r["date"])}</span>'
                                        f'<span class="cal-val num">{ui.esc(r["value"])} {ui.esc(r["unit"])}</span></div>',
                                        unsafe_allow_html=True)

            ind_pick = st.pills("History (10y)", list(macro.WB_INDICATORS.keys()),
                                default="GDP Growth (YoY %)", key=f"ind_{iso}")
            if ind_pick:
                series = macro.wb_series(iso, macro.WB_INDICATORS[ind_pick])
                if series:
                    st.plotly_chart(
                        charts.bar_years(series, f"{region} — {ind_pick}", y_title="%"),
                        use_container_width=True, config={"displayModeBar": False})
                else:
                    ui.empty_state("World Bank API unreachable for this series.")

    ui.section("Cross-region comparison", "Same indicator, all regions")
    ind_pick = st.pills("Indicator", list(macro.WB_INDICATORS.keys()),
                        default="Inflation, CPI (YoY %)", key="xreg")
    focus = st.pills("Focus region", list(macro.REGIONS.keys()),
                     default="South Africa", key="xreg_focus") or "South Africa"
    if ind_pick:
        frames = {}
        for region, iso in macro.REGIONS.items():
            s = macro.wb_series(iso, macro.WB_INDICATORS[ind_pick])
            if s:
                frames[region] = pd.Series({y: v for y, v in s})
        if frames:
            df = pd.DataFrame(frames).sort_index()
            st.plotly_chart(charts.multi_line(df, ind_pick, y_title="%",
                                              highlight=focus),
                            use_container_width=True, config={"displayModeBar": False})
        else:
            ui.empty_state("No comparison data available.")
