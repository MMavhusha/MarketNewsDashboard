"""Core pages: Executive Summary, Market News, Shock Alerts,
Company Announcements, Economic Calendar."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from components import charts, ui
from data_sources import calendar_data, markets, news


# ------------------------------------------------------------ shared bits
def render_summary_strip():
    quotes = markets.get_summary_strip()
    r1, r2 = st.columns([2, 1])
    with r1:
        mode = st.pills("View", ["Priority markets", "All markets"],
                        default="Priority markets", key="sum_mode",
                        label_visibility="collapsed") or "Priority markets"
    with r2:
        period = st.pills("Chart period", ["1M", "1D (today)"], default="1M",
                          key="sum_period",
                          label_visibility="collapsed") or "1M"
    intraday_mode = period.startswith("1D")
    if mode == "Priority markets":
        show = [q for q in quotes if q.name in markets.SUMMARY_PRIMARY]
        show.sort(key=lambda q: markets.SUMMARY_PRIMARY.index(q.name))
        ncols = 2
    else:
        show = quotes
        ncols = 3
    intraday = (markets.get_intraday([(q.name, q.ticker) for q in show])
                if intraday_mode else {})
    per = (len(show) + ncols - 1) // ncols
    cols = st.columns(ncols, gap="medium")
    for i, col in enumerate(cols):
        chunk = show[i * per:(i + 1) * per]
        with col, st.container(border=True):
            for q in chunk:
                fig, tag = None, ""
                if q.ok and intraday_mode:
                    today = intraday.get(q.ticker)
                    prev = (q.price - q.change) if q.change is not None else None
                    if today and prev:
                        fig = charts.intraday_spark(today, prev, height=34)
                        tag = "1D"
                    else:
                        tag = "no intraday feed"
                elif q.ok and len(q.spark) > 2:
                    fig = charts.sparkline(q.spark, height=34, fill=False)
                    tag = "1M"
                ui.summary_row(q, fig, key=f"spark_{mode[:3]}_{period[:2]}_{q.ticker}",
                               period=tag)
    if intraday_mode:
        ui.legend("1D: solid line = today's session · dotted = prior close · "
                  "closed markets show no intraday feed")


def _story_row(item, show_importance=False):
    imp = ui.importance_badge(item["importance"]) if show_importance else ""
    st.markdown(
        f'''<div class="ann-row">{ui.sentiment_badge(item["sentiment"])}{imp}
        <span class="a-t"><a href="{ui.esc(item["link"])}" target="_blank"
        title="{ui.esc(item["title"])}">{ui.esc(item["title"])}</a></span>
        <span class="a-m">{ui.esc(item["source"])} ·
        {ui.esc(news.fmt_time(item["published"]))}</span></div>''',
        unsafe_allow_html=True)


# ------------------------------------------------------------ exec summary
def page_executive_summary():
    main, rail = st.columns([3.2, 1], gap="medium")

    items = news.get_news()
    with main:
        hero_item = news.pick_hero(items)
        if hero_item:
            ui.hero(hero_item, news.fmt_time(hero_item["published"]))
        else:
            ui.empty_state("No live news available for the hero story.")

        ui.section("Global Market Summary",
                   "Latest vs prior session · mini-chart = last month · yfinance")
        render_summary_strip()

        left, right = st.columns([1.5, 1], gap="medium")
        with left:
            ui.section("Breaking News", "Ranked by importance")
            if items:
                for item in (items[1:6] if hero_item else items[:5]):
                    ui.news_card(item, news.fmt_time(item["published"]))
            else:
                ui.empty_state("News feeds are currently unreachable.")
        with right:
            ui.section("Market Shock Alerts", "Derived from observed moves")
            alerts = markets.get_shock_alerts()
            if alerts:
                for a in alerts[:4]:
                    ui.alert_card(a)
            else:
                ui.empty_state("No moves beyond alert thresholds in the latest "
                               "session.")

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

        ui.section("Market Movers", "Requested instruments first")
        extended = st.toggle("Include extended universe (global indices, other FX)",
                             value=False, key="mv_ext")
        gainers, losers = markets.get_movers(universe="extended" if extended else "core")
        ui.legend(("Core + extended universe" if extended else
                   "Requested instruments only") + f" · top/bottom from "
                  f"{len(markets.CORE_MOVERS) + (len(markets.EXTENDED_MOVERS) if extended else 0)} tracked")
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown('<div class="card"><div style="font-size:11px;font-weight:700;'
                        'text-transform:uppercase;letter-spacing:1px;color:#1E8052;'
                        'margin-bottom:6px;">Top gainers</div>' +
                        "".join(ui.mover_row(q) for q in gainers) + "</div>",
                        unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="card"><div style="font-size:11px;font-weight:700;'
                        'text-transform:uppercase;letter-spacing:1px;color:#B0212C;'
                        'margin-bottom:6px;">Top decliners</div>' +
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
    if top:
        with st.container(key="trend_wrap"):
            labels = {f"{k.title()} · {v}": k for k, v in top}
            pick = st.pills("Topics", list(labels.keys()), default=None,
                            key="trend_pick", label_visibility="collapsed")
            if pick:
                tag = labels[pick]
                stories = [it for it in items if tag in it.get("tags", [])]
                rows = "".join(
                    f'<div class="rail-item"><a href="{ui.esc(it["link"])}" '
                    f'target="_blank">{ui.esc(it["title"][:90])}</a></div>'
                    for it in stories)
                st.markdown(f'<div class="rail-card">{rows}</div>',
                            unsafe_allow_html=True)
    else:
        st.markdown('<div class="rail-card"><div class="rail-item">No live '
                    'tags</div></div>', unsafe_allow_html=True)

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
            or '<div class="rail-item" style="color:#909288;">Save stories with the '
               '🔖 button on the Market News page. Saved items last for your '
               'browser session.</div>')
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


# ------------------------------------------------------------ market news
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

    ui.legend(f"{len(view)} stories · ranked by importance · public RSS wires")
    if not view:
        ui.empty_state("No stories match the current filters, or feeds are unreachable.")
        return
    for idx, item in enumerate(view[:30]):
        c1, c2 = st.columns([12, 1])
        with c1:
            ui.news_card(item, news.fmt_time(item["published"]))
        with c2:
            if st.button("🔖", key=f"bm_{idx}",
                         help="Save this article — it will appear under Saved "
                              "Articles on the Executive Summary (this session)"):
                saved = st.session_state.setdefault("saved_articles", [])
                if item["title"] not in [s["title"] for s in saved]:
                    saved.insert(0, {"title": item["title"], "link": item["link"]})
                st.toast("Saved — see Saved Articles on the Executive Summary.")


# ------------------------------------------------------------ shock alerts
_ALERT_ASSET = {"index": "Equities", "fx": "FX", "commodity": "Commodities",
                "crypto": "Crypto"}


def _wire_sentiment(asset_class: str) -> str:
    counts = {"Positive": 0, "Negative": 0, "Neutral": 0}
    for it in news.get_news():
        if it["asset"] == asset_class:
            counts[it["sentiment"]] += 1
    total = sum(counts.values())
    if not total:
        return ""
    return (f'Wire sentiment for {asset_class} stories: '
            f'{counts["Negative"]} negative · {counts["Positive"]} positive · '
            f'{counts["Neutral"]} neutral (observed coverage, not a forecast)')


def page_shock_alerts():
    t = markets.get_thresholds()
    kinds = {tk: k for _, tk, k, _ in markets.SUMMARY_STRIP}
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
            kind = next((k for n, tk, k, _ in markets.SUMMARY_STRIP
                         if n == a["assets"]), "index")
            senti = _wire_sentiment(_ALERT_ASSET.get(kind, "Equities"))
            if senti:
                ui.legend(senti)
        with c2:
            if st.button("✕", key=f"dis_{i}", help="Dismiss"):
                dismissed.add(a["title"])
                st.rerun()
        shown += 1
    if alerts and shown == 0:
        ui.empty_state("All active alerts dismissed for this session.")
    st.caption(f"Active thresholds (warning/critical) — indices "
               f"{t['index'][0]}%/{t['index'][1]}% · FX {t['fx'][0]}%/{t['fx'][1]}% · "
               f"commodities {t['commodity'][0]}%/{t['commodity'][1]}% · "
               f"crypto {t['crypto'][0]}%/{t['crypto'][1]}%. "
               "Your team can adjust these under Settings → Alert thresholds.")


# ------------------------------------------------------------ announcements

_CAT_COLORS = {"Dividends": "#2A8B7C", "Leadership": "#7E6CA5",
               "Earnings": "#1F3864", "M&A": "#FF671D",
               "Capital raises": "#1B7B9C", "Buybacks": "#1E8052",
               "Guidance": "#B0212C"}

def page_announcements():
    ann = news.get_announcements()
    if not ann:
        ui.empty_state("Announcement feeds unreachable. A SENS/Bloomberg corporate "
                       "actions wire can replace this source in future.")
        return
    cats = sorted({a["category"] for a in ann})
    cc1, cc2 = st.columns([2.4, 1])
    with cc1:
        pick = st.pills("Category", ["All"] + cats, default="All", key="ann_cat",
                        label_visibility="collapsed") or "All"
    company = cc2.text_input("Company", key="ann_co",
                             placeholder="Search company or keyword",
                             label_visibility="collapsed")
    view = ann if pick == "All" else [a for a in ann if a["category"] == pick]
    if company:
        cl = company.lower()
        view = [a for a in view if cl in a["title"].lower()
                or cl in (a.get("source") or "").lower()]
    now = datetime.now(timezone.utc)
    view = sorted(view, key=lambda a: a["published"] or now - timedelta(days=30),
                  reverse=True)
    today = [a for a in view if a["published"] and (now - a["published"]).days < 1]
    earlier = [a for a in view if a not in today]

    def row(a):
        rail = _CAT_COLORS.get(a["category"], "#C9CBC4")
        st.markdown(
            f'''<div class="ann-row" style="border-left:4px solid {rail};">{ui.badge(a["category"], "blue")}
            <span class="a-t"><a href="{ui.esc(a["link"])}" target="_blank"
            title="{ui.esc(a["title"])}">{ui.esc(a["title"])}</a></span>
            <span class="a-m">{ui.esc(a.get("source") or "Wire")} ·
            {ui.esc(news.fmt_time(a["published"]))}</span></div>''',
            unsafe_allow_html=True)

    from itertools import groupby
    sast = ZoneInfo("Africa/Johannesburg")

    def day_of(a):
        return a["published"].astimezone(sast).date() if a["published"] else None

    dated = [a for a in view if a["published"]]
    undated = [a for a in view if not a["published"]]
    groups = [(d, list(g)) for d, g in groupby(dated, key=day_of)]
    visible, archived = groups[:3], groups[3:]
    for d, items_g in visible:
        ui.cal_day_header(d.strftime("%A %d %B") +
                          (" · today" if d == datetime.now(sast).date() else ""))
        for a in items_g[:15]:
            row(a)
    if archived:
        lo = archived[-1][0].strftime("%d %b")
        hi = archived[0][0].strftime("%d %b")
        n = sum(len(g) for _, g in archived)
        with st.expander(f"{lo} – {hi} · {n} announcements"):
            for d, items_g in archived:
                ui.cal_day_header(d.strftime("%A %d %B"))
                for a in items_g[:15]:
                    row(a)
    if undated:
        with st.expander(f"Undated wire items · {len(undated)}"):
            for a in undated[:15]:
                row(a)


# ------------------------------------------------------------ calendar
def page_calendar():
    """Agenda view — the standard pattern across ForexFactory, Investing.com
    and Bloomberg WECO: chronological rows grouped by day, filterable by
    impact and country."""
    horizon = st.pills("Horizon", ["Next 7 days", "Next 14 days"],
                       default="Next 7 days", key="cal_h") or "Next 7 days"
    days_ahead = 7 if horizon.startswith("Next 7") else 14
    cal = calendar_data.get_calendar(days_ahead=days_ahead)
    if not cal:
        ui.empty_state("No calendar data returned by the provider.")
        return

    f1, f2 = st.columns([1, 2])
    imp_pick = f1.pills("Impact", ["All", "High", "Medium"], default="All",
                        key="cal_imp") or "All"
    countries = sorted({e["country"] for e in cal})
    ctry_pick = f2.multiselect("Countries", countries, default=[],
                               placeholder="All countries")
    view = cal
    if imp_pick == "High":
        view = [e for e in view if e["importance"] == "High"]
    elif imp_pick == "Medium":
        view = [e for e in view if e["importance"] in ("High", "Medium")]
    if ctry_pick:
        view = [e for e in view if e["country"] in ctry_pick]
    ui.legend(f"{len(view)} events · rows ordered by time within each day · "
              "times in SAST · Consensus = market forecast before release, "
              "Previous = prior reading")

    if not view:
        ui.empty_state("No events match the current filters.")
        return
    day = None
    sast = ZoneInfo("Africa/Johannesburg")
    today_hdr = None
    for e in view:
        try:
            dt = datetime.fromisoformat(e["_dt"].replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            d = dt.astimezone(sast).date()
            hdr = d.strftime("%A %d %B") + (
                " · today" if d == datetime.now(sast).date() else "")
        except Exception:
            hdr = e.get("day") or "Scheduled"
        if hdr != day:
            day = hdr
            ui.cal_day_header(hdr)
        ui.tl_row(e)
    st.caption("Importance is the provider's market-impact rating. No in-app "
               "estimation is performed.")
