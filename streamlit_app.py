"""RisCura Market News — Streamlit entry point."""
from __future__ import annotations

from pathlib import Path

import streamlit as st
from streamlit_option_menu import option_menu

st.set_page_config(
    page_title="RisCura Market News",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

from auth import check_password  # noqa: E402
from data_sources import markets  # noqa: E402
from views import core, markets_pages, reports  # noqa: E402


def inject_css():
    css = Path(__file__).parent.joinpath("assets", "styles.css").read_text()
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)


PAGES = {
    # Ordered for a PM's morning workflow: brief -> what needs attention ->
    # what's coming -> narrative -> corporate actions -> markets detail ->
    # slower context -> weekly synthesis -> outputs -> admin.
    "Executive Summary": ("speedometer2", core.page_executive_summary,
                          "Morning briefing · overnight moves, top stories, alerts"),
    "Alerts": ("bell", core.page_alerts,
               "Watchlist keyword alerts · shock threshold breaches"),
    "Calendar": ("calendar3", core.page_calendar,
                 "Scheduled economic releases and market holidays"),
    "Market News": ("newspaper", core.page_market_news,
                    "Wire coverage with sentiment and importance · This-week view"),
    "Announcements": ("megaphone", core.page_announcements,
                              "Dividends · leadership · earnings · M&A · capital actions"),
    "Currencies": ("currency-exchange", markets_pages.page_currencies,
                   "Majors vs USD · select a pair for its full panel"),
    "Commodities": ("minecart-loaded", markets_pages.page_commodities,
                    "Spec instruments · select one for its full panel · SA BoP impact"),
    "Regional Macro": ("globe2", markets_pages.page_regional_macro,
                       "SA · US · Euro Area · UK · China · India · Japan"),
    "Reports": ("file-earmark-text", reports.page_reports,
                "Weekly executive summary · monthly full pack · HTML download"),
    "Settings": ("gear", reports.page_settings,
                 "Providers, keys, refresh"),
}


def sidebar() -> str:
    with st.sidebar:
        logo = Path(__file__).parent / "assets" / "riscura_logo.svg"
        if logo.exists():  # brand rule: always the official vector wordmark
            st.image(str(logo), width=132)
            st.markdown('<div class="sb-sub">MARKET NEWS</div>',
                        unsafe_allow_html=True)
        else:  # fallback until the official asset is committed to assets/
            st.markdown(
                '<div class="sb-brand"><span class="wordmark">RISCURA</span>'
                '<span class="obar"></span></div>'
                '<div class="sb-sub">MARKET NEWS</div>',
                unsafe_allow_html=True,
            )
        keys = list(PAGES.keys())
        pending = st.session_state.pop("nav_to", None)
        choice = option_menu(
            None, keys,
            icons=[v[0] for v in PAGES.values()],
            default_index=0,
            manual_select=keys.index(pending) if pending in keys else None,
            key="main_nav",
            styles={
                "container": {"padding": "0", "background-color": "transparent"},
                "icon": {"font-size": "13px", "color": "#FF671D"},
                "nav-link": {
                    "font-family": "Lato, sans-serif",
                    "font-size": "12.5px", "font-weight": "500",
                    "color": "#212322", "padding": "7px 14px",
                    "border-radius": "7px", "margin": "2px 8px",
                    "--hover-color": "#FFF1E9",
                },
                "nav-link-selected": {
                    "background-color": "#FF671D", "color": "#FFFFFF",
                    "font-weight": "600",
                },
            },
        )
        if st.button("↻ Refresh data", use_container_width=True):
            markets.clear_caches()
            with st.spinner("Refreshing market data…"):
                try:  # pre-warm so the page re-renders with fresh data at once
                    qs = markets.get_summary_strip()
                    markets.get_intraday([(q.name, q.ticker) for q in qs])
                except Exception:
                    pass
            st.rerun()
    return choice


PAGE_TITLES = {"Announcements": "Company Announcements"}


def topbar(page: str):
    subtitle = PAGES[page][2]
    page = PAGE_TITLES.get(page, page)
    st.markdown(
        f'''<div class="pagehead">
        <div><span class="ph-accent"></span>
        <div class="ph-title">{page}</div>
        <div class="ph-sub">{subtitle}</div></div>
        <div class="ph-meta"><span class="live-dot"></span>Last refresh
        <b>{markets.last_refresh()}</b><br>
        yfinance · public RSS wires · World Bank · SARB · FRED · Forex Factory</div>
        </div>''',
        unsafe_allow_html=True,
    )


def main():
    inject_css()
    if not check_password():
        return
    if st.session_state.pop("_auth_warn", False):
        st.warning("No APP_PASSWORD secret configured — the app is running "
                   "unprotected (development mode).", icon="🔓")
    from data_sources import app_state
    app_state.ensure_loaded()
    page = sidebar()
    topbar(page)
    PAGES[page][1]()


if __name__ == "__main__":
    main()
