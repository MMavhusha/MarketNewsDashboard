"""News via free RSS feeds (Google News/CNBC/MarketWatch/Moneyweb et al.).

Classification is MODEL-PRIMARY (provider chain in ai_enrich: Gemini → Groq
→ these keyword rules as the guaranteed fallback) — descriptive tagging of
published content only; no prediction, no generation. A two-tier relevance
gate (rules here + the model's `relevant` field) drops consumer
personal-finance / lifestyle / agri-trade content. Feeds are pluggable so
premium wires (Bloomberg, Reuters direct, RiscFlash) can replace them.
"""
from __future__ import annotations

import html
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import streamlit as st

try:
    import feedparser
except Exception:  # pragma: no cover
    feedparser = None

FEEDS = [
    # (source label, url, default region)
    ("Google News · Markets", "https://news.google.com/rss/search?q=%22stock+market%22+OR+%22bond+market%22+OR+%22financial+markets%22+OR+%22equity+markets%22+when:1d&hl=en-US&gl=US&ceid=US:en", "Global"),
    ("CNBC World Markets", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362", "Global"),
    ("MarketWatch Top Stories", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "United States"),
    ("Moneyweb", "https://www.moneyweb.co.za/feed/", "South Africa"),
    ("Google News · Central banks", "https://news.google.com/rss/search?q=central+bank+OR+inflation+OR+rates+when:2d&hl=en-US&gl=US&ceid=US:en", "Global"),
]

_POS = {"surge", "rally", "gain", "gains", "record", "beat", "beats", "strong",
        "growth", "rise", "rises", "recovery", "upgrade", "optimism", "boost",
        "higher", "jump", "jumps", "soar", "profit", "expansion"}
_NEG = {"fall", "falls", "drop", "drops", "plunge", "slump", "crash", "fear",
        "fears", "recession", "cut", "cuts", "downgrade", "loss", "losses",
        "weak", "decline", "crisis", "default", "war", "sanctions", "selloff",
        "lower", "tumble", "miss", "misses", "contraction", "layoffs",
        "warns", "warning", "threat", "threats", "retaliate", "retaliation",
        "worsen", "worsens", "worsening", "escalation", "escalates",
        "conflict", "clash", "clashes", "skirmish", "skirmishes",
        "turmoil", "slowdown", "missile", "airstrike", "invasion"}

_REGIONS = {
    "South Africa": ["south africa", "south african", "sarb", "jse", "rand", "zar", "eskom", "stats sa", "pretoria", "johannesburg", "cape town", "sasol", "naspers", "mtn", "transnet", "load shedding", "ramaphosa", "godongwana"],
    "United States": ["u.s.", "united states", "america", "washington", "fed", "federal reserve", "fomc", "wall street", "s&p", "nasdaq", "treasury", "dollar", "trump"],
    "Euro Area": ["euro", "ecb", "eurozone", "germany", "france", "bund"],
    "United Kingdom": ["uk", "britain", "boe", "bank of england", "ftse", "sterling", "pound"],
    "China": ["china", "pboc", "yuan", "beijing", "shanghai", "hang seng"],
    "India": ["india", "rbi", "rupee", "sensex", "nifty", "mumbai"],
    "Japan": ["japan", "boj", "yen", "nikkei", "tokyo"],
}

_ASSETS = {
    "Equities": ["stock", "stocks", "equit", "shares", "index", "s&p", "nasdaq", "ftse", "nikkei", "jse", "earnings"],
    "Rates & Bonds": ["bond", "yield", "treasury", "rate", "rates", "fomc", "central bank", "ecb", "sarb", "boe", "boj", "inflation", "cpi"],
    "FX": ["dollar", "euro", "rand", "yen", "yuan", "currency", "forex", "fx", "sterling", "rupee"],
    "Commodities": ["oil", "brent", "crude", "gold", "copper", "platinum", "iron ore", "coal", "opec", "commodity"],
    "Crypto": ["bitcoin", "crypto", "ethereum"],
}

# Instrument-level tagging: the single most-affected traded instrument,
# priority-ordered (first match wins), keyword-boundary matched. Labels
# align with the app's tracked instruments.
_INSTRUMENTS = {
    "Oil": ["oil", "brent", "crude", "wti", "opec"],
    "Gold": ["gold"],
    "Copper": ["copper"],
    "Platinum": ["platinum"],
    "Iron Ore": ["iron ore"],
    "Coal": ["coal"],
    "USD/ZAR": ["rand", "usdzar", "zar"],
    "EUR/USD": ["eurusd"],
    "USD/JPY": ["usdjpy"],
    "Bitcoin": ["bitcoin", "btc"],
    "S&P 500": ["s&p 500", "s&p"],
    "NASDAQ": ["nasdaq"],
    "FTSE 100": ["ftse"],
    "JSE ALSI": ["jse", "alsi"],
}

_HIGH_IMPORTANCE = ["fed", "fomc", "ecb", "sarb", "rate decision", "inflation",
                    "cpi", "gdp", "recession", "crash", "opec", "sanctions",
                    "war", "default", "emergency", "intervention", "crisis",
                    "unemployment", "stimulus", "tariff", "tariffs", "acquisition", "merger",
                    "takeover", "buyout", "earnings", "ipo", "bankruptcy",
                    "bailout", "rate cut", "rate hike", "central bank",
                    "payrolls", "jobs report", "retail sales", "pmi",
                    "billion", "trillion", "capex"]


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


# ---- Word-boundary keyword matching (permanent fix for the substring
# class: "wary"→war, "Warsh"→war, "reward"→war, "FedEx"/"Fedorov"→fed,
# "brand"/"grand"→rand, "Indiana"→india). Compiled once per keyword. ----
_KW_CACHE: dict[str, "re.Pattern"] = {}


def _kw(k: str) -> "re.Pattern":
    p = _KW_CACHE.get(k)
    if p is None:
        p = re.compile(r"(?<![a-z0-9&])" + re.escape(k) + r"(?![a-z0-9&])")
        _KW_CACHE[k] = p
    return p


def _matches(t: str, keys) -> list[str]:
    return [k for k in keys if _kw(k).search(t)]


def _norm(t: str) -> str:
    """Lowercase + expand n't contractions so negation is visible to the
    tokenizer ("isn't golden" must not read as positive "golden")."""
    return t.lower().replace("n't", " not")


_GNEWS_SUFFIX = re.compile(r"\s+-\s+[^-]{2,60}$")


def _strip_publisher(title: str) -> str:
    """Google News appends ' - Publisher' to titles; strip one suffix."""
    return _GNEWS_SUFFIX.sub("", title).strip()


_OPINION_MARKERS = ["opinion", "analysis |", "macroscope", "commentary",
                    "column:", "editorial", "explainer", "newsletter",
                    "podcast", "mises institute", "project syndicate"]

# Score-only keywords: they raise importance but make meaningless chips.
_TAG_EXCLUDE = {"billion", "trillion"}

# Rules tier of the relevance gate: blatant consumer personal-finance,
# lifestyle and local/agri-trade content is dropped before classification.
# Ambiguous stories are judged by the AI layer's `relevant` field.
_IRRELEVANT_MARKERS = [
    "heloc", "credit card debt", "credit-card debt", "my retirement",
    "retirement mistake", "financial advisor says", "social security check",
    "farmers market", "farmers markets", "soybean", "cattle", "angus",
    "4-h", "county fair", "recipe", "horoscope", "crossword", "quiz",
    "prediction market", "prediction markets",
]
_ADVICE_RE = re.compile(r"^(i'?m |i |we're |my )|should (i|you) |"
                        r"here's how much ")


def _is_relevant(title: str, summary: str) -> bool:
    t = f"{title} {summary}".lower()
    if _matches(t, _IRRELEVANT_MARKERS):
        return False
    return not _ADVICE_RE.search(title.lower())




# ---------------- Directional sentiment engine (no LLM) ----------------
# Finance sentiment is directional: "unemployment falls" is GOOD while
# "growth falls" is BAD — the same verb flips meaning with the subject.
# Pipeline: (1) decisive multiword phrases, (2) subject×direction pairs,
# (3) negation flips, (4) residual single-word lexicon as a tiebreaker.
# Known ceiling: multi-entity headlines, sarcasm and complex causality still
# misread — that class needs a language model.

_PHRASES = {
    "better than expected": 2, "beats estimates": 2, "beat expectations": 2,
    "tops forecasts": 2, "record high": 2, "eases fears": 2, "fears ease": 2,
    "tensions ease": 2, "rate cut hopes": 2, "rate cut bets": 2,
    "soft landing": 1, "upgrades outlook": 2, "raises guidance": 2,
    "worse than expected": -2, "misses estimates": -2, "missed expectations": -2,
    "record low": -2, "profit warning": -2, "cuts forecast": -2,
    "cuts guidance": -2, "lowers outlook": -2, "rate hike fears": -2,
    "hard landing": -2, "trade war": -1, "load shedding": -1,
    "state of disaster": -2, "downgrades outlook": -2, "ceasefire": 2,
    "strikes deal": 2, "reaches deal": 2, "supply crunch": -1,
    "supply shock": -1, "red line": -1,
}

# Subjects that are GOOD news when they rise (and bad when they fall)
_GOOD_UP = {"growth", "gdp", "profit", "profits", "earnings", "stocks",
            "shares", "markets", "equities", "rand", "exports", "employment",
            "hiring", "jobs", "confidence", "sales", "output", "production",
            "demand", "investment", "reserves", "surplus", "wages"}
# Subjects that are BAD news when they rise (and good when they fall)
_BAD_UP = {"inflation", "unemployment", "deficit", "debt", "defaults",
           "bankruptcies", "tariffs", "tensions", "fears", "costs",
           "joblessness", "insolvencies", "arrears", "volatility",
           "shortages", "outages", "sanctions", "skirmishes"}

_UP_VERBS = {"rise", "rises", "rising", "rose", "jump", "jumps", "jumped",
             "surge", "surges", "surged", "climb", "climbs", "climbed",
             "soar", "soars", "soared", "gain", "gains", "gained", "rally",
             "rallies", "rallied", "rebound", "rebounds", "accelerate",
             "accelerates", "strengthen", "strengthens", "improves",
             "improve", "improved", "grows", "grew", "beats", "beat",
             "higher", "up"}
_DOWN_VERBS = {"fall", "falls", "falling", "fell", "drop", "drops",
               "dropped", "slump", "slumps", "slumped", "plunge", "plunges",
               "plunged", "sink", "sinks", "sank", "slide", "slides", "slid",
               "ease", "eases", "eased", "cool", "cools", "cooled", "slow",
               "slows", "slowed", "weaken", "weakens", "weakened", "tumble",
               "tumbles", "tumbled", "decline", "declines", "declined",
               "shrink", "shrinks", "shrank", "misses", "missed", "lower",
               "down"}
_NEGATORS = {"not", "no", "without", "fails", "fail", "unlikely", "denies",
             "denied", "halts"}


def _sentiment(text: str) -> str:
    t = _norm(text)
    score = 0
    for phrase, val in _PHRASES.items():
        if phrase in t:
            score += val
    toks = re.findall(r"[a-z&']+", t)
    for i, tok in enumerate(toks):
        subj = (1 if tok in _GOOD_UP else -1 if tok in _BAD_UP else 0)
        if not subj:
            continue
        # Subject→verb order dominates English headlines: scan the tokens
        # AFTER the subject first, then nearest-first backwards (for
        # "falling inflation" constructions). A flat mixed window wrongly
        # binds a subject to the previous clause's verb.
        direction, vpos = 0, -1
        for off in range(i + 1, min(i + 4, len(toks))):
            w = toks[off]
            if w in _UP_VERBS:
                direction, vpos = 1, off
                break
            if w in _DOWN_VERBS:
                direction, vpos = -1, off
                break
        if not direction:
            for w in reversed(toks[max(0, i - 2):i]):
                if w in _UP_VERBS:
                    direction = 1
                    break
                if w in _DOWN_VERBS:
                    direction = -1
                    break
        if not direction:
            continue
        pair = subj * direction  # good×up=+, bad×up=−, bad×down=+, good×down=−
        # Negators live before the subject ("no growth in exports") OR
        # between subject and verb ("profits did not rise") — check both.
        neg_zone = toks[max(0, i - 3):i] + (toks[i + 1:vpos] if vpos > i else [])
        if any(w in _NEGATORS for w in neg_zone):
            pair = -pair
        score += 2 * pair
    if score == 0:  # tiebreaker: legacy single-word lexicon
        words = set(toks)
        score = len(words & _POS) - len(words & _NEG)
    return "Positive" if score > 0 else "Negative" if score < 0 else "Neutral", score


def _sentiment_label(text: str) -> str:
    return _sentiment(text)[0]


def _classify(title: str, summary: str, default_region: str = "") -> dict:
    """Title-weighted classification. RSS summaries can describe a different
    story (Moneyweb digests) or embed publisher junk (Google News), so the
    TITLE decides whenever it is decisive; the summary only supplements —
    capped for importance and never able to overturn a confident title."""
    tt = _norm(title)
    ts = _norm(f"{title} {summary[:160]}")

    sentiment, _sc = _sentiment(title)
    if abs(_sc) < 2:  # title not decisive: let a capped slice of summary help
        sentiment, _sc = _sentiment(f"{title} {summary[:160]}")

    # Region/asset: keyword match only, title first — an outlet's
    # nationality does not make a story about that country.
    region = "Global"
    for scope in (tt, ts):
        hit = next((reg for reg, keys in _REGIONS.items()
                    if _matches(scope, keys)), None)
        if hit:
            region = hit
            break

    asset = "Macro"
    for scope in (tt, ts):
        hit = next((a for a, keys in _ASSETS.items()
                    if _matches(scope, keys)), None)
        if hit:
            asset = hit
            break

    # Instruments are PLURAL — a story about oil AND the S&P 500 is about
    # both. Rules tier: every word-boundary match, ordered by first mention,
    # title first (summary only when the title names none), capped at 3.
    # The model tier overrides with a context judgment of which instruments
    # the story is MATERIALLY about (see ai_enrich prompt).
    instruments: list[str] = []
    for scope in (tt, ts):
        found = []
        for lbl, keys in _INSTRUMENTS.items():
            pos = min((m.start() for m in
                       (_kw(k).search(scope) for k in keys) if m),
                      default=None)
            if pos is not None:
                found.append((pos, lbl))
        if found:
            instruments = [lbl for _, lbl in sorted(found)][:3]
            break

    title_hits = _matches(tt, _HIGH_IMPORTANCE)
    sum_hits = [k for k in _matches(ts, _HIGH_IMPORTANCE) if k not in title_hits]
    score = 2 * len(title_hits) + min(2, len(sum_hits))
    opinion = bool(_matches(tt, _OPINION_MARKERS))
    if opinion:  # op-eds and columns rank below primary reporting
        score = max(0, score - 2)
    importance = "High" if score >= 4 else "Medium" if score >= 2 else "Low"

    # Visible tags from the TITLE only — digest-style summaries describe
    # other stories. The affected instrument renders via its own dedicated
    # chip (item["instrument"]), so it never duplicates into tags; score-
    # only terms (billion/trillion) never surface as chips either.
    kw_tags = [k for k in title_hits if k not in _TAG_EXCLUDE]
    tags = ((["opinion"] if opinion else []) + kw_tags)[:3]
    return {"sentiment": sentiment, "region": region, "asset": asset,
            "confident": abs(_sc) >= 2, "instruments": instruments,
            "importance": importance, "score": score, "tags": tags}


@st.cache_data(ttl=900, show_spinner=False)
def get_news(max_per_feed: int = 12) -> list[dict]:
    if feedparser is None:
        return []
    items, seen = [], set()
    with ThreadPoolExecutor(max_workers=len(FEEDS)) as ex:
        parsed_feeds = list(ex.map(
            lambda f: (f[0], f[1], f[2], feedparser.parse(f[1])), FEEDS))
    for source, url, default_region, parsed in parsed_feeds:
        gnews = "news.google.com" in url
        try:
            for e in parsed.entries[:max_per_feed]:
                title = _clean(getattr(e, "title", ""))
                if gnews:
                    title = _strip_publisher(title)
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())
                summary = _clean(getattr(e, "summary", ""))[:280]
                if gnews:
                    summary = _strip_publisher(summary)
                # Suppress summaries that merely duplicate the title
                if summary and summary.lower().startswith(title.lower()[:60]):
                    summary = ""
                if not _is_relevant(title, summary):
                    continue  # relevance gate, rules tier
                link = getattr(e, "link", "")
                ts = getattr(e, "published_parsed", None) or getattr(e, "updated_parsed", None)
                when = datetime.fromtimestamp(time.mktime(ts), tz=timezone.utc) if ts else None
                item = {"title": title, "summary": summary, "link": link,
                        "source": source, "published": when}
                item.update(_classify(title, summary, default_region))
                items.append(item)
        except Exception:
            continue
    items.sort(key=lambda i: (i["score"], i["published"] or datetime.min.replace(tzinfo=timezone.utc)),
               reverse=True)
    try:  # AI classification — MODEL-PRIMARY: every displayed story goes to
        # the provider chain (Gemini → Groq → rules) in batches; the rules
        # verdicts above stand only when every provider tier fails. The
        # model also judges relevance; stories it rejects are dropped.
        from data_sources import ai_enrich
        if ai_enrich.enabled() and items:
            queue = items[:50]
            for start in range(0, len(queue), 25):
                chunk = queue[start:start + 25]
                fields = ai_enrich.classify_batch(
                    tuple((i["title"], i["summary"]) for i in chunk),
                    hero=(start == 0))
                for idx, f in fields.items():
                    if idx < len(chunk):
                        chunk[idx].update(f)
                        chunk[idx]["_ai"] = True  # admin: model-touched
            items = [i for i in items if not i.get("_irrelevant")]
            items.sort(key=lambda i: (i["score"], i["published"] or
                                      datetime.min.replace(tzinfo=timezone.utc)),
                       reverse=True)
    except Exception:
        pass
    return items


