"""Core pages: Executive Summary, Market News, Shock Alerts,
Company Announcements, Economic Calendar."""
from __future__ import annotations

import streamlit as st

from components import charts, ui
from data_sources import calendar_data, markets, news


# ------------------------------------------------------------ shared bits
def render_summary_strip():
    quotes = markets.get_summary_strip()
    cols = st.columns(len(quotes))
    for col, q in zip(cols, quotes):
        with col:
            st.markdown(ui.market_card_html(q), unsafe_allow_html=True)
            if q.ok and len(q.spark) > 2:
                st.plotly_chart(charts.sparkline(q.spark), use_container_width=True,
                                config={"displayModeBar": False},
                                key=f"spark_{q.ticker}")


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

        ui.section("Global Market Summary", "Latest close vs prior session · yfinance")
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
                for e in cal[:5]:
                    ui.cal_row(e)
            else:
                ui.empty_state("Calendar requires a Trading Economics key (Settings).")

        ui.section("Market Movers", "Best and worst across the tracked universe")
        gainers, losers = markets.get_movers()
        c1, c2 = st.columns(2, gap="medium")
        with c1:
            st.markdown('<div class="card"><div class="rt" style="font-size:11px;'
                        'font-weight:700;text-transform:uppercase;letter-spacing:1px;'
                        'color:#027A48;margin-bottom:6px;">Top gainers</div>' +
                        "".join(ui.mover_row(q) for q in gainers) + "</div>",
                        unsafe_allow_html=True)
        with c2:
            st.markdown('<div class="card"><div class="rt" style="font-size:11px;'
                        'font-weight:700;text-transform:uppercase;letter-spacing:1px;'
                        'color:#B42318;margin-bottom:6px;">Top decliners</div>' +
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
    st.markdown(
        '<div class="rail-card"><div class="rt">Trending Topics</div>' +
        ("".join(f'<div class="rail-item">{ui.badge(k, "blue")} '
                 f'<span style="color:#98A2B3;">{v} stories</span></div>' for k, v in top)
         or '<div class="rail-item">No live tags</div>') + "</div>",
        unsafe_allow_html=True,
    )

    watch = st.session_state.setdefault("watchlist", ["USD/ZAR", "Brent Crude", "Gold"])
    strip = {q.name: q for q in markets.get_summary_strip() if q.ok}
    rows = ""
    for w in watch:
        q = strip.get(w)
        rows += (f'<div class="rail-item"><b>{ui.esc(w)}</b> — '
                 + (f'<span class="num {ui.chg_cls(q.change_pct)}">{q.change_pct:+.2f}%</span>'
                    if q else '<span style="color:#98A2B3;">n/a</span>') + "</div>")
    st.markdown(f'<div class="rail-card"><div class="rt">Watchlist</div>{rows}</div>',
                unsafe_allow_html=True)

    saved = st.session_state.get("saved_articles", [])
    rows = ("".join(f'<div class="rail-item"><a href="{ui.esc(s["link"])}" target="_blank">'
                    f'{ui.esc(s["title"][:70])}</a></div>' for s in saved[:6])
            or '<div class="rail-item" style="color:#98A2B3;">Bookmark articles from '
               'Market News</div>')
    st.markdown(f'<div class="rail-card"><div class="rt">Saved Articles</div>{rows}</div>',
                unsafe_allow_html=True)

    alerts = markets.get_shock_alerts()
    crit = [a for a in alerts if a["severity"] == "Critical"]
    qi = (f'{len(alerts)} active alert(s), {len(crit)} critical. '
          if alerts else "No threshold breaches. ")
    qi += f'{len(items)} stories ingested this cycle.'
    st.markdown(f'<div class="rail-card"><div class="rt">Quick Insights</div>'
                f'<div class="rail-item">{ui.esc(qi)}</div></div>',
                unsafe_allow_html=True)


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
    cats = ["All"] + sorted({a["category"] for a in ann})
    pick = st.selectbox("Category", cats)
    view = ann if pick == "All" else [a for a in ann if a["category"] == pick]
    for a in view[:30]:
        st.markdown(
            f'''<div class="news-card">
            <div class="hl"><a href="{ui.esc(a["link"])}" target="_blank">{ui.esc(a["title"])}</a></div>
            <div class="mt">{ui.badge(a["category"], "blue")}
            <b>{ui.esc(a.get("source") or "Wire")}</b> · {ui.esc(news.fmt_time(a["published"]))}</div>
            </div>''',
            unsafe_allow_html=True,
        )


def page_calendar():
    ui.section("Economic Calendar", "Central banks · inflation · GDP · employment · PMI · rates")
    st.caption(f"Provider: {calendar_data.provider_label()}")
    if not calendar_data.has_full_access():
        st.info("Free Forex Factory feed covers major currencies only. Add "
                "TE_API_KEY in Streamlit Secrets to include South Africa and "
                "India releases.", icon="🔑")
    days = st.slider("Days ahead", 1, 14, 7)
    cal = calendar_data.get_calendar(days_ahead=days)
    if not cal:
        ui.empty_state("No calendar data returned by the provider.")
        return
    for e in cal[:60]:
        ui.cal_row(e)
    st.caption("Source: Trading Economics API. Expected/previous values as published "
               "by the provider — no in-app estimation.")
