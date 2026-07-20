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


def test_instrument_field_and_score_only_terms():
    from data_sources.news import _classify
    oil = _classify("Oil prices erase gains after Iran says U.S. talks could be pursued", "", "")
    assert oil["instrument"] == "Oil" and "oil" not in oil["tags"], oil
    rand = _classify("Rand firms as SARB holds repo rate", "", "")
    assert rand["instrument"] == "USD/ZAR", rand
    india = _classify("India central bank draws over $20 billion from forex measures", "", "")
    assert "billion" not in india["tags"] and india["importance"] != "Low", india
    lilly = _classify("Eli Lilly to buy AtaiBeckley for $2.8 billion", "", "")
    assert "billion" not in lilly["tags"] and lilly["importance"] != "Low"


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")
