# RisCura Market News — Project Notes
_Build log and full project state. Written 16 Jul 2026. Start any new working
session by having the assistant read this file._

## What this is
Internal morning-briefing dashboard for RisCura's PM and Research teams.
Streamlit + Plotly + pandas, deployed on Streamlit Community Cloud from the
private GitHub repo **TshirangwanaL/MarketNewRetry** (account
lufuno.tshirangwa001@gmail.com). Access gate: shared APP_PASSWORD.
Deploy routine: replace repo contents with the delivered zip →
`git add . && git commit && git push` → hard refresh (Ctrl+Shift+R).

## Hard rules (from the product owner)
- **No forecasting or trend extrapolation anywhere.** Observation only.
- **No fake/substitute data.** Unavailable sources say so explicitly.
- Brand: RisCura spec v1.4 (Orange #FF671D = emphasis only, Anthracite
  #003B71, forest green #1E8052 / burgundy #B0212C for up/down — pure
  red/green banned; Lato; wordmark never retyped — official SVG at
  `assets/riscura_logo.svg` when committed, typed fallback until then).
- Typography: two tiers — structural labels uppercase 700; interactive
  12px/600 sentence case; metadata 11px. Native theming in
  `.streamlit/config.toml` does most of the work; `assets/styles.css` holds
  only custom components.

## Pages (sidebar order = PM workflow)
Executive Summary → Shock Alerts → Economic Calendar → Market News →
Announcements → Currencies → Commodities → Regional Macro → Weekly Key
Events → Reports → Settings.
- **Exec Summary**: auto-refreshing market strip (fragment, 120s, 1M/1D
  toggle, intraday vs dotted prior close), hero story, movers, calendar
  preview (mini cards), rail: trending pills, keyword alerts, watchlist
  (editable popover), saved articles (team), quick insights.
- **Calendar**: agenda/timeline rows grouped by day, impact+country filters,
  7/14-day horizon (free feed = this week + next week only). Curated SA
  events merge from `data/za_calendar.json` (ships EMPTY — team adds SARB
  MPC / Stats SA dates via git; app never invents dates).
- **Currencies/Commodities**: master-detail with 1M/6M/1Y/5Y range pills and
  range-aware KPIs; FX "all pairs" is a CUSTOM HTML board (native
  LineChartColumn abandoned — it forces thick orange theme sparklines,
  unstylable): thin graphite SVG sparklines (own scale, endpoint dot =
  window direction), window-% column, sort pills (Pair / win % / 1D %),
  hover rows; row-click + selection column removed — pairs open via the
  pills above.
- **Regional Macro**: regions SA, US, Euro Area, UK, China, India, **Japan**.
  Per-region: WB tiles (SA CPI upgraded to SARB monthly), policy rate
  (SA=SARB; US/EA=FRED when keyed), 10Y (US=live; SA=SARB latest, matcher
  prefers **R2035** then R209 — pack uses R2035), 3-year charts per the
  reference pack: SA–Gold, US–WTI, EZ–Brent, China–Copper, Japan–Iron Ore
  (UK→Brent, India→Gold assigned by convention, unconfirmed vs pack), PLUS
  per-region policy-rate & CPI-YoY 3Y monthly histories in pack style
  (marker line; max=green, min=orange, latest=burgundy with value label):
  US & EA charted live from FRED (DFF, ECBDFR, CPIAUCSL→YoY, EA HICP
  CP0000EZ19M086NEST→YoY — YoY is labelled arithmetic on the published
  index, never estimation); SA/UK/CN/IN/JP show named pending source (TE
  key). SARB
  releases grid dedupes anything promoted to headline tiles.
- **Weekly Key Events**: auto-compiled stories (fixed-width badge columns) +
  shared editorial notes: identity-once ("Posting as X"), compact compose,
  in-cell editing with forced Material/Minor declaration, word-diff history
  with per-revision removal, week grouping.
- **Reports**: weekly = Executive Summary only; monthly = full pack;
  downloadable HTML; editorial notes included. Scheduled weekly build:
  `.github/workflows/weekly-report.yml` (Mon 05:00 UTC → commits to
  `reports/`).
