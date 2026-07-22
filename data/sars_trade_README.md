# Commodity trade data — sources, step by step

The commodity trade statement is sourced in three tiers, automatically, best first:

1. **UN Comtrade** (primary) — the UN's official global trade database, free, with
   a real JSON API. Does South Africa, monthly, per HS chapter, exports AND imports,
   vs the World aggregate. This is the proper programmatic source and needs no manual
   downloads. Values are in **USD**.
2. **SARS CSV** (manual fallback) — drop a file at `data/sars_trade.csv` if you want
   to override with SARS's own ZAR figures. Details below.
3. **Dated fallback** — built-in illustrative figures, clearly stamped, if neither
   of the above is available.

## Setting up UN Comtrade (do this once)

1. Go to https://comtradedeveloper.un.org/ and register (free).
2. Follow their sign-up steps, and when asked to pick a product, choose the free
   one: **"comtrade - v1"**.
3. Once registered, your profile shows a **subscription key** (a "primary key").
   Copy it.
4. Put it in the app's secrets as **`COMTRADE_API_KEY`**:
   - On Streamlit Community Cloud: app -> Settings -> Secrets, add a line
     `COMTRADE_API_KEY = "your-key-here"`
   - Locally: add the same line to `.streamlit/secrets.toml`, or set an environment
     variable `COMTRADE_API_KEY`.
5. Save and let the app restart. The commodity statement's source label will read
   "UN Comtrade" and the figures will be live.

Free tier limits are 500 API calls/day and 100,000 rows/call — far more than this
dashboard needs (it makes two small calls per refresh, cached for six hours).

### What the app pulls from Comtrade
- Reporter: South Africa (code 710)
- Partner: World (code 0) — the all-destinations aggregate
- Commodities: HS chapters 26 (ores), 27 (coal/crude/petroleum),
  71 (gold/platinum/precious metals), 74 (copper), plus the "TOTAL" of all
  commodities so shares and the trade balance reconcile
- Flows: exports and imports (both), monthly, most recent months available

### A note on currency and definitions
Comtrade values are USD, so the trade balance shown is a USD figure (the app labels
it as such). There can be small definitional differences from SARS's own ZAR
figures — Comtrade uses countries' reported data on a standard basis. For showing
each commodity's share and net contribution, USD is fine and matches the USD
commodity spot prices elsewhere in the dashboard.

## SARS CSV fallback (only if you want ZAR / to override Comtrade)

SARS Trade Statistics data-download portal:
https://tools.sars.gov.za/tradestatsportal/data_download.aspx

Note: this portal is a restricted BETA and can be awkward — no country aggregate
(only per-country rows), mandatory tariff selection, and a size cap, so large
requests may fail to download. If it won't cooperate, use the Comtrade path above.
If you do use it:

1. Trade Type = Exports AND Imports (both; the net reconciliation needs imports).
2. Focus Area = Tariffs, and set Tariff = Select all within each chapter.
3. Chapters = 26, 27, 71, 74 (and Select all if you want the total/residual).
4. Country = Select all destinations (the parser sums per-country rows into a total).
5. Period = the two most recent years, all months.
6. Columns = at least TradeType, Chapter, YearMonth, CustomsValue.
7. Save the combined file as exactly data/sars_trade.csv. Values are ZAR.

If the portal caps the download, pull one chapter or one month at a time and
concatenate the CSVs (one header row, then all data rows).
