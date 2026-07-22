# Commodity trade data — sources, step by step

The commodity trade statement is sourced in three tiers, automatically, best first:

1. **UN Comtrade** (primary) — the UN's official global trade database. Uses the
   **public preview endpoint, which needs NO key or registration at all.** It's
   capped at 500 records per call, which comfortably covers what this dashboard
   asks for (4 chapters x a few recent months x 2 flows). Values are in **USD**.
2. **SARS CSV** (manual fallback) — drop a file at `data/sars_trade.csv` if you want
   to override with SARS's own ZAR figures. Details below.
3. **Dated fallback** — built-in illustrative figures, clearly stamped, if neither
   of the above is available.

## UN Comtrade — nothing to set up

Because this dashboard's needs are small, it uses Comtrade's free, keyless
**public preview** endpoint (`comtradeapi.un.org/public/v1/preview/...`). There is
**no registration, no key, nothing to paste into secrets.** It should just work.

If you ever want higher limits (e.g. for a much bigger pull elsewhere), you can
optionally register a free key at https://comtradedeveloper.un.org/ (pick the
"comtrade - v1" product) and add it as `COMTRADE_API_KEY` in the app's secrets —
the app will send it if present, but it isn't required for this dashboard.

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