def pick_hero(items: list[dict]) -> dict | None:
    return items[0] if items else None


def fmt_time(dt) -> str:
    if not dt:
        return ""
    delta = datetime.now(timezone.utc) - dt
    hrs = delta.total_seconds() / 3600
    if hrs < 1:
        return f"{int(delta.total_seconds() // 60)}m ago"
    if hrs < 24:
        return f"{int(hrs)}h ago"
    return dt.strftime("%d %b %Y")


# Company announcements: keyword RSS queries as free stand-ins for a
# corporate-actions wire (SENS / Bloomberg CACS in future).
# SENS candidate feeds (parsed defensively; JSE issuer announcements)
SENS_FEEDS = [
    ("Moneyweb SENS", "https://www.moneyweb.co.za/tools-and-data/sens/feed/"),
    ("Sharenet SENS", "https://www.sharenet.co.za/v3/rss/sens.php"),
]

ANNOUNCEMENT_QUERIES = [
    ("Dividends", "dividend+declaration+when:7d"),
    ("Dividends", "JSE+dividend+declaration+when:7d"),
    ("Earnings", "JSE+results+trading+statement+when:7d"),
    ("Leadership", "CEO+appointed+OR+CEO+resigns+when:7d"),
    ("Earnings", "quarterly+earnings+results+when:2d"),
    ("M&A", "merger+OR+acquisition+announced+when:7d"),
    ("Capital raises", "capital+raise+OR+rights+issue+when:7d"),
    ("Buybacks", "share+buyback+when:7d"),
    ("Guidance", "guidance+update+OR+trading+statement+when:7d"),
]


