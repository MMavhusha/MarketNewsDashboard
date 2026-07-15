"""Market pages: Commodities, Currencies, Regional Macro."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from components import charts, ui
from data_sources import macro, markets


def page_commodities():
    ui.section("Commodities", "Brent · WTI · Gold · Platinum · Copper · Iron ore · Coal")
    quotes = markets.get_commodities()
    units = {n: u for n, _, u in markets.COMMODITIES}
    cols = st.columns(4)
    for i, q in enumerate(quotes):
        with cols[i % 4]:
            st.markdown(ui.market_card_html(q), unsafe_allow_html=True)
            if q.ok and len(q.spark) > 2:
                st.plotly_chart(charts.sparkline(q.spark), use_container_width=True,
                                config={"displayModeBar": False}, key=f"cspark_{q.ticker}")
            st.caption(units.get(q.name, ""))

    ok = [q for q in quotes if q.ok]
    if ok:
        pick = st.selectbox("Historical chart", [q.name for q in ok])
        tk = next(q.ticker for q in ok if q.name == pick)
        s = markets.get_history(tk, "1y")
        if len(s):
            st.plotly_chart(charts.line_chart(s, f"{pick} — 1 year"),
                            use_container_width=True, config={"displayModeBar": False})

    ui.section("Impact on South Africa's Balance of Payments",
               "Structural trade exposure × latest price moves")
    st.caption("Exposure mapping reflects the well-documented composition of SA trade "
               "(PGMs, gold, coal and iron ore as key exports; crude oil as the dominant "
               "commodity import). Price moves below are live data; net BoP effect in a "
               "given period depends on volumes and the rand.")
    live = {q.name: q for q in quotes}
    alias = {"Iron Ore": "Iron Ore (SGX proxy)", "Coal": "Coal (Newcastle proxy)"}
    for name, tk, side, note in macro.SA_BOP_EXPOSURES:
        q = live.get(name) or live.get(alias.get(name, ""))
        chg = (f'<span class="num {ui.chg_cls(q.change_pct)}">{q.change_pct:+.2f}%</span>'
               if q and q.ok and q.change_pct is not None
               else '<span style="color:#98A2B3;">n/a</span>')
        kind = "green" if side == "Export" else "red"
        st.markdown(
            f'''<div class="cal-row">
            <span class="cty">{ui.esc(name)}</span>
            <span class="ev">{ui.badge(side, kind)} {ui.esc(note)}</span>
            <span class="cal-val">{chg}</span>
            </div>''',
            unsafe_allow_html=True,
        )


def page_currencies():
    ui.section("Currency Dashboard", "Majors vs USD · yfinance (RiscFlash-ready)")
    quotes = markets.get_fx()
    cols = st.columns(4)
    for i, q in enumerate(quotes):
        with cols[i % 4]:
            st.markdown(ui.market_card_html(q), unsafe_allow_html=True)
            if q.ok and len(q.spark) > 2:
                st.plotly_chart(charts.sparkline(q.spark), use_container_width=True,
                                config={"displayModeBar": False}, key=f"fxspark_{q.ticker}")

    ok = [q for q in quotes if q.ok]
    if ok:
        pick = st.selectbox("Pair — 1 year history", [q.name for q in ok])
        tk = next(q.ticker for q in ok if q.name == pick)
        s = markets.get_history(tk, "1y")
        if len(s):
            st.plotly_chart(charts.line_chart(s, f"{pick} — 1 year"),
                            use_container_width=True, config={"displayModeBar": False})

    ui.section("Commentary", "Factual, derived from observed moves")
    movers = sorted((q for q in ok if q.change_pct is not None),
                    key=lambda q: abs(q.change_pct), reverse=True)
    if movers:
        top = movers[0]
        direction = "strengthened" if top.change_pct > 0 else "weakened"
        st.markdown(
            f'<div class="card">The largest move in the tracked set was '
            f'<b>{ui.esc(top.name)}</b>, which {direction} '
            f'<span class="num {ui.chg_cls(top.change_pct)}">{top.change_pct:+.2f}%</span> '
            f'to {top.fmt.format(top.price)} (as at {ui.esc(top.asof or "latest close")}). '
            f'For narrative context, see stories tagged FX under Market News.</div>',
            unsafe_allow_html=True,
        )
    else:
        ui.empty_state("FX data unavailable.")


def page_regional_macro():
    ui.section("Regional Macroeconomic Dashboard",
               "South Africa · United States · Euro Area · United Kingdom · China · India")
    st.caption("Comparison indicators from the World Bank Open Data API (annual, latest "
               "available). Policy rates, PMI and 10Y yields require a keyed provider — "
               "see the source registry below.")

    matrix = macro.wb_latest_matrix()
    tabs = st.tabs(list(macro.REGIONS.keys()))
    for tab, (region, iso) in zip(tabs, macro.REGIONS.items()):
        with tab:
            cols = st.columns(4)
            for i, (ind, per_region) in enumerate(matrix.items()):
                cell = per_region.get(region)
                with cols[i]:
                    if cell:
                        yr, val = cell
                        st.markdown(
                            f'<div class="metric-block"><div class="metric-label">{ui.esc(ind)}</div>'
                            f'<div class="metric-value num">{val:,.2f}</div>'
                            f'<div class="metric-sub">{yr} · World Bank</div></div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            f'<div class="metric-block"><div class="metric-label">{ui.esc(ind)}</div>'
                            f'<div class="metric-value" style="font-size:14px;color:#98A2B3;">unavailable</div>'
                            f'<div class="metric-sub">World Bank</div></div>',
                            unsafe_allow_html=True)
            fx_name, fx_tk = macro.REGION_FX[region]
            q = markets.get_quotes([(fx_name, fx_tk)])[0]
            with cols[3]:
                st.markdown(ui.market_card_html(q), unsafe_allow_html=True)

            ind_pick = st.selectbox("Indicator history (10y)", list(macro.WB_INDICATORS.keys()),
                                    key=f"ind_{iso}")
            series = macro.wb_series(iso, macro.WB_INDICATORS[ind_pick])
            if series:
                st.plotly_chart(charts.bar_years(series, f"{region} — {ind_pick}"),
                                use_container_width=True, config={"displayModeBar": False})
            else:
                ui.empty_state("World Bank API unreachable for this series.")

    ui.section("Cross-region comparison", "Same indicator, all regions")
    ind_pick = st.selectbox("Indicator", list(macro.WB_INDICATORS.keys()), key="xreg")
    frames = {}
    for region, iso in macro.REGIONS.items():
        s = macro.wb_series(iso, macro.WB_INDICATORS[ind_pick])
        if s:
            frames[region] = pd.Series({y: v for y, v in s})
    if frames:
        df = pd.DataFrame(frames).sort_index()
        st.plotly_chart(charts.multi_line(df, ind_pick), use_container_width=True,
                        config={"displayModeBar": False})
    else:
        ui.empty_state("No comparison data available.")

    ui.section("Source registry", "Free source now → target premium source")
    for ind, (free, prem) in macro.PROVIDER_REGISTRY.items():
        st.markdown(
            f'<div class="cal-row"><span class="cty">{ui.esc(ind)}</span>'
            f'<span class="ev">{ui.esc(free)}</span>'
            f'<span class="cal-val" style="width:320px;">→ {ui.esc(prem)}</span></div>',
            unsafe_allow_html=True,
        )
