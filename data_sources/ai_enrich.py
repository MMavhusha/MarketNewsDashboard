"""Optional AI classification layer (Claude API).

If ANTHROPIC_API_KEY is present in Streamlit Secrets, story sentiment,
importance, region and asset tagging — plus the hero's one-line
"why it matters" — are produced by a language model instead of keyword
rules. This is classification and summarisation of published text only:
no forecasting, no market prediction. On any failure the keyword rules
stand unchanged.
"""
from __future__ import annotations

import json

import requests
import streamlit as st

_MODEL = "claude-haiku-4-5"
_URL = "https://api.anthropic.com/v1/messages"

_SENT = {"Positive", "Negative", "Neutral"}
_IMP = {"High", "Medium", "Low"}
_REG = {"South Africa", "United States", "Euro Area", "United Kingdom",
        "China", "India", "Japan", "Global"}
_AST = {"Equities", "Rates & Bonds", "FX", "Commodities", "Crypto", "Macro"}


def _key() -> str | None:
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except FileNotFoundError:
        return None


def enabled() -> bool:
    return bool(_key())


@st.cache_data(ttl=900, show_spinner=False)
def classify_batch(headlines: tuple[tuple[str, str], ...]) -> dict[int, dict]:
    """headlines: ((title, summary), ...) -> {index: fields}. {} on failure."""
    key = _key()
    if not key or not headlines:
        return {}
    lines = "\n".join(f"{i}. {t} — {s[:160]}" for i, (t, s) in enumerate(headlines))
    prompt = (
        "You classify financial news for an institutional dashboard. For each "
        "numbered story return sentiment (Positive/Negative/Neutral, meaning "
        "the tone for markets described, not a forecast), importance "
        "(High/Medium/Low for institutional investors), region (South Africa/"
        "United States/Euro Area/United Kingdom/China/India/Japan/Global) and "
        "asset (Equities/Rates & Bonds/FX/Commodities/Crypto/Macro). For story "
        "0 only, add why: ONE factual sentence on why it matters to investors, "
        "no predictions. Respond with ONLY a JSON array of objects with keys "
        "i, sentiment, importance, region, asset, and why (story 0 only).\n\n"
        + lines)
    try:
        r = requests.post(
            _URL, timeout=25,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": _MODEL, "max_tokens": 2000,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        text = "".join(b.get("text", "") for b in r.json().get("content", []))
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
        out = {}
        for row in json.loads(text):
            i = int(row.get("i", -1))
            fields = {}
            if row.get("sentiment") in _SENT:
                fields["sentiment"] = row["sentiment"]
            if row.get("importance") in _IMP:
                fields["importance"] = row["importance"]
                fields["score"] = {"High": 5, "Medium": 3, "Low": 1}[row["importance"]]
            if row.get("region") in _REG:
                fields["region"] = row["region"]
            if row.get("asset") in _AST:
                fields["asset"] = row["asset"]
            if i == 0 and isinstance(row.get("why"), str) and row["why"].strip():
                fields["why"] = row["why"].strip()[:220]
            if i >= 0 and fields:
                out[i] = fields
        return out
    except Exception:
        return {}
