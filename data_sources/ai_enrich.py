"""AI classification layer — MODEL-PRIMARY with a tiered provider chain.

Chain: Anthropic (if ANTHROPIC_API_KEY) → Gemini via its OpenAI-compatible
endpoint (LLM_API_KEY, the default primary) → Groq free tier (GROQ_API_KEY)
→ and if every tier fails, the keyword rules engine's verdicts stand
unchanged. Classification and summarisation of published text only: no
forecasting, no market prediction. Every real call is audited with the
provider that served it.
"""
from __future__ import annotations

import json
import time as _time

import requests
import streamlit as st

_ANTHROPIC_MODEL = "claude-haiku-4-5"
_ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
_GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/openai"
_GEMINI_MODEL = "gemini-2.5-flash"
_GROQ_BASE = "https://api.groq.com/openai/v1"
_GROQ_MODEL = "llama-3.3-70b-versatile"

_SENT = {"Positive", "Negative", "Neutral"}
_IMP = {"High", "Medium", "Low"}
_REG = {"South Africa", "United States", "Euro Area", "United Kingdom",
        "China", "India", "Japan", "Global"}
_AST = {"Equities", "Rates & Bonds", "FX", "Commodities", "Crypto", "Macro"}
_INSTR = {"Oil", "Gold", "Copper", "Platinum", "Iron Ore", "Coal",
          "USD/ZAR", "EUR/USD", "USD/JPY", "Bitcoin", "S&P 500", "NASDAQ",
          "FTSE 100", "JSE ALSI"}
_INSTR = {"Oil", "Gold", "Copper", "Platinum", "Iron Ore", "Coal",
          "USD/ZAR", "EUR/USD", "USD/JPY", "Bitcoin", "S&P 500",
          "NASDAQ", "FTSE 100", "JSE ALSI"}


def _secret(name: str) -> str | None:
    try:
        v = st.secrets.get(name)
        if v:
            return v
    except FileNotFoundError:
        pass
    import os
    return os.environ.get(name) or None


def providers() -> list[dict]:
    """Ordered provider chain. kind: 'anthropic' | 'openai'."""
    chain: list[dict] = []
    if _secret("ANTHROPIC_API_KEY"):
        chain.append({"label": f"Anthropic · {_ANTHROPIC_MODEL}",
                      "kind": "anthropic", "key": _secret("ANTHROPIC_API_KEY")})
    if _secret("LLM_API_KEY"):
        base = (_secret("LLM_API_BASE") or _GEMINI_BASE).rstrip("/")
        model = _secret("LLM_MODEL") or _GEMINI_MODEL
        from urllib.parse import urlparse
        chain.append({"label": f"{urlparse(base).netloc} · {model}",
                      "kind": "openai", "key": _secret("LLM_API_KEY"),
                      "base": base, "model": model})
    if _secret("GROQ_API_KEY"):
        model = _secret("GROQ_MODEL") or _GROQ_MODEL
        chain.append({"label": f"api.groq.com · {model}", "kind": "openai",
                      "key": _secret("GROQ_API_KEY"),
                      "base": _GROQ_BASE, "model": model})
    return chain


def enabled() -> bool:
    return bool(providers())


def provider_label() -> str:
    chain = [p["label"] for p in providers()]
    return " → ".join(chain + ["rules"]) if chain else "off (rules only)"


