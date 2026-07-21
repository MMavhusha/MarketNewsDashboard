"""Canonical source-of-truth registry.

The dashboard pulls from several providers (yfinance, SARB, FRED, OECD-via-FRED,
World Bank). Some real-world figures are available from more than one of them,
which risks two pages reporting different numbers for the same thing. This
registry names the SINGLE canonical owner of each figure so the rest of the app
can defer to it, and gives the admin diagnostics a spec to check live values
against.

This is documentation-as-code: it does not fetch anything itself. It records the
deliberate ownership decisions, with the reasoning, so future changes don't
silently reintroduce a duplicate.
"""
from __future__ import annotations

# figure key -> (canonical source, where it is shown, note on why / how dups avoided)
CANONICAL = {
    # ---- Prices (single owner: yfinance, shared 300s cache) ----
    "gold_price": ("yfinance GC=F", "Commodities",
                   "One yfinance download cache feeds strip, Commodities and "
                   "movers, so the price is identical everywhere. SARB gold "
                   "series is filtered out of Regional Macro to avoid a second "
                   "figure."),
    "usdzar_spot": ("yfinance USDZAR=X", "Currencies",
                    "Spot rand rate. SARB raw FX series filtered out of "
                    "Regional Macro; SARB REER is kept (a different figure — "
                    "trade-weighted index, not spot)."),

    # ---- Rates & yields (region-gated so no cell has two sources) ----
    "us_10y": ("FRED DGS10", "Regional Macro · US",
               "US-only branch; never competes with OECD series."),
    "sa_10y": ("SARB R2035 bond", "Regional Macro · South Africa",
               "SA prefers the live SARB bond; the OECD za_10y series is NOT "
               "wired for SA (only UK/JP/IN/CN), so the SARB figure is the sole "
               "SA 10Y owner."),
    "intl_10y": ("OECD via FRED (IRLTLT01)", "Regional Macro · UK/JP/IN/CN",
                 "Only used where no native source exists; freshness-guarded."),
    "us_policy": ("FRED DFF", "Regional Macro · US", "US-only branch."),
    "ea_policy": ("FRED ECBDFR", "Regional Macro · Euro Area", "EA-only branch."),
    "sa_policy": ("SARB repo/prime", "Regional Macro · South Africa",
                  "SARB is the SA monetary owner."),

    # ---- Inflation (region-gated) ----
    "us_cpi": ("FRED CPIAUCSL", "Regional Macro · US", "US-only branch."),
    "ea_hicp": ("FRED HICP (Eurostat)", "Regional Macro · Euro Area", "EA-only."),
    "sa_cpi": ("SARB CPI", "Regional Macro · South Africa", "SARB is SA owner."),

    # ---- Macro aggregates (World Bank only, annual) ----
    "gdp_growth": ("World Bank (annual)", "Regional Macro",
                   "World Bank is the sole GDP source; no overlap with FRED "
                   "which supplies rates/CPI, not GDP here."),
    "unemployment": ("World Bank (annual), except US=FRED UNRATE", "Regional Macro",
                     "US uses FRED UNRATE (monthly, fresher); all other regions "
                     "use World Bank. Region-gated, so never two figures in one "
                     "cell."),
}


def owner(figure_key: str) -> str | None:
    entry = CANONICAL.get(figure_key)
    return entry[0] if entry else None


def as_rows() -> list[dict]:
    """Flatten for display in the admin diagnostics panel."""
    return [{"figure": k, "canonical_source": v[0], "shown_on": v[1],
             "reconciliation": v[2]} for k, v in CANONICAL.items()]
