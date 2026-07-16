"""News via free RSS feeds (Reuters/CNBC/MarketWatch/Moneyweb et al.).

Classification is rule-based (keyword lexicons) — descriptive tagging of
published content only; no prediction, no generation. Feeds are pluggable so
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
    ("Reuters (via Google News)", "https://news.google.com/rss/search?q=markets+when:1d&hl=en-US&gl=US&ceid=US:en", "Global"),
    ("CNBC World Markets", "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100727362", "Global"),
    ("MarketWatch Top Stories", "https://feeds.content.dowjones.io/public/rss/mw_topstories", "United States"),
    ("Moneyweb", "https://www.moneyweb.co.za/feed/", "South Africa"),
    ("Investing.com News (via Google News)", "https://news.google.com/rss/search?q=central+bank+OR+inflation+OR+rates+when:2d&hl=en-US&gl=US&ceid=US:en", "Global"),
]

_POS = {"surge", "rally", "gain", "gains", "record", "beat", "beats", "strong",
        "growth", "rise", "rises", "recovery", "upgrade", "optimism", "boost",
        "higher", "jump", "jumps", "soar", "profit", "expansion"}
_NEG = {"fall", "falls", "drop", "drops", "plunge", "slump", "crash", "fear",
        "fears", "recession", "cut", "cuts", "downgrade", "loss", "losses",
        "weak", "decline", "crisis", "default", "war", "sanctions", "selloff",
        "lower", "tumble", "miss", "misses", "contraction", "layoffs"}

_REGIONS = {
    "South Africa": ["south africa", "south african", "sarb", "jse", "rand", "zar", "eskom", "stats sa", "pretoria", "johannesburg", "cape town", "sasol", "naspers", "mtn", "transnet", "load shedding", "ramaphosa", "godongwana"],
    "United States": ["u.s.", "us ", "fed ", "federal reserve", "fomc", "wall street", "s&p", "nasdaq", "treasury", "dollar"],
    "Euro Area": ["euro", "ecb", "eurozone", "germany", "france", "bund"],
    "United Kingdom": ["uk ", "britain", "boe", "bank of england", "ftse", "sterling", "pound"],
    "China": ["china", "pboc", "yuan", "beijing", "shanghai", "hang seng"],
    "India": ["india", "rbi ", "rupee", "sensex", "nifty", "mumbai"],
    "Japan": ["japan", "boj", "yen", "nikkei", "tokyo"],
}

_ASSETS = {
    "Equities": ["stock", "stocks", "equit", "shares", "index", "s&p", "nasdaq", "ftse", "nikkei", "jse", "earnings"],
    "Rates & Bonds": ["bond", "yield", "treasury", "rate", "rates", "fomc", "central bank", "ecb", "sarb", "boe", "boj", "inflation", "cpi"],
    "FX": ["dollar", "euro", "rand", "yen", "yuan", "currency", "forex", "fx", "sterling", "rupee"],
    "Commodities": ["oil", "brent", "crude", "gold", "copper", "platinum", "iron ore", "coal", "opec", "commodity"],
    "Crypto": ["bitcoin", "crypto", "ethereum"],
}

_HIGH_IMPORTANCE = ["fed", "fomc", "ecb", "sarb", "rate decision", "inflation",
                    "cpi", "gdp", "recession", "crash", "opec", "sanctions",
                    "war", "default", "emergency", "intervention", "crisis",
                    "unemployment", "stimulus", "tariff"]


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    return html.unescape(re.sub(r"\s+", " ", text)).strip()


def _classify(title: str, summary: str, default_region: str = "") -> dict:
    t = f"{title} {summary}".lower()
    words = set(re.findall(r"[a-z&']+", t))
    pos, neg = len(words & _POS), len(words & _NEG)
    sentiment = "Positive" if pos > neg else "Negative" if neg > pos else "Neutral"

    # Region = keyword match only; an outlet's nationality does not make a
    # story about that country (a SA site covering a US IPO is Global).
    region = "Global"
    for reg, keys in _REGIONS.items():
        if any(k in t for k in keys):
            region = reg
            break

    asset = "Macro"
    for a, keys in _ASSETS.items():
        if any(k in t for k in keys):
            asset = a
            break

    score = sum(2 for k in _HIGH_IMPORTANCE if k in t) + (1 if pos + neg >= 2 else 0)
    importance = "High" if score >= 4 else "Medium" if score >= 2 else "Low"

    tags = [k for k in _HIGH_IMPORTANCE if k in t][:3]
    return {"sentiment": sentiment, "region": region, "asset": asset,
            "importance": importance, "score": score, "tags": tags}


@st.cache_data(ttl=900, show_spinner=False)
def get_news(max_per_feed: int = 12) -> list[dict]:
    if feedparser is None:
        return []
    items, seen = [], set()
    with ThreadPoolExecutor(max_workers=len(FEEDS)) as ex:
        parsed_feeds = list(ex.map(
            lambda f: (f[0], f[2], feedparser.parse(f[1])), FEEDS))
    for source, default_region, parsed in parsed_feeds:
        try:
            for e in parsed.entries[:max_per_feed]:
                title = _clean(getattr(e, "title", ""))
                if not title or title.lower() in seen:
                    continue
                seen.add(title.lower())
                summary = _clean(getattr(e, "summary", ""))[:280]
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
    try:  # optional AI classification (see data_sources/ai_enrich.py)
        from data_sources import ai_enrich
        if ai_enrich.enabled() and items:
            top = items[:25]
            fields = ai_enrich.classify_batch(
                tuple((i["title"], i["summary"]) for i in top))
            for idx, f in fields.items():
                if idx < len(top):
                    top[idx].update(f)
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
                title = _clean(getattr(e, "title", ""))
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