- **Settings**: feed status (live diagnostics per source), PM news keyword
  watchlist (shared), PM alert thresholds (shared), admin area (see below).

## Data sources & caveats (the honest list)
- **yfinance**: rate-limited + ~15min delayed; 2-min shared cache; refresh
  button clears ONLY market+news caches and pre-warms before rerun (with
  retries) so 1D charts are correct immediately. JSE ALSI (^J203.JO) patchy;
  iron ore TIO=F and coal MTF=F flaky proxies.
- **Commodities (exact set)**: Brent BZ=F, WTI CL=F, Copper HG=F **COMEX
  $/lb converted ×2204.62 to $/tonne** (pure unit conversion, labelled; LME
  is the premium target), Gold GC=F (COMEX front-month spot proxy), Iron Ore
  62% Fe CFR TIO=F (SGX proxy), Platinum, Coal.
- **SARB Web API**: no key; 41 series live. Field names vary — policy rate
  is literally named "SARB policy rate" (matcher: policy rate/repurchase/
  repo). Same class of bug possible on other series; fix = screenshot of the
  live tile label.
- **World Bank**: annual only (known gap vs pack's monthly cadence).
- **FRED**: key present (FRED_API_KEY). Fills US policy (DFF), US 10Y
  (DGS10), EA policy (ECBDFR), plus 3Y monthly histories for US/EA policy
  and US CPI-U / EA HICP indices (fred.history, 6h cache, ~4 extra calls
  per 6h). Deliberately NOT used for UK/EA/JP/CN/IN
  yields (OECD series discontinued 2024). 120 req/min; app uses a handful/day.
- **Forex Factory calendar**: free JSON (this+next week, majors only).
- **News**: 5 RSS wires fetched in parallel; Google News queries for
  announcements + two SENS candidate feeds (Moneyweb/Sharenet — verify via
  feed status; swap if dead). Region = keyword-or-Global, never outlet
  nationality.
- **Remaining premium ask (precise)**: TE key covers China/India policy
  rates & yields, four international 10Y histories, all Manufacturing
  PMIs, and the SA/UK/CN/IN/JP policy-rate & CPI-YoY 3Y histories. Nothing
  else needs money.

## Classification stack (news)
1. **Directional rules engine** (`data_sources/news.py`): decisive phrases →
   subject×direction pairs (good-up vs bad-up × up/down verbs, subject-then-
   verb binding) → negation flips → legacy word lists as tiebreaker. Word
   lists are team-tunable via git. 8 edge cases in tests.
2. **Triage**: confident rule verdicts (|score|≥2) stand; only ambiguous
   headlines (≤15/cycle, hero always included for its "why") go to a model.
3. **AI layer** (`data_sources/ai_enrich.py`): provider-agnostic. Secrets:
   `LLM_API_KEY` (defaults to Gemini OpenAI-compatible endpoint,
   gemini-2.5-flash; override LLM_API_BASE/LLM_MODEL for Groq/Databricks/
   Mistral) or `ANTHROPIC_API_KEY`. Classifies sentiment AND importance
   (High/Med/Low) + region/asset + hero rationale. Silent fallback to rules.
   Every real call audited.

## Admin & audit
- `ADMIN_PASSWORD` secret unlocks (Settings): **AI audit trail** (every real
  model call: time, provider, headlines sent, fields returned, latency,
  errors; durable via repo store = git-committed/tamper-evident; JSON
  download) and the **Secrets documentation** section. Admin also sees AI
  transparency in-page: ✦ on model-classified stories, counts, hero
  rationale provenance.
- Shared state (`data/app_state.json` via repo store): watchlist, alert
  thresholds, saved articles, news keywords. Editorial notes:
  `data/editorial_notes.json`. All writes are git commits.

## Secrets inventory (names only — values live in Streamlit Cloud Secrets)
APP_PASSWORD (rotate: it appeared in a chat) · GITHUB_TOKEN (fine-grained
PAT, Contents RW — enables shared notes/state/audit) · FRED_API_KEY (set) ·
LLM_API_KEY (Gemini — regenerate after chat exposure) · ADMIN_PASSWORD ·
optional: TE_API_KEY, ANTHROPIC_API_KEY, LLM_API_BASE, LLM_MODEL.

## Known limits / pending
- **SHIPPED (this session) — pack-parity per-region reporting**: each
  Regional Macro tab now opens with an "At a glance" grid (this region
  only): Indicator+source | Latest | Release | Period | 1M/3M/12M Δ.
  Old metric tiles removed (grid subsumes them; SARB `promoted` dedupe
  preserved via _region_rows). Deltas = arithmetic on published
  observations where history exists TODAY: US (CPI YoY, policy, UNRATE
  unemployment, 10Y), EA (HICP YoY, policy), FX all regions (yfinance 2y);
  everything else shows n/a* until the free-API source upgrades land.
  Release column intentionally "—" (free APIs publish measured period,
  not release dates) — richer sources fill it later. US/EA CPI + US
  unemployment latest now come from monthly FRED series instead of WB
  annual (SA CPI stays SARB monthly). "Compare regions" popover per tab:
  opt-in toggle (popovers render eagerly, so the toggle gates the 7-region
  fetch), one indicator at a time, never the default view.
- **SHIPPED (this session) — FX "All pairs" v2, JPM sell-side style**:
  performance ladder (Plotly horizontal diverging bars, ranked by move
  over a 1D/1W/1M/6M/YTD window pill, green/burgundy, outside value
  labels, quote-convention legend) + multi-horizon heat table (1D/1W/1M/
  6M/YTD % per pair from published daily closes, cell tint scales with
  magnitude, full tint at 8%, ZAR pairs pinned first). Sparkline board
  retired (spark_svg kept in ui.py, unused); returns via _fx_returns on
  the cached 2y _fx_series; YTD = vs final close of prior year; 1D = the
  quote's change vs prior close for cross-page consistency.
- **SHIPPED (this session) — Weekly movers fixed**: "Week's largest moves"
  now uses get_weekly_movers — true 1W % (last close vs last close
  on/before 7 calendar days prior, same convention as the FX heat table)
  over the FULL core+extended universe (24 instruments), with an honest
  computation legend. Previously ranked 1-DAY change over core only.
- **SHIPPED (20 Jul) — news permanent fix, all four layers**:
  A. Ingestion — Google News feed now finance-scoped ("stock market OR
  bond market OR financial markets OR equity markets", was bare "markets");
  " - Publisher" suffixes stripped from Google News titles AND summaries;
  title-duplicate summaries suppressed; honest feed labels.
  B. Relevance gate — rules tier (_is_relevant: personal-finance/lifestyle/
  agri markers + first-person-advice regex) drops blatant cases pre-
  classification; model tier adds `relevant` bool per story, _irrelevant
  items dropped post-enrichment. Quirky phrasings can slip rules; the
  scoped feed + model field are the second and third nets.
  C. Classifier — word-boundary regex via _kw/_matches on ALL keyword
  lists (kills wary/Warsh/reward→war, FedEx/Fedorov→fed, brand→rand,
  Indiana→india); n't→not normalisation + negation window extended to
  subject-verb gap ("profits didn't rise" no longer Positive);
  geopolitical lexicon (warns/threats/retaliate/worsen/escalation/
  conflict/skirmish...); corporate-event importance keywords (acquisition/
  merger/earnings/billion/trillion/ipo...); opinion markers downweight
  score −2 and tag "opinion"; TITLE-weighted classification — title
  decides when decisive, summary capped (importance ≤+2, first 160 chars
  for sentiment), visible tags from TITLE ONLY; US region list rebuilt
  without bare "us"/space-hacks.
  D. AI layer — MODEL-PRIMARY: top 50 stories in batches of 25 every
  cycle (was ≤15 ambiguous); provider CHAIN in ai_enrich.providers():
  Anthropic (if keyed) → Gemini (LLM_API_KEY) → Groq (GROQ_API_KEY, base
  api.groq.com/openai/v1, default llama-3.3-70b-versatile, override
  GROQ_MODEL) → rules stand if all fail; audit records the SERVING
  provider per call; provider_label() shows the full chain in feed
  status. Tests 7→14, all diagnosed cases covered.
  ACTION REQUIRED: add GROQ_API_KEY to Streamlit secrets (console.groq.com,
  free) and confirm the regenerated Gemini LLM_API_KEY is actually set.
- **PARTIALLY SHIPPED — observability**: error ring buffer
  (data_sources/obs.py) now captures fail-soft failures (yfinance download/
  history, news feed parse) that previously vanished silently; surfaced on
  Settings → System errors (admin). Page-render smoke test added
  (tests/test_smoke.py — renders all 9 pages against a mocked Streamlit;
  would have caught the cols[2] and _detail_panel bugs). STILL QUEUED for a
  fuller build: classification debugger, per-feed latency/HTTP diagnostics,
  cache observability, data-quality panel, hmac admin-check hardening, and
  wiring the remaining ~8 silent except-blocks into obs.guard().
- **QUEUED — Free-API source upgrades (from reference pack xlsx, 16 Jul;
  after the four NEXT SESSION items, ~2–3 hrs)**: (a) **BIS SDMX API**
  (free, no key) for ALL five policy rates incl. PBoC/BOJ/SARB histories —
  removes them from the TE ask and fills the SA/UK/CN/IN/JP policy-history
  pending blocks; (b) Bundesbank free API — Germany 10Y Bund;
  (c) Japan MOF published CSV — 10Y JGB; (d) Eurostat keyless API — EZ
  CPI/GDP/unemployment; (e) IMF IFS / DBnomics — China GDP/CPI;
  (f) World Bank Pink Sheet monthly — iron ore; (g) e-Stat (free
  registration) — Japan CPI/unemployment. Irreducible paid/manual residue
  after this: all 5 PMIs (ISM/Caixin/HCOB/Jibun/Absa — proprietary press
  releases; TE key or manual monthly entry), LME copper (COMEX conversion
  stays the labelled proxy), China 10Y CGB (no open API). Reference-pack
  audit notes: its "Methodology & Sources" tab is MISSING from the file,
  and its commodities 12M forecasts use trend extrapolation (banned here).
- Identity is one shared password; real roles need **Entra OIDC** (IT app
  registration). Names on notes are self-declared until then.
- Keyword alerts are in-app only; email/Teams push needs SMTP/webhook.
- Databricks LLM route: manager raising access (login blocked at Entra —
  Reference ID logged); provider-agnostic layer ready, 3 secrets to switch.
- `data/za_calendar.json` still empty — team to add SARB/Stats SA dates.
- Official wordmark SVG not yet committed.
- Mobile untested; Streamlit ceiling: no transitions/pixel layout/spinnerless.
- Tests: `python tests/test_logic.py` (7) — run after any classifier edit.

## Free-API hunt for the "irreducible" gaps (researched, not assumed)
Findings on the 3 items previously marked no-free-API:

1. **China 10Y government bond yield** — LIKELY AVAILABLE FREE via FRED/OECD.
   OECD publishes "Long-Term Government Bond Yields: 10-Year: Main" on FRED
   under pattern IRLTLT01{CC}M156N (confirmed live for US=IRLTLT01USM156N,
   and FRED lists UK/JP/EA/Canada as siblings). China candidate =
   IRLTLT01CNM156N (MONTHLY, OECD MEI). Also confirmed China sits in FRED's
   OECD MEI family (IR3TTS01CNM156N = China 3M T-bill yield is live).
   CAVEAT: monthly (not daily) and I could NOT hit fred.* from the build
   sandbox (not in egress allowlist → 403), so the exact CN 10Y id is
   UNVERIFIED. ACTION: on deploy (has FRED_API_KEY + net), test
   fred.latest("IRLTLT01CNM156N"); if 400/empty, try the OECD SDMX direct
   API (stats.oecd.org / sdmx.oecd.org, no key) for DSD MEI IRLTLT01.CHN.
   If both fail, keep labelled "TradingEconomics/manual".
2. **LME copper** — still no free official LME feed; COMEX HG=F ×2204.62
   proxy stays (labelled). OECD/FRED don't carry LME cash. UNCHANGED.
3. **PMIs (ISM/Caixin/HCOB/Jibun/Absa)** — still proprietary press releases,
   no free API. UNCHANGED (TE key or manual monthly).

Bonus: FRED/OECD IRLTLT01 family also gives FREE monthly 10Y for UK
(GB), Japan (JP), India (IN?), SA (ZA?) — worth wiring to fill the
Regional Macro 10Y pending-blocks alongside the BIS policy-rate upgrade,
if daily granularity isn't required (these are month-end).

## API AUDIT (systematic double-check) — 21 Jul 2026
Verified every external data source: is it free, live, correctly labelled, gracefully degrading.

**yfinance (markets, FX, commodities, indices)** — free, no key, ~15min delayed.
- VERIFIED tickers resolve: S&P500 ^GSPC, JSE ALSI ^J203.JO, FX =X pairs, GC=F/BZ=F/HG=F/PL=F/TIO=F.
- FIXED THIS AUDIT: MTF=F is API2 (Rotterdam/European coal), NOT Newcastle — relabelled
  "Coal API2 Rotterdam (proxy)" (was mislabelled "Newcastle proxy"). Same class of error as the
  earlier Iron Ore SGX→CME fix. BoP note updated: SA coal actually prices nearer API4/Richards Bay.
- Batched history (get_history_batch) collapses per-instrument fan-out; 300s cache.
- RISK: unofficial/undocumented; can break without notice. Mitigated by shared cache + graceful n/a.

**FRED (US/EA rates, CPI, unemployment, intl 10Y, US yield curve)** — free key, 120 req/min.
- VERIFIED live & current: DGS10, DFF, ECBDFR, CPIAUCSL, UNRATE, and full CMT curve
  (DGS1MO…DGS30, updated within days as of this audit).
- OECD intl 10Y (IRLTLT01xx) — SOME discontinued 2024; accessed only via latest_fresh() staleness
  guard (>120d old → honest blank). Cannot verify live from sandbox; guard makes safe either way.
- 6h cache.

**SARB Web API** (custom.resbank.co.za/SarbWebApi) — free, no key, SA-specific.
- 4 endpoints (HomePageRates, CurrentMarketRates, Prices SDDS, RealSector SDDS). Tolerant parsing.
- _dup() filter drops metal/FX that duplicate Commodities/Currencies; admin leak-check confirms.
- 1h cache.

**Forex Factory calendar** (nfs.faireconomy.media ff_calendar_*.json) — free public feed.
- VERIFIED still live at the URL used. CRITICAL RATE LIMIT (confirmed this audit): max 2 weekly
  downloads / 5 min since Aug 2024; over-limit returns "Request Denied" HTML, not JSON.
- APP RESPECTS IT: 3600s (1h) shared cache = ~1 fetch/hour, well under limit. Over-limit HTML →
  r.json() raises → except → tries mirror (cdn-nfs) → graceful. Robust.

**Google News RSS + Moneyweb/Sharenet SENS feeds** (news.py) — free RSS.
- Finance-scoped queries. Parsed defensively. 15min cache. Low risk (RSS is stable), but SENS
  feeds are best-effort (Moneyweb/Sharenet may change paths). Degrade to empty, don't crash.

**Trading Economics calendar** (api.tradingeconomics.com) — PAID key (TE_API_KEY), optional.
- Only used if key present; otherwise Forex Factory is the calendar source. Not relied upon.

**AI providers** (Gemini generativelanguage / Groq / Anthropic) — keys; free tiers for Gemini+Groq.
- Chain Gemini→Groq→rules, retry-with-backoff on 429/503. Two models before rules fallback.

**World Bank** (api.worldbank.org/v2) — free, no key, annual macro. Stable. 6h+ cache.

**GitHub API** (app_state persistence) — GITHUB_TOKEN. For committing app-state/weekly report.

NOT USABLE (confirmed, not integrated): Refinitiv/Eikon (paid enterprise, no free API);
US Treasury physical trade tonnage (SARS PDF only); LME copper (COMEX proxy stays); PMIs (proprietary).

## REAL SARB Balance of Payments (replaced commodity proxy) — 22 Jul 2026
User asked: is there a published BoP from SARS/SARB/StatsSA? YES — SARB publishes the
official BoP (Quarterly Bulletin). Replaced the commodity-value PROXY with the real thing.

DECISION: team needs it current monthly. Approach = live-source-first.
- FOUND: SARB Web API has ReleaseOfSelectedData + MonthlyIndicatorsAll/{dataType} endpoints
  (verified via Swagger help page). These expose BoP/trade indicators live as JSON — same API
  the app already uses for rates. Fields: MeasureName, Value, Period, CategoryName, FormatNumber.
- BUILT: sarb.get_balance_of_payments() hits MonthlyIndicatorsAll/CurrentData, filters rows by
  _BOP_KEYWORDS (current account / trade balance / …), returns {live, as_of, rows, source_url}.
  Each row carries its own Period → trade balance (monthly) and current account (quarterly) each
  show at native frequency. Cached 6h.
- FALLBACK (never silently stale): if live feed unreachable / category names differ, returns
  dated official figures — Q1 2026: current account R190.7bn (2.4% GDP), trade balance R437.9bn —
  clearly stamped "latest published: Q1 2026" + link to SARB current-account-release page.
- CAVEAT: exact MonthlyIndicatorsAll category/keyword matching UNVERIFIED from sandbox (can't reach
  custom.resbank.co.za). On deploy, if live=False when it should be live, tune _BOP_KEYWORDS /
  the dataType path against the real response. Dated fallback makes it safe either way.
- Commodity panel RE-FRAMED: no longer "the BoP" — now "Commodity export drivers" (supporting
  context, live price moves + 2025 export values), sitting BELOW the real BoP. Honest separation:
  real official BoP up top, commodity drivers as the what-pushes-on-it lens below.
- SPURIOUS-CONTENT NOTE: a Global Business Outlook article on the Q1 2026 CA had injected/implausible
  claims (SARB citing "Iran war" and "Anthropic Claude Mythos Preview" as financial-stability risks).
  IGNORED those; used only the hard CA numbers, corroborated across SARB site + Trading Economics.

TODO on next deploy: verify get_balance_of_payments() returns live=True; if not, adjust the
dataType segment (tried CurrentData) and _BOP_KEYWORDS to match SARB's actual category labels.

## SARS trade portal — the single consistent commodity source (data layer built) — 22 Jul 2026
User pushed to find ONE source for SA per-commodity exports spanning annual + monthly 2026,
same currency/definitions, to enable a real period-movement statement. FOUND IT:
- SARS Trade Statistics data-download portal: https://tools.sars.gov.za/tradestatsportal/data_download.aspx
- Official SA customs data, FREE, per HS chapter, monthly AND annual, ZAR, one definition, to 2026.
- Fields incl. TradeType, Chapter (bare "71"), ChapterAndDescription, YearMonth/CalendarYear,
  CustomsValue, StatisticalQuantity. Chapters we track: 26 Ores, 27 Coal/Crude/Petroleum,
  71 Gold/Platinum/Precious, 74 Copper.
- CATCH: it's an ASP.NET viewstate form (not a REST API), and UNTESTABLE from the build sandbox
  (network allowlist excludes tools.sars.gov.za).

BUILT (data_sources/sars_trade.py): three-tier sourcing, each honest about which it used:
  1. LIVE  — _try_live() replicates the form POST (viewstate GET then POST). Best-effort; field
             names/handshake may need tuning on first deploy.
  2. CSV   — reads data/sars_trade.csv that the user downloads from the same portal (robust; real
             data; monthly human step). Parser prefers bare Chapter col, tolerant of quoted commas
             in descriptions, sums months per chapter, excludes imports.
  3. DATED — _DATED fallback (2025 annual chapter values, ZAR bn, stamped) so never blank/silently stale.
get_commodity_exports() -> {source, as_of, unit, rows[{chapter,label,value,period}], source_url}.
Test: test_sars_trade_parser (23 logic tests now). data/sars_trade_README.md documents CSV drop.

NOT YET DONE (next step): wire get_commodity_exports() into the Commodities page as a period-movement
statement. Current commodity-drivers panel still uses worldstopexports 2025 USD values. Deciding how to
present movement (annual vs latest-month columns) and whether to switch the driver values to the SARS
chapter basis (coarser but consistent + movement-capable) is the pending UI decision.
DEPLOY TODO: confirm _try_live() returns rows; if not, tune the POST field names / viewstate handling
against the real portal, or rely on the CSV path (which is robust).

## SARS cumulative commodity statement WIRED into Commodities page — 22 Jul 2026
Followed SARS's own presentation (better than a generic financial statement): their headline
commodity report is "Top 10 Cumulative Commodities" = YTD ranking. Standard trade-authority
layout = current month + cumulative YTD this year + prior-year YTD + YoY %. Adopted that.
DECISIONS (user): (1) SARS cumulative format: This-yr YTD | Last-yr YTD | YoY Δ% | latest month.
(2) SARS chapter basis accepted — ch71 combines gold+platinum+precious (coarser but consistent
& movement-capable, which fine 4-digit lines can't be from a single source).
BUILT: sars_trade.get_commodity_movement() → _cumulative_by_chapter() computes like-for-like YTD
(Jan..latest month both years), YoY %, latest-month value, per chapter. Three-tier source (live/
csv/dated) as before. Commodities page "Commodity export drivers" now renders the SARS cumulative
table (YTD cy | YTD py | YoY | latest month + tracked total + YTD share%), with the live spot-price
moves kept as a small secondary table beneath (leading indicator). CSS: bops-val 190→150px,
bops-move 90→95px to fit multi-column. Test test_sars_trade_parser covers parse+cumulative (23 tests).
NOTE: worldstopexports 2025 USD values (macro.SA_TRADE_TOTALS / SA_BOP_EXPOSURES value_bn) no longer
drive the drivers table — SA_BOP_EXPOSURES still used for the spot-price rows (names/tickers) and its
value fields are now unused-but-harmless. SA_TRADE_TOTALS likely orphaned (left in place).
DEPLOY TODO unchanged: confirm _try_live_rows() returns rows; else use CSV path (data/sars_trade.csv).

## Commodity view unified as "contribution to exports" breakdown — 22 Jul 2026
User: the four-step BoP descent was wrong; and "R811bn" as a lump was insufficient — needed the
per-commodity breakdown (rand value + % of TOTAL exports) showing HOW the 37% is built.
Mockups iterated (part-to-whole chain rejected → per-commodity breakdown accepted).
DECISIONS: (1) unify into ONE commodity view — the cumulative table's % is now share of TOTAL
exports (not tracked subset), building to the tracked subtotal and reconciling to 100%. (2) keep
per-commodity proportion bars. (3) spot-price % table REMOVED entirely (not what user asked for).
DONE in views/markets_pages.py page_commodities():
- Removed the live spot-price move table block (quotes still used by the commodity picker up top).
- Added proportion bars under each commodity label (.bops-bar/.bops-bar-fill CSS), width scaled to
  max tracked share so relative size is visible at a glance.
- Added a "How the tracked share builds" caption showing the explicit sum
  (e.g. 17.4 + 10.7 + 7.6 + 1.1 = 36.9% of total SA exports).
- Table already reconciled vs total exports (categories → tracked subtotal → all-other residual →
  100%) from the prior change; this makes the build-up legible + visual.
Share basis is now TOTAL exports (gold/platinum reads 17.4%, its true basket weight), not subset.
Period-honesty caption retained: commodity YTD (SARS) vs trade/CA (SARB quarterly) = share not sum.

## Commodity view rebuilt as five-period MOVEMENT table — 22 Jul 2026
User (explicit, simple ask): track the commodities we follow, break down their value + % per
REPORTED PERIOD, so movement is observable. Drop vague single % and the orange bars.
DECISIONS: (1) period-comparison columns: This month | Last month | Same month last year |
YTD this year | YTD last year, PER COMMODITY. (2) each cell shows rand value AND % share.
(3) keep the trade-balance/BoP link as context.
DATA (sars_trade.py _cumulative_by_chapter): now computes 5 periods per chapter
(this_month, last_month, same_month_ly, ytd, ytd_prev) each with its OWN per-period total-exports
denominator (so the % share is correct for THAT period, not a single YTD denom). __total__ is now
a dict of per-period totals. _pack_movement carries `totals` dict + latest_month/prev_month labels.
_DATED_MOVE rewritten with the 5 periods + per-period totals (Apr 2026 vs Mar 2026 / Apr 2025).
VIEW (markets_pages.py): new CSS-grid table `.cm` (name + 5 period cols + YoY), each cell = value
over % (cm-val / cm-pct orange). Tracked-commodities subtotal row + Total SA exports row (100%).
Removed the old single-% cumulative table, the proportion bars (.bops-bar) and builds-to caption.
Caption explains: read movement across columns; % is share of total exports per period; YoY
like-for-like; BoP period-honesty note retained. Test extended (5-period asserts). 23 logic tests.
NOTE: .bops-bar CSS now unused (harmless); bops-share-inline still used by BoP section? check later.

## Commodity movement table — accounting audit + fixes, and SARS pull documented — 22 Jul 2026
User asked (a) document the SARS pull step by step, (b) audit the table for strict-accounting
explainability/labelling. Did both.

AUDIT FINDINGS (table would NOT have passed as shown in screenshot):
1. Shares jumped 46.4% (tracked) → 100% (total) with NO bridge — the reconciling residual had
   been dropped in the 5-period rebuild. REGRESSION.
2. "YoY" column undefined — didn't state it was YTD-vs-YTD (could read as Apr-vs-Apr).
3. Monthly and YTD columns jammed together with no grouping/divider; order current→backwards.
4. Per-figure provenance not visible; "Total 100%" invited treating dated approx as audited fact.
5. No preliminary/revisable flag (SARS revises 5 yrs).

FIXES (all done, decisions from user):
- Re-added "All other exports" reconciling residual (= total − tracked). Verified it FOOTS in
  every period: tracked + residual = total, shares sum to exactly 100% (this_month 46.4%+53.6%,
  ytd 46.0%+54.0%, etc.).
- Split change into TWO labelled columns: "MoM Δ" (this vs last month) and "YoY Δ (YTD)"
  (YTD cy vs py) — each states its basis.
- Regrouped columns: monthly block [this | last | same-month-LY | MoM Δ] then a vertical divider
  (.cm-div border-left) then YTD block [YTD cy | YTD py | YoY Δ].
- Every share cell now labelled "X% of exports". Caption spells out how to read it, DEFINES the
  four tracked chapters by number, states figures are preliminary/SARS-revisable, and keeps the
  SARS-period-vs-SARB-quarterly BoP honesty note.
- CSS: .cm grid now name + 7 cols; .cm-div divider; .cm-resid italic grey residual row.

SARS PULL — DOCUMENTED in data/sars_trade_README.md (step by step): portal URL; Trade Type=Exports;
Focus Area=Tariffs (not Countries); Country=South Africa reporter / all destinations; Chapters
26,27,71,74 (+ Select all for the total/residual); Period = latest month + prior + same-month-LY +
YTD both years (pick 2 latest years); Columns TradeType/Chapter/YearMonth/CustomsValue; save as
data/sars_trade.csv; refresh monthly (14:00 last working day; preliminary, revised up to 5 yrs).
Why chapter-level (71 combines gold+platinum) documented. 23 logic tests, 9 smoke, pyflakes clean.
