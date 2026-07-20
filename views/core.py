"""Core pages: Executive Summary, Market News, Shock Alerts,
Company Announcements, Economic Calendar."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from components import charts, ui
from data_sources import app_state, calendar_data, markets, news


# ------------------------------------------------------------ shared bits
@st.fragment(run_every=120)
def render_summary_strip():
    """Auto-refreshes itself every 2 minutes (fragment rerun): the shared
    server-side cache (TTL 120s) means all users together cost roughly one
    Yahoo batch request per cycle — safe for an unofficial rate-limited
    source."""
    quotes = markets.get_summary_strip()
    r1, r2 = st.columns([2, 1])
    with r1:
        mode = st.pills("View", ["Priority markets", "All markets"],
                        default="Priority markets", key="sum_mode",
                        label_visibility="collapsed") or "Priority markets"
    with r2:
        period = st.pills("Chart period", ["1M", "1D"], default="1M",
                          key="sum_period",
                          label_visibility="collapsed") or "1M"
    intraday_mode = period == "1D"
    if mode == "Priority markets":
        show = [q for q in quotes if q.name in markets.SUMMARY_PRIMARY]
        show.sort(key=lambda q: markets.SUMMARY_PRIMARY.index(q.name))
        ncols = 2
    else:
        show = quotes
        ncols = 3
    intraday = (markets.get_intraday([(q.name, q.ticker) for q in show])
                if intraday_mode else {})
    missing: list[str] = []
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
                    elif len(q.spark) > 2:  # closed market / brief feed gap
                        fig = charts.sparkline(q.spark, height=34, fill=False)
                        tag = "1M"
                        missing.append(q.name)
                elif q.ok and len(q.spark) > 2:
                    fig = charts.sparkline(q.spark, height=34, fill=False)
                    tag = "1M"
                ui.summary_row(q, fig, key=f"spark_{mode[:3]}_{period[:2]}_{q.ticker}",
                               period=tag)
    tail = (f"Auto-refreshes every 2 minutes · updated {markets.last_refresh()} · "
            "source prices may be delayed up to ~15 min by the exchange")
    if intraday_mode:
        extra = (f" · no intraday session right now for "
                 f"{', '.join(missing[:4])}{'…' if len(missing) > 4 else ''} "
                 "(closed market or feed gap — 1M shown, retries automatically)"
                 if missing else "")
        ui.legend("1D: solid line = today's session · dotted = prior close"
                  + extra + " · " + tail)
    else:
        ui.legend(tail)


# ------------------------------------------------------------ exec summary
def page_executive_summary():
    main, rail = st.columns([3.2, 1], gap="medium")

    items = news.get_news()
    with main:
        hero_item = news.pick_hero(items)
        if hero_item:
            ui.hero(hero_item, news.fmt_time(hero_item["published"]))
            if st.session_state.get("_admin_ok"):
                ui.legend("Admin · hero rationale: "
                          + ("model-generated ✦" if hero_item.get("why")
                             else "rules-derived template"))
        else:
            ui.empty_state("No live news available for the hero story.")

        ui.section("Global Market Summary",
                   "Latest vs prior session · mini-chart = last month · yfinance")
        render_summary_strip()

        left, right = st.columns([1.5, 1], gap="medium")
        with left:
            ui.section("Breaking News", "Ranked by importance")
            if items:
                pool = [i for i in items if i is not hero_item]
                for item in pool[:5]:
                    ui.news_card(item, news.fmt_time(item["published"]))
            else:
                ui.empty_state("News feeds are currently unreachable.")
        with right:
            ui.section("Market Shock Alerts", "Derived from observed moves")
            alerts = markets.get_shock_alerts()
            if alerts:
                for a in alerts[:4]:
                    ui.alert_card(a)
                if st.button("View alert details →", key="qi_goto_alerts",
                             use_container_width=True):
                    st.session_state["nav_to"] = "Calendar & Alerts"
                    st.rerun()
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
                    ui.cal_mini(e)
                ui.legend("Cons = market forecast · Prev = prior · SAST")
            else:
                ui.empty_state("Calendar feed unavailable right now.")

        ui.section("Market Movers", "Requested instruments first")
        extended = st.toggle("Include extended universe (global indices, other FX)",
                             value=False, key="mv_ext")
        gainers, losers = markets.get_movers(universe="extended" if extended else "core")
        ui.legend(f"Top/bottom of "
                  f"{len(markets.CORE_MOVERS) + (len(markets.EXTENDED_MOVERS) if extended else 0)} tracked instruments")
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
    quotes = markets.get_watch_quotes(watch)
    rows = ""
    for w in watch:
        q = quotes.get(w)
        rows += (f'<div class="rail-item"><b>{ui.esc(w)}</b> — '
                 + (f'<span class="num {ui.chg_cls(q.change_pct)}">{q.change_pct:+.2f}%</span>'
                    if q and q.ok and q.change_pct is not None
                    else '<span style="color:#909288;">n/a</span>') + "</div>")
    st.markdown(f'<div class="rail-card"><div class="rt">Watchlist</div>'
                f'{rows or chr(38)}</div>', unsafe_allow_html=True)
    with st.popover("Edit watchlist", use_container_width=True):
        picked = st.multiselect("Instruments", markets.watchable_names(),
                                default=[w for w in watch
                                         if w in markets.watchable_names()],
                                key="watch_edit",
                                help="Tracked across indices, the spec "
                                     "commodities and FX majors. Session-scoped "
                                     "until sign-in and shared storage exist.")
        if picked != watch:
            st.session_state["watchlist"] = picked
            app_state.persist("update watchlist")
            st.rerun()

    saved = st.session_state.get("saved_articles", [])
    rows = ("".join(f'<div class="rail-item"><a href="{ui.esc(s["link"])}" target="_blank">'
                    f'{ui.esc(s["title"][:70])}</a></div>' for s in saved[:6])
            or '<div class="rail-item" style="color:#909288;">Save stories with the '
               '🔖 button on the Market News page. Saved items last for your '
               'browser session.</div>')
    st.markdown(f'<div class="rail-card"><div class="rt">Saved Articles'
                f'{" (team)" if app_state.enabled() else ""}</div>{rows}</div>',
                unsafe_allow_html=True)
    if saved:
        with st.popover("Manage saved", use_container_width=True):
            for si, art in enumerate(list(saved[:12])):
                r1, r2 = st.columns([8, 1])
                r1.markdown(f'<div class="rail-item">{ui.esc(art["title"][:80])}</div>',
                            unsafe_allow_html=True)
                if r2.button("✕", key=f"rmsv_{si}", help="Remove"):
                    saved[:] = [x for x in saved if x["title"] != art["title"]]
                    app_state.persist("remove saved article")
                    st.rerun()

    ui.legend(f"{len(items)} stories ingested this cycle")


# ------------------------------------------------------------ market news
def _weekly_view():
    from views import reports
    reports.render_weekly_view()


def page_market_news():
    mode = st.pills("View", ["All news", "This week"], default="All news",
                    key="news_mode") or "All news"
    if mode == "This week":
        _weekly_view()
        return

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
    kw = st.session_state.get("news_watch_keywords", [])
    admin = st.session_state.get("_admin_ok")
    if admin:
        n_ai = sum(1 for it in view if it.get("_ai"))
        try:
            from data_sources import ai_enrich
            prov = ai_enrich.provider_label()
        except Exception:
            prov = "off"
        ui.legend(f"Admin · model-primary classification via {prov} · "
                  f"{n_ai} of {len(view)} visible stories were model-"
                  f"classified (marked ✦); the rest fell back to rules")
    for idx, item in enumerate(view[:30]):
        if kw and any(news.fuzzy_match(k, item["title"] + " " + item["summary"])
                      for k in kw):
            item = {**item, "title": "⚑ " + item["title"]}
        if admin and item.get("_ai"):
            item = {**item, "title": item["title"] + " ✦"}
        c1, c2 = st.columns([12, 1])
        with c1:
            ui.news_card(item, news.fmt_time(item["published"]))
        with c2:
            saved = st.session_state.setdefault("saved_articles", [])
            is_saved = item["title"] in [x["title"] for x in saved]
            if st.button("✓" if is_saved else "🔖", key=f"bm_{idx}",
                         help=("Remove from Saved Articles" if is_saved else
                               "Save — appears under Saved Articles on the "
                               "Executive Summary")):
                if is_saved:
                    saved[:] = [x for x in saved if x["title"] != item["title"]]
                    app_state.persist("unsave article")
                else:
                    saved.insert(0, {"title": item["title"], "link": item["link"]})
                    app_state.persist("save article")
                st.rerun()


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


# ------------------------------------------------------------ announcements

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
        view = [a for a in view
                if news.fuzzy_match(company,
                                    a["title"] + " " + (a.get("source") or ""))]
    now = datetime.now(timezone.utc)
    view = sorted(view, key=lambda a: a["published"] or now - timedelta(days=30),
                  reverse=True)

    def row(a):
        st.markdown(
            f'''<div class="ann-row">{ui.badge(a["category"], "blue")}
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
    """Calendar & Alerts — one 'what needs my attention' surface: reactive
    threshold breaches first (observed moves), then the scheduled agenda.
    Merges the former standalone Shock Alerts page."""
    alerts = markets.get_shock_alerts()
    t = markets.get_thresholds()
    ui.section("Market shock alerts", "Threshold breaches on observed session moves")
    if not alerts:
        ui.empty_state("No instrument in the tracked universe moved beyond "
                       "warning or critical thresholds in the latest session.")
    else:
        dismissed = st.session_state.setdefault("dismissed_alerts", set())
        shown = 0
        senti_shown: set[str] = set()
        for i, a in enumerate(alerts):
            if a["title"] in dismissed:
                continue
            c1, c2 = st.columns([12, 1])
            with c1:
                ui.alert_card(a)
                kind = next((k for n, tk, k, _ in markets.SUMMARY_STRIP
                             if n == a["assets"]), "index")
                cls = _ALERT_ASSET.get(kind, "Equities")
                if cls not in senti_shown:
                    senti = _wire_sentiment(cls)
                    if senti:
                        ui.legend(senti)
                        senti_shown.add(cls)
            with c2:
                if st.button("✕", key=f"dis_{i}", help="Dismiss"):
                    dismissed.add(a["title"])
                    st.rerun()
            shown += 1
        if shown == 0:
            ui.empty_state("All active alerts dismissed for this session.")
    st.caption(f"Active thresholds (warning/critical) — indices "
               f"{t['index'][0]}%/{t['index'][1]}% · FX {t['fx'][0]}%/{t['fx'][1]}% · "
               f"commodities {t['commodity'][0]}%/{t['commodity'][1]}% · "
               f"crypto {t['crypto'][0]}%/{t['crypto'][1]}%. Adjust under "
               "Settings → Alert thresholds.")

    ui.section("Economic calendar",
               "Scheduled releases and events · agenda view")
    horizon = st.pills("Horizon", ["Next 7 days", "Next 14 days"],
                       default="Next 7 days", key="cal_h") or "Next 7 days"
    days_ahead = 7 if horizon.startswith("Next 7") else 14
    cal = calendar_data.get_calendar(days_ahead=days_ahead)
    if not cal:
        ui.empty_state("No calendar data returned by the provider.")
        return
    dates = sorted(e["date"][:10] for e in cal if e.get("date"))
    span = (f"{dates[0][8:]}/{dates[0][5:7]} – {dates[-1][8:]}/{dates[-1][5:7]}"
            if dates else "")
    note = (" · the free feed publishes this week and next week only, so late "
            "in the week the 14-day view adds few days" if days_ahead == 14 else "")
    ui.legend(f"Window {span}{note}")

    regions_present = sorted({e["country"] for e in cal})
    f1, f2, f3 = st.columns([1, 1.1, 1.5])
    imp_pick = f1.pills("Impact", ["All", "High", "Medium"], default="All",
                        key="cal_imp") or "All"
    region_pick = f2.selectbox("Region", ["All regions"] + regions_present,
                               key="cal_region")
    q = f3.text_input("Search events",
                      placeholder='e.g. "rate", "CPI", "bank holiday"',
                      key="cal_q")
    highlight_only = st.toggle(
        "Show only market-moving items (High impact + closures)",
        key="cal_hi_only")

    view = cal
    if imp_pick == "High":
        view = [e for e in view if e["importance"] == "High"]
    elif imp_pick == "Medium":
        view = [e for e in view if e["importance"] in ("High", "Medium")]
    if region_pick != "All regions":  # compress to a single region
        view = [e for e in view if e["country"] == region_pick]
    if highlight_only:
        view = [e for e in view
                if e["importance"] == "High" or e.get("is_holiday")]
    if q:
        ql = q.lower()
        view = [e for e in view
                if ql in e["event"].lower() or ql in e["country"].lower()]
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
