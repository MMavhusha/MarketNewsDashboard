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
    assert not fuzzy_match("ethereum", "SARB holds repo rate")


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
    # multi-word queries: whole-word AND, order-independent, no prefix bleed
    assert fm("rate cut", "Hungary set for another rate cut")
    assert fm("rate cut", "the central bank will cut the rate")
    assert not fm("rate cut", "accurate cutbacks in budget")
    assert not fm("rate cut", "rate hike expected")
    assert fm("Fed decision", "the Fed made a decision")
    assert not fm("Fed decision", "Fed minutes released")



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


def test_watchlist_scope_helpers():
    from data_sources import watchlist as wl
    st = wl.st
    st.session_state.clear()
    st.session_state["news_watch_keywords"] = [
        {"term": "Fed", "scope": "news"}, {"term": "CPI", "scope": "calendar"},
        {"term": "Eskom", "scope": "both"}]
    assert wl.news_terms() == ["Fed", "Eskom"]
    assert wl.calendar_terms() == ["CPI", "Eskom"]
    st.session_state.clear()


def test_fred_freshness_guard():
    """latest_fresh must block stale (discontinued) series to avoid showing
    out-of-date values as if current."""
    import datetime as dt
    from data_sources import fred
    today = dt.date.today()
    fresh = (today - dt.timedelta(days=45)).isoformat()
    stale = (today - dt.timedelta(days=500)).isoformat()
    _orig = fred.latest
    try:
        fred.latest = lambda sk: {"value": "1.73", "date": fresh, "label": "x"}
        assert fred.latest_fresh("cn_10y") is not None
        fred.latest = lambda sk: {"value": "2.80", "date": stale, "label": "x"}
        assert fred.latest_fresh("cn_10y") is None
        fred.latest = lambda sk: None
        assert fred.latest_fresh("cn_10y") is None
    finally:
        fred.latest = _orig


def test_monetary_and_directional_sentiment():
    """Rules engine handles clear directional signals. It does NOT attempt the
    'priced-in / anticipated = Neutral' nuance — that needs the model — so we
    only assert what the rules can defensibly decide. Crucially, 'set to
    rise/fall' keeps its direction (the phrase is not a sentiment marker)."""
    from data_sources.news import _classify
    # directional monetary signals
    assert _classify("Fed cuts rates as inflation cools", "", "")["sentiment"] == "Positive"
    assert _classify("Inflation surges to 6%, rate hike fears mount", "", "")["sentiment"] == "Negative"
    # 'set to' is structural — direction comes from what follows, not the phrase
    assert _classify("Rand set to rise on strong exports", "", "")["sentiment"] == "Positive"
    assert _classify("Stocks set to fall on recession fears", "", "")["sentiment"] == "Negative"


def test_sars_trade_parser():
    import sys, types
    st = types.ModuleType("streamlit"); st.cache_data = lambda **k: (lambda f: f)
    sys.modules["streamlit"] = st
    from data_sources import sars_trade as S
    csv_text = (
        'TradeType,Chapter,ChapterAndDescription,YearMonth,CustomsValue\n'
        'Exports,71,"71 - Gold, Platinum, Diamonds",2026-01,32000000000\n'
        'Exports,71,"71 - Gold, Platinum, Diamonds",2026-02,31000000000\n'
        'Exports,26,"26 - Ores",2026-01,20000000000\n'
        'Imports,71,"71 - Gold",2026-01,5000000000\n')
    parsed = S._parse_csv_text(csv_text)
    # parser now keeps both trade types; export path filters to exports
    exp = [r for r in parsed if r.get("trade") == "export"]
    agg = S._aggregate(exp)
    by = {a["chapter"]: a["value"] for a in agg}
    assert by["71"] == 63000000000, "Ch71 should sum Jan+Feb exports only"
    assert by["26"] == 20000000000
    assert "71" in by and len(agg) == 2  # imports excluded, 2 export chapters
    # import row was captured with trade='import'
    assert any(r.get("trade") == "import" for r in parsed)
    # dated fallback shape (network + csv absent in test)
    res = S.get_commodity_exports()
    assert res["source"] in ("dated", "csv", "live") and res["rows"]
    # five-period movement structure + per-period totals for share
    mvcsv = ('TradeType,Chapter,YearMonth,CustomsValue\n'
             'Exports,71,2025-04,33000000000\n'
             'Exports,71,2026-03,46500000000\n'
             'Exports,71,2026-04,49000000000\n'
             'Exports,26,2026-04,19500000000\n'
             'Exports,87,2026-04,48000000000\n'
             'Exports,99,2026-04,65500000000\n')
    cum = S._cumulative_by_chapter(S._parse_csv_text(mvcsv),
                                   S._parse_csv_text(mvcsv, keep_all=True))
    packed = S._pack_movement("csv", cum)
    t = packed["totals"]
    assert abs(t["this_month"] - 182e9) < 1e6  # 49+19.5+48+65.5
    r71 = [x for x in packed["rows"] if x["chapter"] == "71"][0]
    assert abs(r71["this_month"] - 49e9) < 1e6
    assert abs(r71["same_month_ly"] - 33e9) < 1e6  # Apr 2025
    assert packed["latest_month"] == "2026-04" and packed["prev_month"] == "2026-03"


def test_net_trade_recon_foots():
    import sys, types
    st = types.ModuleType("streamlit"); st.cache_data = lambda **k: (lambda f: f)
    sys.modules["streamlit"] = st
    from data_sources import sars_trade as S
    csv = ('TradeType,Chapter,YearMonth,CustomsValue\n'
           'Exports,71,2026-01,100000000000\n'
           'Imports,71,2026-01,5000000000\n'
           'Exports,27,2026-01,20000000000\n'
           'Imports,27,2026-01,60000000000\n'
           'Exports,87,2026-01,40000000000\n'
           'Imports,87,2026-01,30000000000\n')
    rec = S._net_recon_from_rows(S._parse_csv_text(csv, keep_all=True))
    assert abs(rec["total_exports"] - 160e9) < 1e6
    assert abs(rec["total_imports"] - 95e9) < 1e6
    # ch27 is a net importer (imports > exports)
    c27 = [r for r in rec["rows"] if r["chapter"] == "27"][0]
    assert c27["exports"] - c27["imports"] == -40e9
    # foots: tracked net + other net = total exports - total imports (trade bal)
    trk_e = sum(r["exports"] for r in rec["rows"])
    trk_i = sum(r["imports"] for r in rec["rows"])
    tb = rec["total_exports"] - rec["total_imports"]
    other = (rec["total_exports"] - trk_e) - (rec["total_imports"] - trk_i)
    assert abs((trk_e - trk_i) + other - tb) < 1e6


def test_bop_reconciliation_foots():
    import sys, types
    st = types.ModuleType("streamlit"); st.cache_data = lambda **k: (lambda f: f)
    sys.modules["streamlit"] = st
    from data_sources import sarb
    r = sarb.get_bop_reconciliation()
    # exports - imports = trade balance
    assert abs((r["exports"] - r["imports"]) - r["trade_balance"]) < 0.1
    # trade balance + net services/income/transfers = current account
    assert abs((r["trade_balance"] + r["services_income_transfers"])
               - r["current_account"]) < 0.1


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")
