# SARS trade CSV (optional, for commodity export data)

The commodity export figures on the Commodities page can be sourced from SARS
customs data (official, free, per HS chapter, monthly + annual, ZAR).

Sourcing is three-tier and automatic:
1. LIVE  — the app tries the SARS portal directly.
2. CSV   — if the live scrape is unavailable, the app reads `sars_trade.csv`
           in this folder (if present).
3. DATED — otherwise it shows the last recorded figures, clearly stamped.

## To provide the CSV (tier 2)
1. Go to https://tools.sars.gov.za/tradestatsportal/data_download.aspx
2. Trade Type = Exports; select the year(s)/month(s) you want; select all
   chapters (or at least 26, 27, 71, 74); Select All columns.
3. Download and save the file here as exactly `sars_trade.csv`.
The app will pick it up automatically (needs Chapter, CustomsValue, YearMonth
columns; TradeType if present). Refresh monthly to keep it current.
