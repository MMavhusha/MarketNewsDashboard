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
                        f'<div class="k-val num {cls}">{val}</div>'
                        f'<div class="k-sub">observed · yfinance</div></div>',
                        unsafe_allow_html=True)
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

    ui.section("All pairs at a glance", "Sortable — click a column header · open any pair via the pills above")
    ok_q = [x for x in quotes if x.ok]
    asof = next((x.asof for x in ok_q if x.asof), "latest close")
    win = st.pills("Trend window", ["1M", "6M", "1Y"], default="1M",
                   key="fx_grid_win", label_visibility="collapsed") or "1M"
    if win == "1M":
        trends = {x.name: (x.spark if len(x.spark) > 2 else None) for x in ok_q}
    else:
        per = {"6M": "6mo", "1Y": "1y"}[win]
        trends = {}
        for x in ok_q:
            h = markets.get_history(x.ticker, per)
            trends[x.name] = [float(v) for v in h.tolist()][-60:] if len(h) > 2 else None
    df = pd.DataFrame({
        "Pair": [x.name for x in ok_q],
        f"{win} trend": [trends.get(x.name) for x in ok_q],
        "Last": [round(float(x.price), 4) for x in ok_q],
        "1D %": [round(float(x.change_pct), 2)
                 if x.change_pct is not None else None for x in ok_q],
    })

    def _pcol(v):
        if v is None:
            return "color: #909288"
        return "color: #1E8052" if v >= 0 else "color: #B0212C"

    event = st.dataframe(
        df.style.map(_pcol, subset=["1D %"]),
        hide_index=True, use_container_width=True, row_height=48,
        height=int(48 * (len(ok_q) + 1)) + 6,
        column_config={
            "Pair": st.column_config.TextColumn(width="small"),
            f"{win} trend": st.column_config.LineChartColumn(width="medium"),
            "Last": st.column_config.NumberColumn(format="%.4f", width="small"),
            "1D %": st.column_config.NumberColumn(format="%+.2f%%", width="small"),
        },
        on_select="rerun", selection_mode="single-row", key="fx_grid")
    try:
        rows_sel = event.selection.rows
        if rows_sel:
            chosen = df.iloc[rows_sel[0]]["Pair"]
            if chosen != pick:
                st.session_state["fx_pick"] = chosen
                st.rerun()
    except Exception:
        pass
    ui.legend(f"As at {asof} · 1D % vs prior close · sparklines show the shape "
              "of one month of daily closes, each on its own scale")


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


def page_regional_macro():
    st.caption("Indicator set mirrors the macro pack. Live free sources fill what "
               "they can (World Bank, SARB, yfinance); the rest shows its named "
               "target source. No estimation is performed.")

    matrix = macro.wb_latest_matrix()
    tabs = st.tabs(list(macro.REGIONS.keys()))
    for tab, (region, iso) in zip(tabs, macro.REGIONS.items()):
        with tab:
            promoted: set = set()  # SARB series shown in the headline grid
            cells = []
            for ind in ["GDP Growth (YoY %)", "Inflation, CPI (YoY %)",
                        "Unemployment Rate (%)"]:
                if region == "South Africa" and ind.startswith("Inflation"):
                    cpi = _sarb_find("cpi")
                    if cpi:
                        promoted.add(cpi["name"])
                        cells.append((ind, ui.esc(cpi["value"]),
                                      f'{cpi["date"]} · SARB (monthly)'))
                        continue
                cell = matrix.get(ind, {}).get(region)
                cells.append((ind, f"{cell[1]:,.2f}" if cell else None,
                              f"{cell[0]} · World Bank" if cell else "World Bank unreachable"))
            if region == "South Africa":
                repo = _sarb_repo()
                if repo is not None and "_reachable" in repo:
                    repo = None  # API fine; series name not matched
                if repo:
                    promoted.add(repo["name"])
                cells.append(("Policy Rate (%)", ui.esc(repo["value"]) if repo else None,
                              f'{repo["date"]} · SARB Web API' if repo
                              else "not published under a recognised series name — see the SARB tiles below"))
            elif region == "United States" and fred.enabled():
                f = fred.latest("us_policy")
                cells.append(("Policy Rate (%)", f["value"] if f else None,
                              f'{f["date"]} · {f["label"]}' if f
                              else _PENDING["Policy Rate (%)"]))
            elif region == "Euro Area" and fred.enabled():
                f = fred.latest("ea_policy")
                cells.append(("Policy Rate (%)", f["value"] if f else None,
                              f'{f["date"]} · {f["label"]}' if f
                              else _PENDING["Policy Rate (%)"]))
            else:
                cells.append(("Policy Rate (%)", None, _PENDING["Policy Rate (%)"]))
            if region == "South Africa":
                r209 = _sarb_find("r2035", "r209", "2036")
                if r209:
                    promoted.add(r209["name"])
                    cells.append(("10Y Benchmark Yield (%)", ui.esc(r209["value"]),
                                  f'{r209["name"]} · {r209["date"]} · SARB'))
                else:
                    cells.append(("10Y Government Yield (%)", None,
                                  _PENDING["10Y Government Yield (%)"]))
            elif region == "United States":
                f10 = fred.latest("us_10y") if fred.enabled() else None
                if f10:
                    cells.append(("10Y Government Yield (%)", f10["value"],
                                  f'{f10["date"]} · {f10["label"]}'))
                else:
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
                    elif fkey:  # free source mapped but unreachable/keyless
                        st.markdown(
                            f'<div class="metric-block"><div class="metric-label">'
                            f'{ui.esc(label)} — 3Y history</div>'
                            f'<div class="metric-pending">Unavailable right now '
                            f'· Source: {ui.esc(src)}</div></div>',
                            unsafe_allow_html=True)
                    else:
                        st.markdown(
                            f'<div class="metric-block"><div class="metric-label">'
                            f'{ui.esc(label)} — 3Y history</div>'
                            f'<div class="metric-pending">Source: {ui.esc(src)}'
                            f'</div></div>',
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
