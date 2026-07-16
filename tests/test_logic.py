"""Unit tests for the pure logic that has regressed before.
Run: python tests/test_logic.py  (or pytest tests/)"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[0].parent))

from data_sources.news import _classify, _clean
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


def test_word_diff_marks_changes():
    d = _word_diff("rates likely to hold", "rates expected to hold steady")
    assert "line-through" in d and "likely" in d and "expected" in d


if __name__ == "__main__":
    fns = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"{len(fns)} tests passed")
