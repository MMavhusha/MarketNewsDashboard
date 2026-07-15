"""Antonie's Weekly Key Events, Reports (weekly/monthly), Settings."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import streamlit as st

from components import ui
from data_sources import calendar_data, markets, news


def page_weekly_key_events():
    ui.section("Antonie's Weekly Key Events",
               "This week's most important releases, market events and developments")
    st.caption("Auto-compiled from live sources: high-importance news of the past week, "
               "upcoming calendar releases and the week's largest observed moves. "
               "Replaces the former Key Inflection section. Add editorial notes below.")

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
            ui.empty_state("Calendar provider not configured.")

    ui.section("Antonie's notes", "Editorial commentary for the week")
    notes = st.text_area("Notes (kept for this session; persisted storage can be added "
                         "via a lightweight DB later)",
                         value=st.session_state.get("antonie_notes", ""), height=140)
    st.session_state["antonie_notes"] = notes


def page_reports():
    ui.section("Reporting", "Weekly = Executive Summary only · Monthly = full pack")
    mode = st.radio("Report mode", ["Weekly — Executive Summary", "Monthly — Full pack"],
                    horizontal=True)
    st.caption("Compose the report on screen, then use the browser's Print → Save as "
               "PDF for distribution. Automated scheduled PDF generation can be added "
               "as a follow-on (e.g. GitHub Action).")

    from views import core, markets_pages  # local import to avoid cycles

    st.markdown(
        f'''<div class="topbar"><div>
        <div class="tb-title">RisCura Market News — '
        f'{"Weekly Executive Summary" if mode.startswith("Weekly") else "Monthly Full Pack"}</div>
        <div class="tb-meta">Produced {datetime.now(timezone.utc).strftime("%d %B %Y")} ·
        Sources as attributed per section</div></div></div>''',
        unsafe_allow_html=True,
    )

    core.page_executive_summary()
    if mode.startswith("Monthly"):
        st.divider()
        core.page_shock_alerts()
        st.divider()
        core.page_announcements()
        st.divider()
        core.page_calendar()
        st.divider()
        markets_pages.page_commodities()
        st.divider()
        markets_pages.page_currencies()
        st.divider()
        markets_pages.page_regional_macro()
        st.divider()
        page_weekly_key_events()


def page_settings():
    ui.section("Settings", "Providers, keys and refresh")
    st.markdown(
        '<div class="card">'
        '<b>Data providers</b><br>'
        'Target premium sources per spec: Bloomberg, Reuters, IMF, individual central '
        'banks, J.P. Morgan, RiscFlash (commodities & currencies), Trading Economics. '
        'Current free stand-ins: yfinance (markets/FX/commodities), public RSS wires '
        '(news), World Bank (regional macro), Trading Economics guest (calendar). '
        'Each lives in <code>data_sources/</code> behind a stable interface — swapping a '
        'provider does not touch the views.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(" ")
    st.markdown(
        '<div class="card"><b>Secrets (Streamlit Cloud → App → Settings → Secrets)</b><br>'
        '<code>APP_PASSWORD = "..."</code> — access gate (required in production)<br>'
        '<code>TE_API_KEY = "user:key"</code> — Trading Economics calendar (optional)'
        '</div>',
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
