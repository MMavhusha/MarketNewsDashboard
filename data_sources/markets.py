"""Market data via yfinance (free). Every function degrades to empty
structures on failure — the UI renders explicit 'unavailable' states and
never fabricates values. Swap this module for a premium provider
(Bloomberg / Refinitiv) without touching the views.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
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
    ("Bitcoin", "BTC-USD", "crypto", "{:,.0f}"),
]

COMMODITIES = [
    ("Brent Crude Oil", "BZ=F", "$/bbl"),
    ("WTI Crude Oil", "CL=F", "$/bbl"),
    ("Gold", "GC=F", "$/oz"),
    ("Platinum", "PL=F", "$/oz"),
    ("Copper", "HG=F", "$/lb"),
    ("Iron Ore (SGX proxy)", "TIO=F", "$/t"),
    ("Coal (Newcastle proxy)", "MTF=F", "$/t"),
]

FX_MAJORS = [
    ("EUR/USD", "EURUSD=X"), ("GBP/USD", "GBPUSD=X"), ("USD/JPY", "USDJPY=X"),
    ("USD/ZAR", "USDZAR=X"), ("USD/CNY", "USDCNY=X"), ("AUD/USD", "AUDUSD=X"),
    ("USD/CHF", "USDCHF=X"), ("USD/CAD", "USDCAD=X"), ("USD/INR", "USDINR=X"),
    ("USD/BRL", "USDBRL=X"), ("DXY Index", "DX-Y.NYB"),
]

MOVERS_UNIVERSE = [
    ("S&P 500", "^GSPC"), ("NASDAQ", "^IXIC"), ("Dow Jones", "^DJI"),
    ("FTSE 100", "^FTSE"), ("DAX", "^GDAXI"), ("CAC 40", "^FCHI"),
    ("Nikkei 225", "^N225"), ("Hang Seng", "^HSI"), ("Shanghai Comp", "000001.SS"),
    ("JSE ALSI", "^J203.JO"), ("Sensex", "^BSESN"), ("Brent", "BZ=F"),
    ("Gold", "GC=F"), ("Copper", "HG=F"), ("Platinum", "PL=F"),
    ("USD/ZAR", "USDZAR=X"), ("EUR/USD", "EURUSD=X"), ("USD/JPY", "USDJPY=X"),
    ("Bitcoin", "BTC-USD"), ("US 10Y Yield", "^TNX"),
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
@st.cache_data(ttl=300, show_spinner=False)
def _download(tickers: tuple[str, ...], period: str = "1mo") -> pd.DataFrame:
    """Batch OHLC download; returns empty frame on any failure."""
    if yf is None:
        return pd.DataFrame()
    try:
        df = yf.download(
            list(tickers), period=period, interval="1d",
            group_by="ticker", auto_adjust=True, progress=False, threads=True,
        )
        return df if isinstance(df, pd.DataFrame) else pd.DataFrame()
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
        out.append(q)
    return out


@st.cache_data(ttl=300, show_spinner=False)
def get_history(ticker: str, period: str = "1y") -> pd.Series:
    if yf is None:
        return pd.Series(dtype=float)
    try:
        df = yf.download(ticker, period=period, interval="1d",
                         auto_adjust=True, progress=False)
        return df["Close"].dropna() if not df.empty else pd.Series(dtype=float)
    except Exception:
        return pd.Series(dtype=float)


def get_summary_strip() -> list[Quote]:
    return get_quotes(SUMMARY_STRIP)


def get_commodities() -> list[Quote]:
    return get_quotes([(n, t, "c") for n, t, _ in COMMODITIES])


def get_fx() -> list[Quote]:
    return get_quotes([(n, t) for n, t in FX_MAJORS])


def get_movers(top_n: int = 6) -> tuple[list[Quote], list[Quote]]:
    qs = [q for q in get_quotes(MOVERS_UNIVERSE) if q.ok and q.change_pct is not None]
    qs.sort(key=lambda q: q.change_pct, reverse=True)
    return qs[:top_n], list(reversed(qs[-top_n:]))


# ------------------------------------------------------------ shock alerts
# Derived, factual display of observed moves — thresholds only, no forecasting.
_THRESHOLDS = {
    "index": (2.0, 3.5), "fx": (1.5, 3.0),
    "commodity": (3.0, 6.0), "crypto": (5.0, 10.0),
}


def get_shock_alerts() -> list[dict]:
    alerts = []
    quotes = get_quotes(SUMMARY_STRIP)
    kinds = {t: k for _, t, k, _ in SUMMARY_STRIP}
    extra = get_quotes([("US 10Y Yield", "^TNX"), ("VIX", "^VIX")])
    for q in extra:
        kinds[q.ticker] = "index"
    for q in quotes + extra:
        if not q.ok or q.change_pct is None:
            continue
        warn, crit = _THRESHOLDS.get(kinds.get(q.ticker, "index"), (2.0, 3.5))
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
    return datetime.now(timezone.utc).strftime("%d %b %Y %H:%M UTC")


def clear_caches():
    st.cache_data.clear()
