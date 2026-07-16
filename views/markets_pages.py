"""Market pages: Commodities, Currencies, Regional Macro — master-detail
layout (select an instrument, see its full analytical panel)."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components import charts, ui
from data_sources import macro, markets, sarb


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

    hist = markets.get_history(q.ticker, "1y")
    k1, k2, k3, k4 = st.columns(4)
    m1 = _pct(q.spark[-1], q.spark[0]) if len(q.spark) > 1 else None
    kpis = [("1M change", f"{m1:+.2f}%" if m1 is not None else "—",
             ui.chg_cls(m1)),
            ("52W high", q.fmt.format(float(hist.max())) if len(hist) else "—", ""),
            ("52W low", q.fmt.format(float(hist.min())) if len(hist) else "—", ""),
            ("1Y change", (f"{_pct(float(hist.iloc[-1]), float(hist.iloc[0])):+.2f}%"
                           if len(hist) > 1 else "—"),
             ui.chg_cls(_pct(float(hist.iloc[-1]), float(hist.iloc[0]))
                        if len(hist) > 1 else None))]
    for col, (label, val, cls) in zip((k1, k2, k3, k4), kpis):
        with col:
            st.markdown(f'<div class="kpi"><div class="k-label">{label}</div>'
                        f'<div class="k-val num {cls}">{val}</div>'
                        f'<div class="k-sub">observed · yfinance</div></div>',
                        unsafe_allow_html=True)
    if len(hist):
        st.plotly_chart(charts.line_chart(hist, "", y_title=unit, height=320),
                        use_container_width=True, config={"displayModeBar": False},
                        key=key)
    if note:
        st.caption(note)


# ---------------------------------------------------------------- pages
def page_commodities():
    quotes = markets.get_commodities()
    units = {n: u for n, _, u in markets.COMMODITIES}
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

    ui.section("All pairs at a glance", "Latest vs prior session · 1M mini-chart")
    c1, c2 = st.columns(2, gap="medium")
    half = (len(quotes) + 1) // 2
    chunks = [quotes[:half], quotes[half:]]
    for col, chunk in zip((c1, c2), chunks):
        with col, st.container(border=True):
            for x in chunk:
                fig = (charts.sparkline(x.spark, height=32, label="1M")
                       if x.ok and len(x.spark) > 2 else None)
                ui.summary_row(x, fig, key=f"fxrow_{x.ticker}")
            for _ in range(half - len(chunk)):  # keep both panels equal height
                st.markdown('<div style="height:64px;"></div>',
                            unsafe_allow_html=True)


def _sarb_repo():
    for rows in sarb.get_sa_indicators().values():
        for r in rows:
            if "repo" in r["name"].lower():
                return r
    return None


_PENDING = {
    "Policy Rate (%)": "Central bank release / Trading Economics (key)",
    "Manufacturing PMI": "S&P Global / Trading Economics (key)",
    "10Y Government Yield (%)": "Trading Economics / Bloomberg (key)",
}


def page_regional_macro():
    st.caption("Indicator set mirrors the macro pack. Live free sources fill what "
               "they can (World Bank, SARB, yfinance); the rest shows its named "
               "target source. No estimation is performed.")

    matrix = macro.wb_latest_matrix()
    tabs = st.tabs(list(macro.REGIONS.keys()))
    for tab, (region, iso) in zip(tabs, macro.REGIONS.items()):
        with tab:
            cells = []
            for ind in ["GDP Growth (YoY %)", "Inflation, CPI (YoY %)",
                        "Unemployment Rate (%)"]:
                cell = matrix.get(ind, {}).get(region)
                cells.append((ind, f"{cell[1]:,.2f}" if cell else None,
                              f"{cell[0]} · World Bank" if cell else "World Bank unreachable"))
            if region == "South Africa":
                repo = _sarb_repo()
                cells.append(("Policy Rate (%)", ui.esc(repo["value"]) if repo else None,
                              f'{repo["date"]} · SARB Web API' if repo
                              else "SARB Web API unreachable"))
            else:
                cells.append(("Policy Rate (%)", None, _PENDING["Policy Rate (%)"]))
            if region == "United States":
                q10 = markets.get_quotes([("US 10Y", "^TNX")])[0]
                cells.append(("10Y Government Yield (%)",
                              f"{q10.price/10:,.2f}" if q10.ok else None,
                              f"{q10.asof} · CBOE via yfinance" if q10.ok
                              else "yfinance unreachable"))
            else:
                cells.append(("10Y Government Yield (%)", None,
                              _PENDING["10Y Government Yield (%)"]))
            cells.append(("Manufacturing PMI", None, _PENDING["Manufacturing PMI"]))

            cols = st.columns(3)
            for i, (label, value, sub) in enumerate(cells):
                with cols[i % 3]:
                    if value is not None:
                        st.markdown(
                            f'<div class="metric-block"><div class="metric-label">{ui.esc(label)}</div>'
                            f'<div class="metric-value num">{value}</div>'
                            f'<div class="metric-sub">{ui.esc(sub)}</div></div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            f'<div class="metric-block"><div class="metric-label">{ui.esc(label)}</div>'
                            f'<div class="metric-pending">Source: {ui.esc(sub)}</div></div>',
                            unsafe_allow_html=True)
                    st.markdown(" ")
            fx_name, fx_tk = macro.REGION_FX[region]
            q = markets.get_quotes([(fx_name, fx_tk)])[0]
            with cols[2]:
                st.markdown(ui.market_card_html(q), unsafe_allow_html=True)

            if region == "South Africa":
                groups = sarb.get_sa_indicators()
                if groups:
                    ui.section("Live SARB releases", "SARB public Web API · no key")
                    key_rows = groups.get("Key rates & prices") or next(iter(groups.values()))
                    tiles = key_rows[:8]
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
                    other = {g: rows for g, rows in groups.items() if rows is not key_rows}
                    n_other = sum(len(v) for v in other.values()) + max(0, len(key_rows) - 8)
                    if n_other:
                        with st.expander(f"All published series ({n_other})"):
                            for glabel, rows in groups.items():
                                start = 8 if rows is key_rows else 0
                                for r in rows[start:]:
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
    if ind_pick:
        frames = {}
        for region, iso in macro.REGIONS.items():
            s = macro.wb_series(iso, macro.WB_INDICATORS[ind_pick])
            if s:
                frames[region] = pd.Series({y: v for y, v in s})
        if frames:
            df = pd.DataFrame(frames).sort_index()
            st.plotly_chart(charts.multi_line(df, ind_pick, y_title="%"),
                            use_container_width=True, config={"displayModeBar": False})
        else:
            ui.empty_state("No comparison data available.")