@st.cache_data(ttl=1800, show_spinner=False)
def get_announcements(max_per_cat: int = 5) -> list[dict]:
    if feedparser is None:
        return []
    out, seen = [], set()
    # JSE SENS wires first (authoritative issuer announcements when reachable)
    for label, url in SENS_FEEDS:
        try:
            parsed = feedparser.parse(url)
            for e in parsed.entries[:20]:
                title = _clean(getattr(e, "title", ""))
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())
                ts = getattr(e, "published_parsed", None)
                when = (datetime.fromtimestamp(time.mktime(ts), tz=timezone.utc)
                        if ts else None)
                out.append({"category": "SENS (JSE)", "title": title,
                            "link": getattr(e, "link", ""), "published": when,
                            "source": label})
        except Exception:
            continue
    for cat, q in ANNOUNCEMENT_QUERIES:
        url = f"https://news.google.com/rss/search?q={q}&hl=en-US&gl=US&ceid=US:en"
        try:
            parsed = feedparser.parse(url)
            for e in parsed.entries[:max_per_cat]:
                title = _strip_publisher(_clean(getattr(e, "title", "")))
                if not title:
                    continue
                ts = getattr(e, "published_parsed", None)
                when = datetime.fromtimestamp(time.mktime(ts), tz=timezone.utc) if ts else None
                if title.lower() in seen:
                    continue
                seen.add(title.lower())
                out.append({"category": cat, "title": title,
                            "link": getattr(e, "link", ""), "published": when,
                            "source": _clean(getattr(getattr(e, "source", None), "title", "") if hasattr(e, "source") else "")})
        except Exception:
            continue
    return out


