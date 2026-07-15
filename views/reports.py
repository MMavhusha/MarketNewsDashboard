"""Weekly Key Events, Reports (weekly/monthly with real download), Settings."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

from components import report_builder, ui
from data_sources import calendar_data, macro, markets, news

NAMED_SOURCES = [
    ("Bloomberg", "News, markets, corporate actions", "Public RSS wires / yfinance"),
    ("Reuters", "News wires", "Reuters via public RSS"),
    ("International Monetary Fund", "Macro comparisons, WEO", "World Bank Open Data (aligned series)"),
    ("Individual country central banks", "Policy rates, releases", "SARB Web API live (SA); others pending"),
    ("J.P. Morgan", "Research, FX forecasts", "Not available free — commentary derived from observed moves only"),
    ("RiscFlash", "Commodities & currencies", "yfinance (drop-in replacement ready)"),
    ("Trading Economics", "Calendar, indicators", "Forex Factory public feed; TE key upgrades coverage"),
]


def page_weekly_key_events():
    ui.section("Weekly Key Events",
               "This week's most important releases, market events and developments")
    st.caption("Auto-compiled from live sources: high-importance news of the past week, "
               "upcoming calendar releases and the week's largest observed moves. "
               "Replaces the former Key Inflection section.")

    items = [i for i in news.get_news() if i["importance"] == "High"]
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    weekly = [i for i in items if (i["published"] or week_ago) >= week_ago]

    c1, c2 = st.columns([1.6, 1], gap="medium")
    with c1:
        ui.section("Key macro & market stories", "High importance, past 7 days")
        if weekly:
            for item in weekly[:8]:
                ui.news_card(item, news.fmt_time(item["published"]))
        else:
            ui.empty_state("No high-importance stories captured this week (or feeds "
                           "unreachable).")
    with c2:
        ui.section("Week's largest moves", "")
        gainers, losers = markets.get_movers(top_n=4)
        st.markdown('<div class="card">' +
                    "".join(ui.mover_row(q) for q in gainers + losers) +
                    "</div>", unsafe_allow_html=True)

        ui.section("Upcoming releases", "Next 7 days")
        cal = calendar_data.get_calendar()
        high = [e for e in cal if e["importance"] == "High"] or cal
        if high:
            for e in high[:6]:
                ui.cal_row(e)
        else:
            ui.empty_state("Calendar feed unavailable right now.")

    ui.section("Editorial notes", "Commentary for the week")
    notes = st.text_area("Notes (kept for this session; persisted storage can be added "
                         "via a lightweight DB later)",
                         value=st.session_state.get("weekly_notes", ""), height=140)
    st.session_state["weekly_notes"] = notes


def page_reports():
    ui.section("Reporting", "Weekly = Executive Summary only · Monthly = full pack")
    mode = st.radio("Report mode", ["Weekly — Executive Summary", "Monthly — Full pack"],
                    horizontal=True)
    monthly = mode.startswith("Monthly")

    c1, c2 = st.columns([1, 2.4])
    with c1:
        if st.button("Generate report", type="primary"):
            with st.spinner("Compiling report from live data..."):
                st.session_state["report_html"] = report_builder.build_report(monthly)
                st.session_state["report_kind"] = "monthly" if monthly else "weekly"
    with c2:
        st.caption("Generates a self-contained, RisCura-branded HTML file compiled "
                   "from live data. Open it in any browser; use Print, then Save as "
                   "PDF, for distribution.")

    html = st.session_state.get("report_html")
    if html:
        kind = st.session_state.get("report_kind", "weekly")
        fname = f"RisCura_Market_News_{kind}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.html"
        st.download_button("Download report", data=html, file_name=fname,
                           mime="text/html")
        ui.section("Preview", fname)
        st.components.v1.html(html, height=650, scrolling=True)


def page_settings():
    ui.section("Data Sources", "Target premium source → current free stand-in")
    for name, role, standin in NAMED_SOURCES:
        st.markdown(
            f'<div class="cal-row"><span class="cty" style="width:230px;">{ui.esc(name)}</span>'
            f'<span class="ev">{ui.esc(role)}</span>'
            f'<span class="cal-val" style="width:380px;text-align:left;">{ui.esc(standin)}</span></div>',
            unsafe_allow_html=True)
    st.caption("No trend extrapolation, predictive modelling or AI-generated market "
               "predictions anywhere in this application. Each provider lives in "
               "data_sources/ behind a stable interface; swapping one does not touch "
               "the views.")

    ui.section("Secrets", "Streamlit Cloud → App → Settings → Secrets")
    st.markdown(
        '<div class="card">'
        '<code>APP_PASSWORD = "..."</code> — access gate (required in production)<br>'
        '<code>TE_API_KEY = "user:key"</code> — optional; upgrades calendar to full '
        'country coverage incl. SA/India</div>',
        unsafe_allow_html=True,
    )
    st.markdown(" ")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Force refresh all data"):
            markets.clear_caches()
            st.rerun()
    with c2:
        st.caption("Cache TTLs — markets 5 min · news 15 min · announcements 30 min · "
                   "calendar 60 min · macro 24 h.")
