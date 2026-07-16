"""Core pages: Executive Summary, Market News, Shock Alerts,
Company Announcements, Economic Calendar."""
from __future__ import annotations

import streamlit as st
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from components import charts, ui
from data_sources import calendar_data, markets, news


# ------------------------------------------------------------ shared bits
def render_summary_strip():
    quotes = markets.get_summary_strip()
    primary = [q for q in quotes if q.name in markets.SUMMARY_PRIMARY]
    rest = [q for q in quotes if q.name not in markets.SUMMARY_PRIMARY]
    c1, c2 = st.columns(2, gap="medium")
    halves = [primary[: (len(primary) + 1) // 2], primary[(len(primary) + 1) // 2:]]
    for col, half in zip((c1, c2), halves):
        with col, st.container(border=True):
            for q in half:
                fig = charts.sparkline(q.spark, height=34) if q.ok and len(q.spark) > 2 else None
                ui.summary_row(q, fig, key=f"spark_{q.ticker}")
    with st.expander(f"View all markets ({len(rest)} more)"):
        cc1, cc2 = st.columns(2, gap="medium")
        halves = [rest[: (len(rest) + 1) // 2], rest[(len(rest) + 1) // 2:]]
        for col, half in zip((cc1, cc2), halves):
            with col:
                for q in half:
                    fig = charts.sparkline(q.spark, height=34) if q.ok and len(q.spark) > 2 else None
                    ui.summary_row(q, fig, key=f"spark2_{q.ticker}")


def _news_block(items, limit, key_prefix="n"):
    if not items:
        ui.empty_state("News feeds are currently unreachable. Check network access "
                       "or configure premium wires in Settings.")
        return
    for i, item in enumerate(items[:limit]):
        ui.news_card(item, news.fmt_time(item["published"]))


# ------------------------------------------------------------ pages
def page_executive_summary():
    main, rail = st.columns([3.2, 1], gap="medium")

    items = news.get_news()
    with main:
        hero_item = news.pick_hero(items)
        if hero_item:
            ui.hero(hero_item, news.fmt_time(hero_item["published"]))
        else:
            ui.empty_state("No live news available for the hero story.")

        ui.section("Global Market Summary", "Priority markets first · mini-chart = last month · yfinance")
        render_summary_strip()

        left, right = st.columns([1.5, 1], gap="medium")
        with left:
            ui.section("Breaking News", "Ranked by importance")
            _news_block(items[1:] if hero_item else items, 5)
        with right:
            ui.section("Market Shock Alerts", "Derived from observed moves")
            alerts = markets.get_shock_alerts()
            if alerts:
                for a in alerts[:4]:
                    ui.alert_card(a)
            else:
                ui.empty_state("No moves beyond alert thresholds in the latest session.")

            ui.section("Economic Calendar", "Next 7 days")
            cal = calendar_data.get_calendar()
            if cal:
                day = None
                for e in cal[:5]:
                    if e.get("day") and e["day"] != day:
                        day = e["day"]
                        ui.cal_day_header(day)
                    ui.cal_row(e)
                ui.legend("Consensus = forecast · Previous = prior · SAST")
            else:
                ui.empty_state("Calendar feed unavailable right now.")

        ui.section("Market Movers", "Requested instruments first · toggle for wider context")
        extended = st.toggle("Include extended universe (global indices, other FX)",
                             value=False, key="mv_ext")
        gainers, losers = markets.get_movers(universe="extended" if extended else "core")
        n = len({q.ticker for q in gainers + losers})
        ui.legend(("Core + extended universe" if extended else
                   "Requested instruments only") + f" · showing top/bottom from "
                  f"{len(markets.CORE_MOVERS) + (len(markets.EXTENDED_MOVERS) if extended else 0)} tracked")
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown('<div class="card"><div class="rt" style="font-size:11px;'
                        'font-weight:700;text-transform:uppercase;letter-spacing:1px;'
                        'color:#1E8052;margin-bottom:6px;">Top gainers</div>' +
                        "".join(ui.mover_row(q) for q in gainers) + "</div>",
                        unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="card"><div class="rt" style="font-size:11px;'
                        'font-weight:700;text-transform:uppercase;letter-spacing:1px;'
                        'color:#B0212C;margin-bottom:6px;">Top decliners</div>' +
                        "".join(ui.mover_row(q) for q in losers) + "</div>",
                        unsafe_allow_html=True)

    with rail:
        _right_rail(items)


def _right_rail(items):
    trend_tags: dict[str, int] = {}
    for it in items:
        for t in it.get("tags", []):
            trend_tags[t] = trend_tags.get(t, 0) + 1
    top = sorted(trend_tags.items(), key=lambda kv: kv[1], reverse=True)[:7]
    st.markdown('<div class="rail-card" style="margin-bottom:4px;">'
                '<div class="rt">Trending Topics</div></div>',
                unsafe_allow_html=True)
    if not top:
        st.markdown('<div class="rail-card"><div class="rail-item">No live tags</div></div>',
                    unsafe_allow_html=True)
    for k, v in top:
        stories = [it for it in items if k in it.get("tags", [])]
        with st.expander(f"{k.upper()} · {v} {'story' if v == 1 else 'stories'}"):
            for it in stories:
                st.markdown(
                    f'<div class="rail-item"><a href="{ui.esc(it["link"])}" '
                    f'target="_blank">{ui.esc(it["title"][:90])}</a></div>',
                    unsafe_allow_html=True)

    watch = st.session_state.setdefault("watchlist", ["USD/ZAR", "Brent Crude", "Gold"])
    strip = {q.name: q for q in markets.get_summary_strip() if q.ok}
    rows = ""
    for w in watch:
        q = strip.get(w)
        rows += (f'<div class="rail-item"><b>{ui.esc(w)}</b> — '
                 + (f'<span class="num {ui.chg_cls(q.change_pct)}">{q.change_pct:+.2f}%</span>'
                    if q else '<span style="color:#909288;">n/a</span>') + "</div>")
    st.markdown(f'<div class="rail-card"><div class="rt">Watchlist</div>{rows}</div>',
                unsafe_allow_html=True)

    saved = st.session_state.get("saved_articles", [])
    rows = ("".join(f'<div class="rail-item"><a href="{ui.esc(s["link"])}" target="_blank">'
                    f'{ui.esc(s["title"][:70])}</a></div>' for s in saved[:6])
            or '<div class="rail-item" style="color:#909288;">Bookmark articles from '
               'Market News</div>')
    st.markdown(f'<div class="rail-card"><div class="rt">Saved Articles</div>{rows}</div>',
                unsafe_allow_html=True)

    alerts = markets.get_shock_alerts()
    rows = ""
    if alerts:
        for a in alerts[:3]:
            kind = {"Critical": "red", "Warning": "amber"}.get(a["severity"], "blue")
            rows += (f'<div class="rail-item">{ui.badge(a["severity"], kind)} '
                     f'{ui.esc(a["title"])}</div>')
    else:
        rows = '<div class="rail-item">No threshold breaches this session.</div>'
    rows += (f'<div class="rail-item" style="color:#909288;">{len(items)} stories '
             f'ingested this cycle.</div>')
    st.markdown(f'<div class="rail-card"><div class="rt">Quick Insights</div>{rows}</div>',
                unsafe_allow_html=True)
    if alerts and st.button("View alert details →", key="qi_goto_alerts",
                            use_container_width=True):
        st.session_state["nav_to"] = "Market Shock Alerts"
        st.rerun()


def page_market_news():
    items = news.get_news()
    f1, f2, f3, f4 = st.columns([1, 1, 1, 1.4])
    region = f1.selectbox("Region", ["All"] + sorted({i["region"] for i in items}) if items else ["All"])
    asset = f2.selectbox("Asset class", ["All"] + sorted({i["asset"] for i in items}) if items else ["All"])
    imp = f3.selectbox("Importance", ["All", "High", "Medium", "Low"])
    q = f4.text_input("Search headlines", placeholder="e.g. SARB, oil, tariffs")

    view = items
    if region != "All":
        view = [i for i in view if i["region"] == region]
    if asset != "All":
        view = [i for i in view if i["asset"] == asset]
    if imp != "All":
        view = [i for i in view if i["importance"] == imp]
    if q:
        ql = q.lower()
        view = [i for i in view if ql in i["title"].lower() or ql in i["summary"].lower()]

    ui.section("Market News", f"{len(view)} stories · public RSS wires")
    if not view:
        ui.empty_state("No stories match the current filters, or feeds are unreachable.")
        return
    for idx, item in enumerate(view[:30]):
        c1, c2 = st.columns([12, 1])
        with c1:
            ui.news_card(item, news.fmt_time(item["published"]))
        with c2:
            if st.button("🔖", key=f"bm_{idx}", help="Save to watch rail"):
                saved = st.session_state.setdefault("saved_articles", [])
                if item["title"] not in [s["title"] for s in saved]:
                    saved.insert(0, {"title": item["title"], "link": item["link"]})
                st.toast("Saved.")


def page_shock_alerts():
    ui.section("Market Shock Alerts",
               "Rule-based on observed session moves — display only, no forecasting")
    alerts = markets.get_shock_alerts()
    if not alerts:
        ui.empty_state("No instrument in the tracked universe moved beyond warning or "
                       "critical thresholds in the latest session.")
    dismissed = st.session_state.setdefault("dismissed_alerts", set())
    shown = 0
    for i, a in enumerate(alerts):
        if a["title"] in dismissed:
            continue
        c1, c2 = st.columns([12, 1])
        with c1:
            ui.alert_card(a)
        with c2:
            if st.button("✕", key=f"dis_{i}", help="Dismiss"):
                dismissed.add(a["title"])
                st.rerun()
        shown += 1
    if alerts and shown == 0:
        ui.empty_state("All active alerts dismissed for this session.")
    st.caption("Thresholds — indices 2%/3.5% · FX 1.5%/3% · commodities 3%/6% · "
               "crypto 5%/10% (warning/critical).")


def page_announcements():
    ui.section("Company Announcements",
               "Dividends · leadership · earnings · M&A · capital raises · buybacks · guidance")
    ann = news.get_announcements()
    if not ann:
        ui.empty_state("Announcement feeds unreachable. A SENS/Bloomberg corporate "
                       "actions wire can replace this source in future.")
        return
    cats = sorted({a["category"] for a in ann})
    pick = st.pills("Category", ["All"] + cats, default="All", key="ann_cat",
                    label_visibility="collapsed") or "All"
    view = ann if pick == "All" else [a for a in ann if a["category"] == pick]
    view = sorted(view, key=lambda a: a["published"] or
                  datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    def row(a):
        st.markdown(
            f'''<div class="ann-row">{ui.badge(a["category"], "blue")}
            <span class="a-t"><a href="{ui.esc(a["link"])}" target="_blank"
            title="{ui.esc(a["title"])}">{ui.esc(a["title"])}</a></span>
            <span class="a-m">{ui.esc(a.get("source") or "Wire")} ·
            {ui.esc(news.fmt_time(a["published"]))}</span></div>''',
            unsafe_allow_html=True)

    for a in view[:10]:
        row(a)
    if len(view) > 10:
        with st.expander(f"Show {len(view) - 10} more"):
            for a in view[10:40]:
                row(a)


def page_calendar():
    ui.section("Economic Calendar", "Week view · scheduled data releases and events")
    ui.legend("Orange edge = high impact · Gold = medium · Consensus vs Previous "
              "shown per event · times in SAST")
    horizon = st.pills("Horizon", ["Next 7 days", "Next 14 days"],
                       default="Next 7 days", key="cal_h") or "Next 7 days"
    days_ahead = 7 if horizon.startswith("Next 7") else 14
    cal = calendar_data.get_calendar(days_ahead=days_ahead)
    if not cal:
        ui.empty_state("No calendar data returned by the provider.")
        return

    sast = ZoneInfo("Africa/Johannesburg")
    today = datetime.now(sast).date()
    by_day: dict = {}
    for e in cal:
        try:
            dt = datetime.fromisoformat(e["_dt"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            by_day.setdefault(dt.astimezone(sast).date(), []).append(e)
        except Exception:
            continue

    for week_start in range(0, days_ahead, 7):
        days = [today + timedelta(days=week_start + i) for i in range(7)]
        cols = st.columns(7, gap="small")
        for col, d in zip(cols, days):
            events = by_day.get(d, [])
            today_cls = " cal-col-today" if d == today else ""
            chips = ""
            for e in events[:6]:
                sev = ("ev-high" if e["importance"] == "High"
                       else "ev-medium" if e["importance"] == "Medium" else "")
                exp = e["expected"]
                cons = (f' · Cons {ui.esc(exp)}' if exp not in ("—", "", None) else "")
                chips += (f'<div class="cal-ev {sev}" title="{ui.esc(e["event"])} — '
                          f'Consensus {ui.esc(e["expected"])}, Previous '
                          f'{ui.esc(e["previous"])}">'
                          f'<div class="e-t">{ui.esc((e.get("time") or "")[:5])}</div>'
                          f'<div class="e-n">{ui.esc(e["event"][:44])}</div>'
                          f'<div class="e-c">{ui.esc(e["country"])}{cons}</div></div>')
            more = (f'<div class="e-c" style="text-align:center;">+{len(events)-6} '
                    f'more</div>' if len(events) > 6 else "")
            col.markdown(
                f'<div class="cal-col{today_cls}"><div class="cal-col-h">'
                f'{d.strftime("%a")}<span class="d">{d.day}</span></div>'
                f'{chips or chr(10)}{more}</div>',
                unsafe_allow_html=True)
        st.markdown(" ")
    st.caption("Consensus = the market\'s forecast before release; Previous = the "
               "prior period\'s reading; hover an event for both. Importance is the "
               "provider\'s market-impact rating. No in-app estimation.")
