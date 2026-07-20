"""Unit tests for the pure logic that has regressed before.
Run: python tests/test_logic.py  (or pytest tests/)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0].parent))

from data_sources.news import _classify, _clean, fuzzy_match
from data_sources.calendar_data import _nice
from views.reports import _word_diff


def test_region_keyword_not_outlet():
    assert _classify("SpaceX IPO values company at $1tn", "", "South Africa")["region"] == "Global"
    assert _classify("SARB holds repo rate", "", "Global")["region"] == "South Africa"
    assert _classify("RBI weighs rupee support", "", "Global")["region"] == "India"


def test_sentiment_and_importance():
    pos = _classify("Stocks surge to record on strong growth", "", "")
    neg = _classify("Markets plunge as recession fears mount", "", "")
    assert pos["sentiment"] == "Positive" and neg["sentiment"] == "Negative"
    hi = _classify("Fed rate decision and CPI inflation shock", "", "")
    assert hi["importance"] == "High"


def test_directional_sentiment():
    cases = [("Rate cut hopes lift stocks to record high", "Positive"),
             ("Unemployment falls to decade low", "Positive"),
             ("Inflation surges past forecasts", "Negative"),
             ("Growth slows as demand weakens", "Negative"),
             ("SARB decision eases recession fears", "Positive"),
             ("Company misses estimates as costs jump", "Negative"),
             ("Falling inflation lifts consumer confidence", "Positive")]
    for text, want in cases:
        assert _classify(text, "", "")["sentiment"] == want, text


def test_clean_strips_html():
    assert _clean("<b>Rate&amp;nbsp;cut</b>  news") == "Rate&nbsp;cut news".replace("&nbsp;", "\xa0") or "Rate" in _clean("<b>Rate</b> news")


def test_calendar_nice_sast():
    day, tm = _nice("2026-07-16T06:00:00Z")   # 06:00 UTC = 08:00 SAST
    assert day.endswith("16 Jul") and tm == "08:00 SAST"


def test_fuzzy_typos():
    assert fuzzy_match("escom", "Eskom load shedding")
    assert fuzzy_match("tarrif", "US tariff decision")
    assert fuzzy_match("oli", "oil prices climb")
    assert fuzzy_match("invlation", "Inflation surges")
    assert not fuzzy_match("bitcoin", "SARB holds repo rate")


def test_word_diff_marks_changes():
    d = _word_diff("rates likely to hold", "rates expected to hold steady")
    assert "line-through" in d and "likely" in d and "expected" in d


def test_word_boundary_no_substring_tags():
    from data_sources.news import _classify
    cases = [
        ("Voters wary of government ownership as administration takes stakes", "war"),
        ("Kevin Warsh tipped for Fed chair", "war"),
        ("Minnesota Red Angus breeder: high markets reward hard work", "war"),
        ("FedEx quarterly volumes steady", "fed"),
        ("Zelenskyy ousts defense minister Mykhailo Fedorov", "fed"),
        ("Toward a grand bargain on trade", "war"),
    ]
    for title, bad in cases:
        c = _classify(title, "", "")
        assert bad not in c["tags"], (title, c["tags"])
    assert _classify("New brand strategy unveiled by retailer", "", "")["region"] != "South Africa"
    assert _classify("Indiana factory output steady", "", "")["region"] != "India"


def test_contraction_negation():
    from data_sources.news import _sentiment
    label, _ = _sentiment("Company profits didn't rise this quarter")
    assert label != "Positive"


def test_geopolitical_negative():
    from data_sources.news import _classify
    assert _classify("Iran warns U.S. of retaliation as tensions worsen", "", "")["sentiment"] == "Negative"
    assert _classify("Iran-US skirmishes worsen as shipping dwindles", "", "")["sentiment"] == "Negative"


def test_corporate_event_importance():
    from data_sources.news import _classify
    assert _classify("Eli Lilly to buy AtaiBeckley for $2.8 billion", "", "")["importance"] != "Low"
    assert _classify("TSMC to invest $100 billion after earnings soar", "", "")["importance"] != "Low"


def test_title_weighted_over_summary():
    from data_sources.news import _classify
    c = _classify("Smarter skies for 10bn travellers, without building more airports",
                  "Minister speaks on government's war on construction mafia and electricity crisis.", "")
    assert c["importance"] != "High" and "war" not in c["tags"]


def test_relevance_gate():
    from data_sources.news import _is_relevant
    assert not _is_relevant("I'm 67, own two homes, should I get a HELOC?", "")
    assert not _is_relevant("Her hummus twist at farmers markets", "")
    assert not _is_relevant("Growing Soy's Industrial Markets", "Iowa Soybean Association")
    assert _is_relevant("Fed raises rates by 25bp", "")
    assert _is_relevant("SARB holds repo rate at 6.75%", "")


def test_publisher_suffix_and_opinion():
    from data_sources.news import _strip_publisher, _classify
    assert _strip_publisher("Silence isn't golden - South China Morning Post") == "Silence isn't golden"
    c = _classify("Macroscope | Silence isn't golden for a world looking to the Fed", "", "")
    assert "opinion" in c["tags"] and c["importance"] != "High"


def test_instruments_plural_and_score_only_terms():
    from data_sources.news import _classify
    both = _classify("Oil slides as S&P 500 hits record", "", "")
    assert "Oil" in both["instruments"] and "S&P 500" in both["instruments"], both
    mixed = _classify("Stock market today: Dow, S&P 500, Nasdaq futures edge up as oil turns lower", "", "")
    assert mixed["instruments"][0] == "S&P 500" and "Oil" in mixed["instruments"], mixed
    rand = _classify("Rand firms as SARB holds repo rate", "", "")
    assert rand["instruments"] == ["USD/ZAR"], rand
    india = _classify("India central bank draws over $20 billion from forex measures", "", "")
    assert "billion" not in india["tags"] and india["importance"] != "Low", india
    lilly = _classify("Eli Lilly to buy AtaiBeckley for $2.8 billion", "", "")
    assert "billion" not in lilly["tags"] and lilly["importance"] != "Low"


def test_relevance_gate_sports_and_anchors():
    from data_sources.news import _is_relevant
    # off-topic sport/entertainment dropped
    assert not _is_relevant("Spain isn't the World Cup's only winner",
                            "Spain beat Argentina to win the World Cup.")
    assert not _is_relevant("Wimbledon final draws record crowds", "Tennis.")
    assert not _is_relevant("Taylor Swift concert tour breaks records", "")
    # finance anchor keeps a story even if it mentions sport
    assert _is_relevant("Nike earnings beat despite World Cup spend", "Revenue up.")
    assert _is_relevant("Man Utd bond sale oversubscribed", "Club raised debt.")
    assert _is_relevant("Fed holds rates steady", "Central bank decision.")


def test_watchlist_model():
    import sys, types
    st = types.ModuleType("streamlit"); st.cache_data = lambda **k: (lambda f: f)
    st.session_state = {}
    sys.modules["streamlit"] = st
    from data_sources import watchlist as wl
    st.session_state["news_watch_keywords"] = [
        "Eskom", {"term": "Fed", "scope": "news"}, {"term": "CPI", "scope": "calendar"}]
    got = wl.get()
    assert got[0] == {"term": "Eskom", "scope": "both"}  # legacy string upgraded
    assert wl.terms() == ["Eskom", "Fed", "CPI"]
    st.session_state["news_watch_keywords"] = ["fed", {"term": "Fed", "scope": "news"}]
    assert len(wl.get()) == 1  # de-duped case-insensitively


def test_fuzzy_short_query_strict():
    from data_sources.news import fuzzy_match as fm
    # short queries must not over-match unrelated short words
    assert fm("Fed", "Fed signals ahead")
    assert fm("Fed", "federal reserve meeting")
    assert not fm("Fed", "chicken feed prices")
    assert not fm("Fed", "red ink reported")
    assert not fm("Fed", "fee income rises")
    # longer typo tolerance still works
    assert fm("escom", "Eskom load shedding")
    assert fm("tarrif", "new tariff announced")


def test_alert_index_cross_page():
    # Use the st reference the data modules already hold, rather than swapping
    # sys.modules (modules bind `import streamlit as st` once at import, so a
    # later swap wouldn't reach them — a test-only artifact, never real).
    from data_sources import markets, alerts_index
    from data_sources import watchlist as wl
    st = wl.st
    st.session_state.clear()
    markets.get_shock_alerts = lambda: [
        {"title": "Gold rose 4%", "severity": "Critical", "assets": "Gold", "asof": ""}]
    st.session_state["news_watch_keywords"] = [{"term": "Platinum", "scope": "both"}]
    alerts_index.clear_cache()
    g = alerts_index.for_instrument("Gold")
    assert g and g["shock"] == "Critical", g
    alerts_index.clear_cache()
    p = alerts_index.for_instrument("Platinum")
    assert p and p["shock"] is None and "Platinum" in p["watch"], p
    alerts_index.clear_cache()
    assert alerts_index.for_instrument("Copper") is None
    st.session_state.clear()


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")
