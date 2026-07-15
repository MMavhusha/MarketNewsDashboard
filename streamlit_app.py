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
    "Executive Summary": ("speedometer2", core.page_executive_summary),
    "Market News": ("newspaper", core.page_market_news),
    "Market Shock Alerts": ("exclamation-triangle", core.page_shock_alerts),
    "Company Announcements": ("megaphone", core.page_announcements),
    "Economic Calendar": ("calendar3", core.page_calendar),
    "Commodities": ("minecart-loaded", markets_pages.page_commodities),
    "Currencies": ("currency-exchange", markets_pages.page_currencies),
    "Regional Macro": ("globe2", markets_pages.page_regional_macro),
    "Weekly Key Events": ("star", reports.page_weekly_key_events),
    "Reports": ("file-earmark-text", reports.page_reports),
    "Settings": ("gear", reports.page_settings),
}


def sidebar() -> str:
    with st.sidebar:
        st.markdown(
            '<div class="sb-brand"><span class="logo">Ris<span>Cura</span></span></div>'
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
                "icon": {"font-size": "13px", "color": "#9FBAD0"},
                "nav-link": {
                    "font-size": "12.5px", "font-weight": "500",
                    "color": "#D8E6EE", "padding": "7px 14px",
                    "border-radius": "7px", "margin": "2px 8px",
                    "--hover-color": "#1F3864",
                },
                "nav-link-selected": {
                    "background-color": "#FF671D", "color": "#FFFFFF",
                    "font-weight": "600",
                },
            },
        )
        st.markdown(
            f'<div class="sb-sub" style="margin-top:14px;">'
            f'<span class="live-dot"></span>Free-tier live data<br>'
            f'Refreshed {markets.last_refresh()}</div>',
            unsafe_allow_html=True,
        )
        if st.button("↻ Refresh data", use_container_width=True):
            markets.clear_caches()
            st.rerun()
    return choice


def topbar(page: str):
    st.markdown(
        f'''<div class="topbar">
        <div class="tb-title">{page}</div>
        <div class="tb-meta"><span class="live-dot"></span>Last refresh
        <b>{markets.last_refresh()}</b><br>
        Sources: yfinance · public RSS wires · World Bank · SARB · Forex Factory</div>
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
    page = sidebar()
    topbar(page)
    PAGES[page][1]()


if __name__ == "__main__":
    main()
