# data/
- `za_calendar.json` — team-curated South African calendar events (SARB MPC
  dates, Stats SA CPI/GDP releases). The app merges these into the Economic
  Calendar with your stated source; it never invents dates. Add entries via a
  normal git commit using the format documented in
  `data_sources/calendar_data.py` (`_curated_za`).
- `editorial_notes.json` / `app_state.json` — created automatically by the app
  when a GITHUB_TOKEN secret is configured.