@st.cache_data(ttl=900, show_spinner=False)
def get_feed_status() -> list[dict]:
    """Diagnostics: per-feed reachability and entry counts."""
    out = []
    for source, url, _dr in FEEDS:
        try:
            parsed = feedparser.parse(url) if feedparser else None
            n = len(parsed.entries) if parsed else 0
            ok = bool(n) and not getattr(parsed, "bozo", False)
            out.append({"name": source, "ok": ok, "detail": f"{n} entries"})
        except Exception as e:
            out.append({"name": source, "ok": False, "detail": str(e)[:60]})
    return out


def fuzzy_match(query: str, text: str) -> bool:
    """Substring, prefix, or typo-tolerant word match (difflib, no deps).
    'escom'→Eskom, 'tarrif'→tariff, 'oli'→oil, 'infl'→inflation (prefix).
    Threshold scales with word length: short words need a looser ratio or
    they can never match with a one-letter typo."""
    from difflib import SequenceMatcher
    q = query.lower().strip()
    t = text.lower()
    if not q:
        return True
    if q in t:
        return True
    words = set(re.findall(r"[a-z0-9']+", t))
    for term in q.split():
        thr = 0.66 if len(term) <= 4 else 0.75 if len(term) <= 6 else 0.8
        ok = any(w.startswith(term) or term.startswith(w[:max(3, len(term))])
                 or SequenceMatcher(None, term, w).ratio() >= thr
                 for w in words if abs(len(w) - len(term)) <= 4)
        if not ok:
            return False
    return True