def _prompt(headlines, hero: bool) -> str:
    lines = "\n".join(f"{i}. {t} — {s[:240]}"
                      for i, (t, s) in enumerate(headlines))
    hero_line = ("For story 0 only, add why: ONE factual sentence on why it "
                 "matters to investors, no predictions. " if hero else "")
    return (
        "You classify financial news for an institutional portfolio-"
        "management dashboard. Weigh the summary's facts equally with the "
        "title — headlines often understate. For each numbered story return: "
        "sentiment (Positive/Negative/Neutral — the market RISK TONE of what "
        "is described, not a forecast; active military conflict, attacks, "
        "escalation or sanctions are Negative unless the story is clearly "
        "about de-escalation succeeding), importance (High = central bank "
        "decisions or surprises, major macro data for large economies, armed "
        "conflict or sanctions affecting energy or supply chains, systemic "
        "credit events, corporate events of $10bn+ or mega-cap earnings; "
        "Medium = notable single-company or single-country developments with "
        "market impact; Low = minor items, opinion pieces, advice content), "
        "region (South Africa/United States/Euro Area/United Kingdom/China/"
        "India/Japan/Global), asset (Equities/Rates & Bonds/FX/Commodities/"
        "Crypto/Macro), instruments (a list, possibly empty, of the tracked "
        "instruments this story is MATERIALLY about — judge from context, "
        "not word presence; a story can be about several. Choose only "
        "from: Oil, Gold, Copper, Platinum, Iron Ore, Coal, USD/ZAR, "
        "EUR/USD, USD/JPY, Bitcoin, S&P 500, NASDAQ, FTSE 100, JSE ALSI) "
        "and relevant (true/false: is this market, economy or "
        "corporate news useful to institutional portfolio managers? Consumer "
        "personal-finance advice, lifestyle, sport, entertainment and "
        "local/agri-trade content are false) and instrument (the single most-"
        "affected traded instrument if clearly identifiable, exactly one of: "
        "Oil, Gold, Copper, Platinum, Iron Ore, Coal, USD/ZAR, EUR/USD, "
        "USD/JPY, Bitcoin, S&P 500, NASDAQ, FTSE 100, JSE ALSI; else null). "
        + hero_line +
        "Respond with ONLY a JSON array of objects with keys i, sentiment, "
        "importance, region, asset, relevant, instrument" +
        (", and why (story 0 only)" if hero else "") + ".\n\n" + lines)


def _call(p: dict, prompt: str) -> str:
    if p["kind"] == "anthropic":
        r = requests.post(
            _ANTHROPIC_URL, timeout=25,
            headers={"x-api-key": p["key"],
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": _ANTHROPIC_MODEL, "max_tokens": 3000,
                  "messages": [{"role": "user", "content": prompt}]})
        r.raise_for_status()
        return "".join(b.get("text", "") for b in r.json().get("content", []))
    r = requests.post(
        f"{p['base']}/chat/completions", timeout=25,
        headers={"Authorization": f"Bearer {p['key']}",
                 "content-type": "application/json"},
        json={"model": p["model"], "max_tokens": 3000,
              "messages": [{"role": "user", "content": prompt}]})
    r.raise_for_status()
    return (r.json().get("choices") or [{}])[0].get(
        "message", {}).get("content", "") or ""


def _parse(text: str, hero: bool) -> dict[int, dict]:
    text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```")
    out: dict[int, dict] = {}
    for row in json.loads(text):
        i = int(row.get("i", -1))
        fields: dict = {}
        if row.get("sentiment") in _SENT:
            fields["sentiment"] = row["sentiment"]
        if row.get("importance") in _IMP:
            fields["importance"] = row["importance"]
            fields["score"] = {"High": 5, "Medium": 3, "Low": 1}[row["importance"]]
        if row.get("region") in _REG:
            fields["region"] = row["region"]
        if row.get("asset") in _AST:
            fields["asset"] = row["asset"]
        if row.get("instrument") in _INSTR:
            fields["instrument"] = row["instrument"]
        if isinstance(row.get("instruments"), list):
            fields["instruments"] = [x for x in row["instruments"]
                                     if x in _INSTR][:3]
        if isinstance(row.get("relevant"), bool) and not row["relevant"]:
            fields["_irrelevant"] = True
        if hero and i == 0 and isinstance(row.get("why"), str) and row["why"].strip():
            fields["why"] = row["why"].strip()[:220]
        if i >= 0 and fields:
            out[i] = fields
    return out


@st.cache_data(ttl=900, show_spinner=False)
def classify_batch(headlines: tuple[tuple[str, str], ...],
                   hero: bool = True) -> dict[int, dict]:
    """((title, summary), ...) -> {index: fields}. Walks the provider chain
    in order; {} only when every tier fails (rules then stand)."""
    if not headlines:
        return {}
    prompt = _prompt(headlines, hero)
    for p in providers():
        _t0 = _time.time()
        try:
            out = _parse(_call(p, prompt), hero)
            _audit(p["label"], headlines, out, _t0, ok=True)
            return out
        except Exception as e:
            _audit(p["label"], headlines, {}, _t0, ok=False,
                   error=str(e)[:120])
            continue
    return {}


def _audit(label: str, headlines, out, t0, ok: bool, error: str = "") -> None:
    try:
        from data_sources import ai_audit
        ai_audit.record({
            "provider": label, "ok": ok,
            "headlines_sent": len(headlines),
            "classifications_returned": len(out),
            "latency_ms": int((_time.time() - t0) * 1000),
            "titles": [t[:80] for t, _ in headlines],
            **({"error": error} if error else {}),
        })
    except Exception:
        pass
