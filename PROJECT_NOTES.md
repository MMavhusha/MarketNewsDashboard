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
- **NEXT SESSION — Admin/developer observability page (~90–120 min)**:
  dedicated admin-only page, unlocked via existing ADMIN_PASSWORD (harden
  the Settings check from plain == to hmac.compare_digest). Panels:
  (a) classification debugger — paste any headline, see the full trace
  (which phrase / subject×verb rule fired, score, confident flag,
  rules-vs-model provenance, relevance verdict once the gate exists);
  (b) per-story AI provenance beyond the ✦ marks; (c) AI audit trail
  extended with latency/error/provider stats; (d) feed diagnostics per
  source (fetch latency, item counts, HTTP status, parse failures);
  (e) error ring buffer — the app fails soft with bare `except` everywhere
  so errors vanish silently today; capture in-memory for admin view;
  (f) cache observability (TTLs, last refresh, per-cache clear);
  (g) data quality (stale quotes by asof age, n/a instruments, history
  gaps); (h) system info (package versions, deploy SHA, secrets-presence
  checklist — names only, never values).
  Tomorrow's full queue ≈ 3.5–4.5 hrs: FX board + movers fix + news
  3-layer fix + admin build.
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
