"""Page-render smoke tests.

These exist because two bugs this project shipped — an undefined ``cols[2]``
and a ``_detail_panel`` name collision with the wrong signature — were both
invisible to the logic tests and only surfaced when a user opened the page.
A smoke test that actually *invokes* every page function against a mocked
Streamlit would have caught both at build time.

The mock is deliberately permissive: it is not testing Streamlit, only that
each page's Python executes end-to-end (names resolve, signatures match,
no attribute errors) with data sources stubbed to empty/typical values.
Run: python tests/test_smoke.py
"""
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _make_streamlit_stub():
    """A MagicMock-based streamlit whose layout primitives return usable
    context managers and whose widget calls return benign defaults."""
    st = MagicMock(name="streamlit")

    class _Ctx:
        """A layout context (column/container/tab) that also proxies widget
        calls — Streamlit lets you do both `with col:` and `col.button(...)`."""
        def __enter__(self):
            return st
        def __exit__(self, *a):
            return False
        def __getattr__(self, name):
            return getattr(st, name)

    def _cols(spec, **k):
        n = spec if isinstance(spec, int) else len(spec)
        return [_Ctx() for _ in range(n)]

    st.columns.side_effect = _cols
    st.container.side_effect = lambda *a, **k: _Ctx()
    st.expander.side_effect = lambda *a, **k: _Ctx()
    st.popover.side_effect = lambda *a, **k: _Ctx()
    st.sidebar = _Ctx()
    st.spinner.side_effect = lambda *a, **k: _Ctx()
    st.tabs.side_effect = lambda labels, **k: [_Ctx() for _ in labels]
    st.form.side_effect = lambda *a, **k: _Ctx()
    # widgets return benign values
    st.selectbox.side_effect = lambda label, options=None, **k: (
        (options[0] if options else None))
    st.pills.side_effect = lambda label, options=None, **k: (
        k.get("default") if k.get("default") is not None
        else (options[0] if options else None))
    st.radio.side_effect = lambda label, options=None, **k: (
        options[0] if options else None)
    st.multiselect.side_effect = lambda *a, **k: []
    st.text_input.side_effect = lambda *a, **k: ""
    st.toggle.side_effect = lambda *a, **k: False
    st.checkbox.side_effect = lambda *a, **k: False
    st.button.side_effect = lambda *a, **k: False
    st.download_button.side_effect = lambda *a, **k: False
    st.slider.side_effect = lambda *a, **k: k.get("value", 0)
    st.number_input.side_effect = lambda *a, **k: k.get("value", 0)
    st.session_state = {}
    st.secrets = types.SimpleNamespace(get=lambda k, d=None: None)
    st.cache_data = lambda **k: (lambda f: f)
    st.cache_resource = lambda **k: (lambda f: f)
    st.components = types.SimpleNamespace(v1=types.SimpleNamespace(
        html=lambda *a, **k: None))
    return st


def _stub_data_sources():
    """Force every network-backed fetch to its empty/typical shape so pages
    render their 'unavailable' branches without touching the network."""
    from data_sources import markets, news, calendar_data
    import pandas as pd

    markets.get_summary_strip = lambda: []
    markets.get_intraday = lambda pairs: {}
    markets.get_movers = lambda **k: ([], [])
    markets.get_weekly_movers = lambda **k: ([], [])
    markets.get_shock_alerts = lambda: []
    markets.get_quotes = lambda items, **k: [
        markets.Quote(name=i[0], ticker=i[1]) for i in items]
    markets.get_history = lambda *a, **k: pd.Series(dtype=float)
    markets.last_refresh = lambda: "—"
    markets.get_thresholds = lambda: markets.DEFAULT_THRESHOLDS
    news.get_news = lambda **k: []
    news.get_announcements = lambda **k: []
    calendar_data.get_calendar = lambda **k: []


def run():
    st = _make_streamlit_stub()
    sys.modules["streamlit"] = st
    _stub_data_sources()

    from views import core, markets_pages, reports
    pages = [
        ("Executive Summary", core.page_executive_summary),
        ("Market News", core.page_market_news),
        ("Announcements", core.page_announcements),
        ("Calendar & Alerts", core.page_calendar),
        ("Currencies", markets_pages.page_currencies),
        ("Commodities", markets_pages.page_commodities),
        ("Regional Macro", markets_pages.page_regional_macro),
        ("Reports", reports.page_reports),
        ("Settings", reports.page_settings),
    ]
    failures = []
    for name, fn in pages:
        st.session_state.clear()
        try:
            fn()
            print(f"PASS render {name}")
        except Exception as e:  # noqa: BLE001
            import traceback
            failures.append((name, e))
            print(f"FAIL render {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
    if failures:
        raise SystemExit(f"\n{len(failures)} page(s) failed to render")
    print(f"\n{len(pages)} pages render cleanly")


if __name__ == "__main__":
    run()
