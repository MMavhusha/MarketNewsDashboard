"""Market data via yfinance (free). Every function degrades to empty
structures on failure — the UI renders explicit 'unavailable' states and
never fabricates values. Swap this module for a premium provider
(Bloomberg / Refinitiv) without touching the views.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Optional

import pandas as pd
import time

import streamlit as st

try:
    import yfinance as yf
except Exception:  # pragma: no cover
    yf = None

# ---------------------------------------------------------------- config
SUMMARY_STRIP = [
    ("S&P 500", "^GSPC", "index", "{:,.2f}"),
    ("NASDAQ", "^IXIC", "index", "{:,.2f}"),
    ("FTSE 100", "^FTSE", "index", "{:,.2f}"),
    ("JSE ALSI", "^J203.JO", "index", "{:,.0f}"),
    ("USD/ZAR", "USDZAR=X", "fx", "{:,.4f}"),
    ("EUR/USD", "EURUSD=X", "fx", "{:,.4f}"),
    ("Gold", "GC=F", "commodity", "{:,.2f}"),
    ("Brent Crude", "BZ=F", "commodity", "{:,.2f}"),
]

# Spec list only: Brent, Iron ore, Gold, Platinum, Coal, Copper
# (name, ticker, unit, multiplier). Multiplier is a pure unit conversion —
# never estimation. Copper: yfinance has no LME feed, so COMEX HG ($/lb) is
# converted to $/tonne (×2204.62) and labelled as such; LME is the premium
# target. Gold GC=F is the COMEX front month — the standard spot proxy.
COMMODITIES = [
    ("Brent Crude Oil", "BZ=F", "$/bbl", 1.0),
    ("WTI Crude Oil", "CL=F", "$/bbl", 1.0),
    ("Copper (COMEX conv., $/t)", "HG=F", "$/tonne", 2204.62),
    ("Gold Spot (COMEX proxy)", "GC=F", "$/oz", 1.0),
    ("Iron Ore 62% Fe CFR (CME TSI)", "TIO=F", "$/tonne", 1.0),
    ("Platinum", "PL=F", "$/oz", 1.0),
    ("Coal (Newcastle proxy)", "MTF=F", "$/tonne", 1.0),
]

FX_MAJORS = [
    ("EUR/USD", "EURUSD=X"), ("GBP/USD", "GBPUSD=X"), ("USD/JPY", "USDJPY=X"),
    ("USD/ZAR", "USDZAR=X"), ("USD/CNY", "USDCNY=X"), ("AUD/USD", "AUDUSD=X"),
    ("USD/CHF", "USDCHF=X"), ("USD/CAD", "USDCAD=X"), ("USD/INR", "USDINR=X"),
    ("USD/BRL", "USDBRL=X"), ("DXY Index", "DX-Y.NYB"),
]

# CORE = instruments explicitly requested in the spec
# (summary strip + the six spec commodities). EXTENDED = broader context set.
CORE_MOVERS = [
    ("S&P 500", "^GSPC"), ("NASDAQ", "^IXIC"), ("FTSE 100", "^FTSE"),
    ("JSE ALSI", "^J203.JO"), ("USD/ZAR", "USDZAR=X"), ("EUR/USD", "EURUSD=X"),
    ("Gold", "GC=F"), ("Brent Crude", "BZ=F"),
    ("Iron Ore", "TIO=F"), ("Platinum", "PL=F"), ("Coal", "MTF=F"),
    ("Copper", "HG=F"),
]
EXTENDED_MOVERS = [
    ("Dow Jones", "^DJI"), ("DAX", "^GDAXI"), ("CAC 40", "^FCHI"),
    ("Nikkei 225", "^N225"), ("Hang Seng", "^HSI"), ("Shanghai Comp", "000001.SS"),
    ("Sensex", "^BSESN"), ("USD/JPY", "USDJPY=X"), ("GBP/USD", "GBPUSD=X"),
    ("USD/CNY", "USDCNY=X"), ("USD/INR", "USDINR=X"),
]


@dataclass
class Quote:
    name: str
    ticker: str
    price: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    spark: list = field(default_factory=list)
    asof: Optional[str] = None
    fmt: str = "{:,.2f}"

    @property
    def ok(self) -> bool:
        return self.price is not None


# ---------------------------------------------------------------- fetch
@st.cache_data(ttl=120, show_spinner=False)
def _download_cached(tickers: tuple[str, ...], period: str = "1mo") -> pd.DataFrame:
    """Batch OHLC download. Raises on total failure so empty results are
    NOT cached — the next run retries instead of pinning a dead cache."""
    df = yf.download(
        list(tickers), period=period, interval="1d",
        group_by="ticker", auto_adjust=True, progress=False, threads=True,
    )
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise RuntimeError("empty batch")
    return df


def _download(tickers: tuple[str, ...], period: str = "1mo") -> pd.DataFrame:
    if yf is None:
        return pd.DataFrame()
    from data_sources import obs
    try:
        with obs.track(f"yfinance download · {len(tickers)} tickers · {period}"):
            return _download_cached(tickers, period)
    except Exception:
        return pd.DataFrame()


def _close_series(df: pd.DataFrame, ticker: str, single: bool) -> pd.Series:
    try:
        s = df["Close"] if single else df[ticker]["Close"]
        return s.dropna()
    except Exception:
        return pd.Series(dtype=float)


def get_quotes(items: list[tuple], period: str = "1mo") -> list[Quote]:
    """items: (name, ticker[, extra..., fmt]). Returns a Quote per item."""
    tickers = tuple(i[1] for i in items)
    df = _download(tickers, period)
    single = len(tickers) == 1
    out: list[Quote] = []
    for item in items:
        name, ticker = item[0], item[1]
        fmt = item[3] if len(item) > 3 else "{:,.2f}"
        q = Quote(name=name, ticker=ticker, fmt=fmt)
        s = _close_series(df, ticker, single) if not df.empty else pd.Series(dtype=float)
        if len(s) >= 2:
            last, prev = float(s.iloc[-1]), float(s.iloc[-2])
            q.price = last
            q.change = last - prev
            q.change_pct = (last / prev - 1.0) * 100 if prev else None
            q.spark = [float(x) for x in s.tail(22).tolist()]
            try:
                q.asof = pd.Timestamp(s.index[-1]).strftime("%d %b %Y")
            except Exception:
                q.asof = None
        if not q.ok:  # per-ticker retry: single fetch often succeeds when
            s2 = get_history(ticker, "1mo")       # a batch member fails
            if len(s2) >= 2:
                last, prev = float(s2.iloc[-1]), float(s2.iloc[-2])
                q.price, q.change = last, last - prev
                q.change_pct = (last / prev - 1.0) * 100 if prev else None
                q.spark = [float(x) for x in s2.tail(22).tolist()]
                try:
                    q.asof = pd.Timestamp(s2.index[-1]).strftime("%d %b %Y")
                except Exception:
                    q.asof = None
        out.append(q)
    return out


@st.cache_data(ttl=120, show_spinner=False)
def _history_cached(ticker: str, period: str) -> pd.Series:
    df = yf.download(ticker, period=period, interval="1d",
                     auto_adjust=True, progress=False)
    if df is None or df.empty:
        raise RuntimeError("empty")
    s = df["Close"].dropna()
    if isinstance(s, pd.DataFrame):
        s = s.iloc[:, 0].dropna()
    return s


def get_history(ticker: str, period: str = "1y") -> pd.Series:
    if yf is None:
        return pd.Series(dtype=float)
    from data_sources import obs
    try:
        with obs.track(f"yfinance history · {ticker} · {period}"):
            return _history_cached(ticker, period)
    except Exception:
        return pd.Series(dtype=float)


SUMMARY_PRIMARY = ["JSE ALSI", "USD/ZAR", "S&P 500", "EUR/USD", "Gold", "Brent Crude"]

SUMMARY_SUBTITLES = {
    "S&P 500": "US large cap", "NASDAQ": "US tech", "FTSE 100": "UK large cap",
    "JSE ALSI": "FTSE/JSE All Share", "USD/ZAR": "Rand per US Dollar",
    "EUR/USD": "Euro vs Dollar", "Gold": "USD per ounce",
    "Brent Crude": "USD per barrel",
}


def get_summary_strip() -> list[Quote]:
    return get_quotes(SUMMARY_STRIP)


def get_commodities() -> list[Quote]:
    qs = get_quotes([(n, t, "c") for n, t, _u, _m in COMMODITIES])
    mult = {n: m for n, _t, _u, m in COMMODITIES}
    for q in qs:  # apply unit conversions (price, spark; % change unaffected)
        m = mult.get(q.name, 1.0)
        if q.ok and m != 1.0:
            q.price = q.price * m
            q.change = (q.change or 0) * m
            q.spark = [v * m for v in q.spark]
    return qs


def get_fx() -> list[Quote]:
    return get_quotes([(n, t) for n, t in FX_MAJORS])


def get_movers(top_n: int = 6, universe: str = "core") -> tuple[list[Quote], list[Quote]]:
    items = CORE_MOVERS if universe == "core" else CORE_MOVERS + EXTENDED_MOVERS
    qs = [q for q in get_quotes(items) if q.ok and q.change_pct is not None]
    qs.sort(key=lambda q: q.change_pct, reverse=True)
    return qs[:top_n], list(reversed(qs[-top_n:]))


def get_weekly_movers(top_n: int = 6) -> tuple[list[Quote], list[Quote]]:
    """True 1-week movers over the FULL core+extended universe: last close
    vs the last close on/before 7 calendar days prior. Pure arithmetic on
    published closes — same 1W convention as the FX heat table."""
    out: list[Quote] = []
    for name, tk in CORE_MOVERS + EXTENDED_MOVERS:
        h = get_history(tk, "1mo")
        if len(h) < 2:
            continue
        past = h[h.index <= h.index[-1] - pd.Timedelta(days=7)]
        if not len(past) or float(past.iloc[-1]) == 0:
            continue
        last, prev = float(h.iloc[-1]), float(past.iloc[-1])
        out.append(Quote(name=name, ticker=tk, price=last,
                         change=last - prev,
                         change_pct=(last - prev) / prev * 100))
    out.sort(key=lambda q: q.change_pct, reverse=True)
    return out[:top_n], list(reversed(out[-top_n:]))


# ------------------------------------------------------------ shock alerts
# Derived, factual display of observed moves — thresholds only, no forecasting.
DEFAULT_THRESHOLDS = {
    "index": (2.0, 3.5), "fx": (1.5, 3.0),
    "commodity": (3.0, 6.0),
}


def get_thresholds() -> dict:
    """PM-adjustable (Settings page); session-scoped until auth/storage exist."""
    return st.session_state.get("alert_thresholds", DEFAULT_THRESHOLDS)


def _alert_universe() -> tuple[list[tuple], dict]:
    """Strip + spec commodities + FX majors (deduped) with their kinds."""
    items, kinds, seen = [], {}, set()
    for n, t, k, f in SUMMARY_STRIP:
        items.append((n, t, k, f)); kinds[t] = k; seen.add(t)
    for n, t, _u, _m in COMMODITIES:
        if t not in seen:
            items.append((n, t, "commodity", "{:,.2f}")); kinds[t] = "commodity"; seen.add(t)
    for n, t in FX_MAJORS:
        if t not in seen:
            k = "index" if "Index" in n else "fx"
            items.append((n, t, k, "{:,.4f}")); kinds[t] = k; seen.add(t)
    return items, kinds


def get_shock_alerts() -> list[dict]:
    alerts = []
    universe, kinds = _alert_universe()
    quotes = get_quotes(universe)
    for q in quotes:
        if not q.ok or q.change_pct is None:
            continue
        warn, crit = get_thresholds().get(kinds.get(q.ticker, "index"), (2.0, 3.5))
        mag = abs(q.change_pct)
        if mag >= crit:
            sev = "Critical"
        elif mag >= warn:
            sev = "Warning"
        else:
            continue
        direction = "rose" if q.change_pct > 0 else "fell"
        alerts.append({
            "severity": sev,
            "title": f"{q.name} {direction} {mag:.1f}% in the latest session",
            "detail": f"Last {q.fmt.format(q.price)} as at {q.asof or 'latest close'}; "
                      f"a move of this size exceeds the {sev.lower()} threshold "
                      f"({crit if sev == 'Critical' else warn:.1f}%).",
            "assets": q.name,
            "asof": q.asof or "",
        })
    order = {"Critical": 0, "Warning": 1}
    alerts.sort(key=lambda a: order[a["severity"]])
    return alerts


def last_refresh() -> str:
    return datetime.now(ZoneInfo("Africa/Johannesburg")).strftime("%d %b %Y %H:%M SAST")


def clear_caches():
    """Refresh = latest prices and headlines. Slow-moving sources (SARB,
    World Bank, FRED, calendar) keep their own TTLs — clearing them would
    waste public-API quota for data that doesn't change intraday."""
    from data_sources import obs
    obs.note_action("cache clear", "markets + news + AI verdicts")
    try:
        from data_sources import alerts_index
        alerts_index.clear_cache()
    except Exception:
        pass
    for fn in (_download_cached, _history_cached, _intraday_cached):
        try:
            fn.clear()
        except Exception:
            pass
    try:
        from data_sources import news as _news
        _news.get_news.clear()
        _news.get_announcements.clear()
    except Exception:
        pass
    try:  # refresh must re-grade too, not re-apply cached model verdicts
        from data_sources import ai_enrich as _ai
        _ai.classify_batch.clear()
    except Exception:
        pass


