# RisCura Market News Dashboard

Institutional market news and macro dashboard for Portfolio Management and
Investment Research. Streamlit + Plotly + custom CSS; free live data sources
behind swappable provider modules (Bloomberg / Reuters / IMF / central banks /
J.P. Morgan / RiscFlash / Trading Economics ready). No forecasting or trend
extrapolation anywhere — current and historical published data only.

## Structure
```
streamlit_app.py        entry point: auth, nav, router
auth.py                 password gate (APP_PASSWORD secret)
assets/styles.css       design system (hides Streamlit chrome)
components/             ui.py (cards/badges/hero) · charts.py (Plotly themes)
data_sources/           markets.py (yfinance) · news.py (RSS + rule tagging)
                        macro.py (World Bank + provider registry)
                        calendar_data.py (Trading Economics)
views/                  core.py · markets_pages.py · reports.py
```

## Deploy to Streamlit Community Cloud (private repo)

1. Push this folder to `TshirangwanaL/MarketNewRetry`:
   ```bash
   cd market-news-dashboard
   git init && git add . && git commit -m "Market News dashboard v1"
   git branch -M main
   git remote add origin https://github.com/TshirangwanaL/MarketNewRetry.git
   git push -u origin main
   ```
2. Go to https://share.streamlit.io → Sign in with the GitHub account
   (lufuno.tshirangwa001@gmail.com) → New app → authorize the Streamlit app
   for private repos → pick `TshirangwanaL/MarketNewRetry`, branch `main`,
   file `streamlit_app.py`.
3. App → Settings → Secrets, add:
   ```toml
   APP_PASSWORD = "choose-a-strong-password"
   # optional, full economic calendar coverage:
   # TE_API_KEY = "your_user:your_key"
   ```
4. Deploy. The shareable URL is `https://<app-name>.streamlit.app`.

## Reporting
Weekly = Executive Summary only; Monthly = full pack (Reports page toggle;
print → Save as PDF for distribution).

## Notes
- Every fetcher fails soft to an explicit "unavailable" state — no fabricated data.
- JSE ALSI (^J203.JO) has patchy free coverage; the card labels itself
  unavailable when Yahoo returns nothing.
- Shock alerts are threshold rules on observed session moves (display only).
