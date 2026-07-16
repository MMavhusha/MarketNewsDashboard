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
  range-aware KPIs; FX "all pairs" is a sortable native grid (neutral
  sparklines, trend-window pills, row-click opens the pair; selection column
  is the accepted cost of row-click).
- **Regional Macro**: regions SA, US, Euro Area, UK, China, India, **Japan**.
  Per-region: WB tiles (SA CPI upgraded to SARB monthly), policy rate
  (SA=SARB; US/EA=FRED when keyed), 10Y (US=live; SA=SARB latest, matcher
  prefers **R2035** then R209 — pack uses R2035), 3-year charts per the
  reference pack: SA–Gold, US–WTI, EZ–Brent, China–Copper, Japan–Iron Ore
  (UK→Brent, India→Gold assigned by convention, unconfirmed vs pack). SARB
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
  (DGS10), EA policy (ECBDFR). Deliberately NOT used for UK/EA/JP/CN/IN
  yields (OECD series discontinued 2024). 120 req/min; app uses a handful/day.
- **Forex Factory calendar**: free JSON (this+next week, majors only).
- **News**: 5 RSS wires fetched in parallel; Google News queries for
  announcements + two SENS candidate feeds (Moneyweb/Sharenet — verify via
  feed status; swap if dead). Region = keyword-or-Global, never outlet
  nationality.
- **Remaining premium ask (precise)**: TE key covers China/India policy
  rates & yields, four international 10Y histories, and all Manufacturing
  PMIs. Nothing else needs money.

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
- Identity is one shared password; real roles need **Entra OIDC** (IT app
  registration). Names on notes are self-declared until then.
- Keyword alerts are in-app only; email/Teams push needs SMTP/webhook.
- Databricks LLM route: manager raising access (login blocked at Entra —
  Reference ID logged); provider-agnostic layer ready, 3 secrets to switch.
- `data/za_calendar.json` still empty — team to add SARB/Stats SA dates.
- Official wordmark SVG not yet committed.
- Mobile untested; Streamlit ceiling: no transitions/pixel layout/spinnerless.
- Tests: `python tests/test_logic.py` (7) — run after any classifier edit.
