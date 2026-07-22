# SARS trade data — how to pull it, step by step

The commodity export movement table is sourced from SARS customs data (official,
free, per HS chapter, monthly + annual, in ZAR, one product definition). Sourcing
is three-tier and automatic: LIVE scrape → CSV drop (this folder) → dated fallback.

## What we pull, and every parameter

SARS Trade Statistics data-download portal:
https://tools.sars.gov.za/tradestatsportal/data_download.aspx

Set the form exactly as follows to reproduce the table's data:

1. **Trade Type = Exports AND Imports.** Pull BOTH. The movement and
   contribution statements use exports; the per-commodity net-trade
   reconciliation needs imports too (net = exports minus imports), so the
   coal/crude chapter correctly shows as a net importer. Do two downloads
   (one Exports, one Imports) and concatenate into one CSV, or select both
   trade types if the portal allows. The parser reads the TradeType column.

2. **Focus Area = Tariffs** (i.e. break the data down by HS tariff chapter),
   NOT "Countries." We want what is exported, by commodity, not by destination.

3. **Country = South Africa** as the reporter. On the SARS portal this is implicit
   (it is SA's own customs authority reporting SA trade). If a country selector is
   shown for trade partners, leave it as "Select all" / all destinations, because we
   want SA's TOTAL exports of each commodity to the world, not to one partner.

4. **Chapter = the four we track (plus "Select all" if you also want the true
   total-exports denominator):**
   - 26 — Ores (iron ore, manganese, chrome)
   - 27 — Crude, Coal, Petroleum
   - 71 — Gold, Platinum, Diamonds, Jewellery and Precious Metals
   - 74 — Copper and Articles Thereof
   To reproduce the "Total SA exports" / "All other exports" reconciliation lines,
   select ALL chapters — the app sums the non-tracked chapters into the residual.

5. **Period = the months/years you want.** For the movement table we need, per the
   latest available month: that month, the prior month, the same month one year
   earlier, and Jan..that-month for the current and prior year (YTD). Selecting the
   two most recent full years covers all five periods.

6. **Columns (Select All, or at minimum):** TradeType, Chapter, YearMonth (or
   CalendarYear), CustomsValue. StatisticalQuantity optional. The parser prefers the
   bare `Chapter` column ("71") and reads `CustomsValue`; it is tolerant of quoted
   commas in `ChapterAndDescription`.

7. Download and save the file here as exactly **`sars_trade.csv`**. The app picks it
   up automatically. Refresh monthly (SARS publishes at 14:00 on the last working
   day of the month; figures are preliminary and revised for up to 5 years).

## Why chapter level (not finer)
SARS exposes this cleanly at 2-digit HS chapter. Chapter 71 therefore combines gold,
platinum and other precious metals into one line — coarser than splitting platinum
and gold, but it is ONE consistent source that supports real period-over-period
movement, which finer split lines cannot (no single free source publishes them
consistently over time). The table labels this explicitly.

## Units and reconciliation
Values are ZAR. Each period's share is that commodity's CustomsValue divided by the
SAME period's total exports, so shares foot: the four tracked chapters + "all other
exports" = 100% of total exports, every period.
