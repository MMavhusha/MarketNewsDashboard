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
_AST = {"Equities", "Rates & Bonds", "FX", "Commodities", "Macro"}
_INSTR = {"Oil", "Gold", "Copper", "Platinum", "Iron Ore", "Coal",
          "USD/ZAR", "EUR/USD", "USD/JPY", "S&P 500", "JSE ALSI"}


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


def _prompt(headlines, hero: bool, themes: str = "") -> str:
    lines = "\n".join(f"{i}. {t} — {s[:240]}"
                      for i, (t, s) in enumerate(headlines))
    hero_line = ("For story 0 only, add why: ONE factual sentence on why it "
                 "matters to investors, no predictions. " if hero else "")
    # Auto-derived, descriptive-only context: recurring themes already
    # present in THIS batch. Anchors every story to the same backdrop, is
    # regenerated each cycle (never stale, no human upkeep), and states what
    # is in the news rather than any forecast.
    ctx = (f"Recurring market themes in today's stories: {themes}. Read the "
           f"stories below as a SET — classify related stories consistently "
           f"(items about the same conflict, policy decision or company must "
           f"not swing between Positive and Negative unless they describe "
           f"genuinely opposite developments) and use these themes as "
           f"background (e.g. a 'ceasefire proposal' is an event WITHIN an "
           f"ongoing conflict). Never let this context add anything not in a "
           f"story's own text.\n\n" if themes else "")
    return (
        "You classify financial news for an institutional portfolio-"
        "management dashboard. " + ctx + "Weigh the summary's facts equally "
        "with the title — headlines often understate. Read headlines the way "
        "an experienced editor would: financial journalists use metaphor, "
        "sarcasm, irony and wordplay. Judge every field by the story's ACTUAL "
        "meaning, not surface keywords — e.g. 'Trump's War on the Future' is "
        "commentary about policy, NOT a military conflict; 'Tech stocks get "
        "crushed' is a price move, not violence; a punning headline about "
        "'brewing trouble' for a coffee company is about that company. Do not "
        "let a dramatic or figurative word drive the sentiment or tags. "
        "For each numbered story return: sentiment (Positive/Negative/Neutral "
        "— the market RISK TONE of what is described, not a forecast; ACTUAL "
        "military conflict, attacks, escalation or sanctions are Negative "
        "unless the story is clearly about de-escalation succeeding — but a "
        "metaphorical 'war'/'battle'/'attack' is not conflict. For monetary "
        "policy, judge by NEWS IMPACT, not just direction: a widely-anticipated "
        "or already-priced action (a scheduled cut/hike the market expects) is "
        "Neutral — the news is the confirmation, not a surprise. Reserve "
        "Positive for a genuine surprise easing, an unexpectedly dovish signal, "
        "or cooling/muted inflation that opens the door to cuts; Negative for a "
        "surprise hike, an unexpectedly hawkish signal, or hot/accelerating "
        "inflation. A cut explicitly framed as a response to a sharply "
        "deteriorating economy is Negative), importance "
        "(High = central bank decisions or surprises, major macro data for "
        "large economies, armed conflict or sanctions affecting energy or "
        "supply chains, systemic credit events, corporate events of $10bn+ "
        "or mega-cap earnings; Medium = notable single-company or single-"
        "country developments with market impact; Low = minor items, "
        "opinion pieces, advice content), region (South Africa/United "
        "States/Euro Area/United Kingdom/China/India/Japan/Global), asset "
        "(Equities/Rates & Bonds/FX/Commodities/Macro), instruments "
        "(a list, possibly empty, of the tracked instruments this story is "
        "MATERIALLY about — judge from context, not word presence; a story "
        "can be about several. Choose only from: Oil, Gold, Copper, "
        "Platinum, Iron Ore, Coal, USD/ZAR, EUR/USD, USD/JPY, "
        "S&P 500, JSE ALSI), tags (0-2 SHORT lowercase "
        "topic labels capturing what the story is really about for a PM — "
        "e.g. 'rate decision', 'earnings', 'sanctions', 'election', "
        "'m&a', 'opinion'; omit if nothing material, and NEVER tag a "
        "figurative word literally) and relevant (true/false: is "
        "this market, economy or corporate news useful to institutional "
        "portfolio managers? Set FALSE for sport (World Cup, football, "
        "tennis, Olympics, cricket, rugby), entertainment/celebrity, "
        "lifestyle, travel, food, human-interest and consumer personal-"
        "finance advice — even when phrased cleverly or mentioning a country "
        "or a company in passing. Set TRUE only if the story is genuinely "
        "about markets, the economy, policy or a company's financial "
        "position). "
        + hero_line +
        "Respond with ONLY a JSON array of objects with keys i, sentiment, "
        "importance, region, asset, instruments, tags, relevant" +
        (", and why (story 0 only)" if hero else "") + ".\n\n" + lines)


def _post_with_retry(do_request, tries: int = 3):
    """Call do_request(); on a 429/503 (rate limit / transient) back off and
    retry a couple of times before giving up on this provider. Rate limits are
    usually momentary, so a short retry recovers many batches that would
    otherwise fall through the chain to the cruder rules engine.
    """
    import time as _t
    last = None
    for attempt in range(tries):
        try:
            r = do_request()
            r.raise_for_status()
            return r
        except requests.HTTPError as e:
            code = getattr(e.response, "status_code", None)
            last = e
            if code in (429, 503) and attempt < tries - 1:
                # exponential-ish backoff: 0.8s, 1.6s (+ jitter via attempt)
                _t.sleep(0.8 * (2 ** attempt))
                continue
            raise
    if last:
        raise last


def _call(p: dict, prompt: str) -> str:
    if p["kind"] == "anthropic":
        r = _post_with_retry(lambda: requests.post(
            _ANTHROPIC_URL, timeout=25,
            headers={"x-api-key": p["key"],
                     "anthropic-version": "2023-06-01",
                     "content-type": "application/json"},
            json={"model": _ANTHROPIC_MODEL, "max_tokens": 3000,
                  "messages": [{"role": "user", "content": prompt}]}))
        return "".join(b.get("text", "") for b in r.json().get("content", []))
    r = _post_with_retry(lambda: requests.post(
        f"{p['base']}/chat/completions", timeout=25,
        headers={"Authorization": f"Bearer {p['key']}",
                 "content-type": "application/json"},
        json={"model": p["model"], "max_tokens": 3000,
              "messages": [{"role": "user", "content": prompt}]}))
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
        if isinstance(row.get("instruments"), list):
            fields["instruments"] = [x for x in row["instruments"]
                                     if x in _INSTR][:3]
        if isinstance(row.get("tags"), list):
            clean = [str(t).strip().lower()[:24] for t in row["tags"]
                     if str(t).strip()]
            fields["tags"] = clean[:2]  # model-decided, context-aware
        if isinstance(row.get("relevant"), bool) and not row["relevant"]:
            fields["_irrelevant"] = True
        if hero and i == 0 and isinstance(row.get("why"), str) and row["why"].strip():
            fields["why"] = row["why"].strip()[:220]
        if i >= 0 and fields:
            out[i] = fields
    return out


@st.cache_data(ttl=900, show_spinner=False)
def classify_batch(headlines: tuple[tuple[str, str], ...],
                   hero: bool = True, themes: str = "") -> dict[int, dict]:
    """((title, summary), ...) -> {index: fields}. Walks the provider chain
    in order; {} only when every tier fails (rules then stand)."""
    if not headlines:
        return {}
    prompt = _prompt(headlines, hero, themes)
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
