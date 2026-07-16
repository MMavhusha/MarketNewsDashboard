"""Weekly Key Events, Reports (weekly/monthly with real download), Settings."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from components import report_builder, ui
from data_sources import calendar_data, macro, markets, news

NAMED_SOURCES = [
    ("Bloomberg", "News, markets, corporate actions", "Public RSS wires / yfinance"),
    ("Reuters", "News wires", "Reuters via public RSS"),
    ("International Monetary Fund", "Macro comparisons, WEO", "World Bank Open Data (aligned series)"),
    ("Individual country central banks", "Policy rates, releases", "SARB Web API live (SA); others pending"),
    ("J.P. Morgan", "Research, FX forecasts", "Not available free — commentary derived from observed moves only"),
    ("RiscFlash", "Commodities & currencies", "yfinance (drop-in replacement ready)"),
    ("Trading Economics", "Calendar, indicators", "Forex Factory public feed; TE key upgrades coverage"),
]


def page_weekly_key_events():
    st.caption("Auto-compiled from live sources: the week's most important stories, "
               "upcoming releases and largest observed moves. Replaces the former "
               "Key Inflection section.")

    all_items = news.get_news()
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    recent = [i for i in all_items if (i["published"] or week_ago) >= week_ago]
    weekly = [i for i in recent if i["importance"] == "High"]
    backfilled = False
    if len(weekly) < 5:  # quiet week: backfill with medium-importance stories
        weekly = weekly + [i for i in recent if i["importance"] == "Medium"][:5 - len(weekly)]
        backfilled = True

    def stories(block):
        for item in block:
            st.markdown(
                f'''<div class="ann-row">{ui.importance_badge(item["importance"])}
                {ui.sentiment_badge(item["sentiment"])}
                <span class="a-t"><a href="{ui.esc(item["link"])}" target="_blank"
                title="{ui.esc(item["title"])}">{ui.esc(item["title"])}</a></span>
                <span class="a-m">{ui.esc(item["source"])} ·
                {ui.esc(news.fmt_time(item["published"]))}</span></div>''',
                unsafe_allow_html=True)

    many = len(weekly) >= 6
    if many:
        c1, c2 = st.columns([1.6, 1], gap="medium")
        with c1:
            ui.section("Key macro & market stories",
                       "Past 7 days" + (" · incl. medium importance" if backfilled else ""))
            stories(weekly[:10])
        side = c2
    else:
        ui.section("Key macro & market stories",
                   "Past 7 days" + (" · incl. medium importance" if backfilled else ""))
        if weekly:
            stories(weekly)
        else:
            ui.empty_state("No qualifying stories captured this week (or feeds "
                           "unreachable).")
        side = st.container()

    with side:
        if many:
            _moves_and_releases(stacked=True)
        else:
            c1, c2 = st.columns(2, gap="medium")
            with c1:
                _moves_block()
            with c2:
                _releases_block()

    ui.section("Editorial notes", "Commentary for the week · authored entries")
    log = st.session_state.setdefault("weekly_notes_log", [])
    c1, c2 = st.columns([1, 3])
    author = c1.text_input("Your name", value=st.session_state.get("note_author", ""),
                           placeholder="e.g. Antonie")
    st.session_state["note_author"] = author
    note = c2.text_area("Note", height=90, key="note_draft",
                        placeholder="Add commentary for the week...")
    if st.button("Add note", type="primary",
                 disabled=not (author.strip() and note.strip())):
        stamp = datetime.now(ZoneInfo("Africa/Johannesburg")).strftime("%d %b %Y %H:%M SAST")
        log.insert(0, {"author": author.strip(), "when": stamp,
                       "text": note.strip(), "history": []})
        st.session_state.pop("note_draft", None)  # clear the draft box
        st.rerun()

    editing = st.session_state.get("note_editing")
    for i, n in enumerate(log):
        n.setdefault("history", [])
        if editing == i:
            # the note card itself becomes the editor: ONE tile, textarea
            # blended in, declaration + actions on a single row inside it
            with st.container(border=True, key=f"note_editor_{i}"):
                new_text = st.text_area("Edit note", value=n["text"],
                                        key=f"nt_{i}", height=90,
                                        label_visibility="collapsed")
                r1, r2, r3, _ = st.columns([3.2, 0.7, 0.9, 2.2],
                                           vertical_alignment="center")
                change_type = r1.radio(
                    "Declare this change",
                    ["Material — record", "Minor — don't record"],
                    index=None, horizontal=True, key=f"nm_{i}",
                    label_visibility="collapsed")
                material = (change_type or "").startswith("Material")
                save = r2.button("Save", key=f"ns_{i}", type="primary",
                                 disabled=not (author.strip() and change_type),
                                 help="Declare material or minor first")
                cancel = r3.button("Cancel", key=f"nc_{i}")
            if save:
                if new_text.strip() and new_text.strip() != n["text"]:
                    if material:
                        stamp = datetime.now(ZoneInfo("Africa/Johannesburg")).strftime(
                            "%d %b %Y %H:%M SAST")
                        n["history"].append({
                            "editor": author.strip(), "when": stamp,
                            "diff": _word_diff(n["text"], new_text.strip())})
                    n["text"] = new_text.strip()
                st.session_state.pop("note_editing", None)
                st.rerun()
            if cancel:
                st.session_state.pop("note_editing", None)
                st.rerun()
            continue

        edited = (f' · last edited by <b>{ui.esc(n["history"][-1]["editor"])}</b> '
                  f'· {ui.esc(n["history"][-1]["when"])}' if n["history"] else "")
        st.markdown(
            f'''<div class="news-card"><div class="sm">{ui.esc(n["text"])}</div>
            <div class="mt"><b>{ui.esc(n["author"])}</b> · {ui.esc(n["when"])}{edited}</div></div>''',
            unsafe_allow_html=True)
        b1, b2, b3, _ = st.columns([0.7, 0.9, 1.6, 7])
        if b1.button("Edit", key=f"ne_{i}", disabled=not author.strip(),
                     help="Enter your name above to edit"):
            st.session_state["note_editing"] = i
            st.rerun()
        if b2.button("Delete", key=f"nd_{i}", disabled=not author.strip(),
                     help="Enter your name above to delete"):
            log.pop(i)
            st.rerun()
        if n["history"]:
            with b3.popover(f"History ({len(n['history'])})"):
                for h in n["history"]:
                    st.markdown(
                        f'''<div class="rail-item">{h["diff"]}<br>
                        <span style="color:#909288;font-size:10.5px;">edited by
                        <b>{ui.esc(h["editor"])}</b> · {ui.esc(h["when"])}</span></div>''',
                        unsafe_allow_html=True)
    st.caption("Names are self-declared; material edits are attributed with "
               "word-level change highlights, minor fixes (e.g. spelling) update "
               "the text silently. Verified identity requires OIDC sign-in via "
               "IT app registration; durable shared notes need a small external "
               "store.")


def _word_diff(old: str, new: str) -> str:
    """Word-level diff: removals struck through in burgundy, additions
    highlighted in orange."""
    import difflib
    parts = []
    for tok in difflib.ndiff(old.split(), new.split()):
        w = ui.esc(tok[2:])
        if tok.startswith("  "):
            parts.append(w)
        elif tok.startswith("- "):
            parts.append(f'<span style="color:#B0212C;text-decoration:'
                         f'line-through;">{w}</span>')
        elif tok.startswith("+ "):
            parts.append(f'<span style="background:#FFE1D0;color:#8A3A00;'
                         f'border-radius:3px;padding:0 2px;">{w}</span>')
    return " ".join(parts)


def _moves_block():
    ui.section("Week's largest moves", "")
    gainers, losers = markets.get_movers(top_n=4)
    st.markdown('<div class="card">' +
                "".join(ui.mover_row(q) for q in gainers + losers) +
                "</div>", unsafe_allow_html=True)


def _releases_block():
    ui.section("Upcoming releases", "Next 7 days")
    cal = calendar_data.get_calendar()
    high = [e for e in cal if e["importance"] == "High"] or cal
    if high:
        day = None
        for e in high[:6]:
            if e.get("day") and e["day"] != day:
                day = e["day"]
                ui.cal_day_header(day)
            ui.cal_row(e)
    else:
        ui.empty_state("Calendar feed unavailable right now.")


def _moves_and_releases(stacked=False):
    _moves_block()
    _releases_block()


def page_reports():
    mode = st.radio("Report mode", ["Weekly — Executive Summary", "Monthly — Full pack"],
                    horizontal=True)
    monthly = mode.startswith("Monthly")

    c1, c2 = st.columns([1, 2.4])
    with c1:
        if st.button("Generate report", type="primary"):
            with st.spinner("Compiling report from live data..."):
                st.session_state["report_html"] = report_builder.build_report(monthly)
                st.session_state["report_kind"] = "monthly" if monthly else "weekly"
    with c2:
        st.caption("Generates a self-contained, RisCura-branded HTML file compiled "
                   "from live data. Open it in any browser; use Print, then Save as "
                   "PDF, for distribution.")

    html = st.session_state.get("report_html")
    if html:
        kind = st.session_state.get("report_kind", "weekly")
        fname = f"RisCura_Market_News_{kind}_{datetime.now(timezone.utc).strftime('%Y%m%d')}.html"
        st.download_button("Download report", data=html, file_name=fname,
                           mime="text/html")
        ui.section("Preview", fname)
        st.components.v1.html(html, height=650, scrolling=True)


def page_settings():
    ui.section("Data Sources", "Target premium source → current free stand-in")
    for name, role, standin in NAMED_SOURCES:
        st.markdown(
            f'<div class="cal-row"><span class="cty" style="width:230px;">{ui.esc(name)}</span>'
            f'<span class="ev">{ui.esc(role)}</span>'
            f'<span class="cal-val" style="width:380px;text-align:left;">{ui.esc(standin)}</span></div>',
            unsafe_allow_html=True)
    st.caption("No trend extrapolation, predictive modelling or AI-generated market "
               "predictions anywhere in this application. Each provider lives in "
               "data_sources/ behind a stable interface; swapping one does not touch "
               "the views.")

    ui.section("Alert thresholds", "Set by the PM team · applied immediately")
    st.caption("A move beyond the warning level raises a Warning alert; beyond "
               "the critical level, a Critical alert. Percent of prior close. "
               "Session-scoped until sign-in and shared storage are added.")
    cur = dict(markets.get_thresholds())
    labels = {"index": "Indices", "fx": "FX", "commodity": "Commodities",
              "crypto": "Crypto"}
    cols = st.columns(4)
    new_t = {}
    for col, (k, lab) in zip(cols, labels.items()):
        with col:
            w, c = cur.get(k, markets.DEFAULT_THRESHOLDS[k])
            w2 = st.slider(f"{lab} — warning %", 0.5, 10.0, float(w), 0.25,
                           key=f"thr_w_{k}")
            c2 = st.slider(f"{lab} — critical %", w2, 15.0, max(float(c), w2), 0.25,
                           key=f"thr_c_{k}")
            new_t[k] = (w2, c2)
    b1, b2, _ = st.columns([1, 1, 4])
    if b1.button("Apply thresholds", type="primary"):
        st.session_state["alert_thresholds"] = new_t
        st.toast("Alert thresholds updated.")
        st.rerun()
    if b2.button("Reset to defaults"):
        st.session_state.pop("alert_thresholds", None)
        st.rerun()

    ui.section("Secrets", "Streamlit Cloud → App → Settings → Secrets")
    st.markdown(
        '<div class="card">'
        '<code>APP_PASSWORD = "..."</code> — access gate (required in production)<br>'
        '<code>TE_API_KEY = "user:key"</code> — optional; upgrades calendar to full '
        'country coverage incl. SA/India</div>',
        unsafe_allow_html=True,
    )
    st.markdown(" ")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Force refresh all data"):
            markets.clear_caches()
            st.rerun()
    with c2:
        st.caption("Cache TTLs — markets 5 min · news 15 min · announcements 30 min · "
                   "calendar 60 min · macro 24 h.")