@st.cache_data(ttl=120, show_spinner=False)
def _intraday_cached(tickers: tuple[str, ...]) -> pd.DataFrame:
    df = yf.download(list(tickers), period="2d", interval="15m",
                     group_by="ticker", auto_adjust=True, progress=False,
                     threads=True)
    if not isinstance(df, pd.DataFrame) or df.empty:
        raise RuntimeError("empty intraday batch")
    return df


def get_intraday(items: list[tuple]) -> dict[str, list[float]]:
    """{ticker: today's session closes}. Retries with backoff because Yahoo
    briefly throttles the refetch burst after a cache clear; returns {} only
    after three failed attempts."""
    if yf is None:
        return {}
    tickers = tuple(i[1] for i in items)
    for attempt in range(3):
        try:
            df = _intraday_cached(tickers)
            single = len(tickers) == 1
            out: dict[str, list[float]] = {}
            for item in items:
                t = item[1]
                try:
                    ser = (df["Close"] if single else df[t]["Close"]).dropna()
                    if ser.empty:
                        continue
                    last_day = ser.index[-1].date()
                    today = ser[[ts.date() == last_day for ts in ser.index]]
                    if len(today) >= 3:
                        out[t] = [float(x) for x in today.tolist()]
                except Exception:
                    continue
            if out or attempt == 2:
                return out
        except Exception:
            pass
        _intraday_cached.clear()
        time.sleep(1.0 + attempt)
    return {}


def watchable_names() -> list[str]:
    names = [n for n, *_ in SUMMARY_STRIP]
    names += [n for n, _t, _u, _m in COMMODITIES if n not in names]
    names += [n for n, _t in FX_MAJORS if n not in names]
    return names


def get_watch_quotes(names: list[str]) -> dict[str, Quote]:
    """Live quotes for watchlist names, drawn from the cached universes."""
    lookup: dict[str, Quote] = {}
    for q in get_summary_strip() + get_commodities() + get_fx():
        lookup.setdefault(q.name, q)
    return {n: lookup[n] for n in names if n in lookup}
