"""Weekly Key Events, Reports (weekly/monthly with real download), Settings."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from components import report_builder, ui
from data_sources import calendar_data, macro, markets, news, notes_store

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
               "upcoming releases and largest observed moves.")

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
                f'''<div class="ann-row">
                <span class="b-col">{ui.importance_badge(item["importance"])}</span>
                <span class="b-col">{ui.sentiment_badge(item["sentiment"])}</span>
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

    shared = notes_store.enabled()
    ui.section("Editorial notes",
               "Commentary for the week · " +
               ("shared, saved to the repo with a full commit audit trail"
                if shared else "authored entries"))
    if shared:
        try:
            log, sha = notes_store.load()
        except Exception:
            st.warning("Note store unreachable (GitHub API) — showing "
                       "session-only notes for now.", icon="⚠️")
            shared, log, sha = False, st.session_state.setdefault(
                "weekly_notes_log", []), None
    else:
        log, sha = st.session_state.setdefault("weekly_notes_log", []), None

    def _persist(action: str):
        nonlocal sha
        if not shared:
            st.session_state["weekly_notes_log"] = log
            return True
        try:
            sha = notes_store.save(log, sha, st.session_state.get(
                "note_author", ""), action)
            return True
        except notes_store.Conflict:
            st.warning("Someone saved changes while you were editing — the "
                       "latest notes have been reloaded; please re-apply your "
                       "change.", icon="⚠️")
            st.rerun()
        except Exception as e:
            st.error(f"Could not save to the repo: {e}")
            return False
    editing_now = st.session_state.get("note_editing")
    # -- identity: asked once, then a quiet "Posting as" line --
    author = st.session_state.get("note_author", "").strip()
    if editing_now is not None:
        ui.legend("Editing a note below — Save or Cancel to add new notes.")
    if editing_now is None and (not author or st.session_state.get("_edit_identity")):
        c1, c2, _ = st.columns([1.4, 0.6, 3])
        name_in = c1.text_input("Your name", value=author,
                                placeholder="e.g. Antonie")
        if c2.button("Set", disabled=not name_in.strip()):
            st.session_state["note_author"] = name_in.strip()
            st.session_state.pop("_edit_identity", None)
            st.rerun()
        author = ""
    elif editing_now is None:
        i1, i2, _ = st.columns([2.4, 0.6, 4])
        i1.markdown(
            f'<div style="font-size:12px;color:#909288;padding-top:6px;">'
            f'{ui.badge(author[:1].upper(), "blue")} Posting as '
            f'<b style="color:#212322;">{ui.esc(author)}</b></div>',
            unsafe_allow_html=True)
        if i2.button("Change", key="chg_id"):
            st.session_state["_edit_identity"] = True
            st.rerun()

    # -- compact compose bar (hidden while a note is being edited) --
    if editing_now is None:
        cc1, cc2 = st.columns([6, 0.9], vertical_alignment="bottom")
        note = cc1.text_area("Note", height=68, key="note_draft",
                             label_visibility="collapsed",
                             placeholder="Add a note for the week…")
        add_clicked = cc2.button("Add", type="primary", use_container_width=True,
                                 disabled=not (author and note.strip()))
    else:
        note, add_clicked = "", False
    if add_clicked:
        stamp = datetime.now(ZoneInfo("Africa/Johannesburg")).strftime(
            "%d %b %Y %H:%M SAST")
        log.insert(0, {"author": author, "when": stamp,
                       "text": note.strip(), "history": []})
        if _persist("add note"):
            st.session_state.pop("note_draft", None)  # clear the draft box
            st.rerun()

    def _week_of(n):
        try:
            d = datetime.strptime(n["when"][:11], "%d %b %Y").date()
            monday = d - timedelta(days=d.weekday())
            return monday
        except Exception:
            return None

    editing = st.session_state.get("note_editing")
    current_week = None
    for i, n in enumerate(log):
        n.setdefault("history", [])
        wk = _week_of(n)
        if wk != current_week:
            current_week = wk
            ui.cal_day_header(f"Week of {wk.strftime('%d %B %Y')}" if wk
                              else "Earlier")
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
                    _persist("edit note")
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
            <div class="mt">{ui.badge((n["author"] or "?")[:1].upper(), "blue")}
            <b>{ui.esc(n["author"])}</b> · {ui.esc(n["when"])}{edited}</div></div>''',
            unsafe_allow_html=True)
        if editing_now is not None:
            continue  # keep focus on the note being edited
        b1, b2, b3, _ = st.columns([0.7, 0.9, 1.6, 7])
        if b1.button("Edit", key=f"ne_{i}", disabled=not author.strip(),
                     help="Enter your name above to edit"):
            st.session_state["note_editing"] = i
            st.rerun()
        if b2.button("Delete note", key=f"nd_{i}", disabled=not author.strip(),
                     help="Removes the note and its in-app history"):
            log.pop(i)
            _persist("delete note")
            st.rerun()
        if n["history"]:
            with b3.popover(f"History ({len(n['history'])})"):
                for j, h in enumerate(list(n["history"])):
                    h1, h2 = st.columns([8, 1])
                    h1.markdown(
                        f'''<div class="rail-item">{h["diff"]}<br>
                        <span style="color:#909288;font-size:10.5px;">edited by
                        <b>{ui.esc(h["editor"])}</b> · {ui.esc(h["when"])}</span></div>''',
                        unsafe_allow_html=True)
                    if h2.button("✕", key=f"hd_{i}_{j}",
                                 disabled=not author.strip(),
                                 help="Remove this recorded change"):
                        n["history"].pop(j)
                        _persist("remove revision record")
                        st.rerun()
                st.caption("Removing a record here tidies the in-app history; "
                           "when the repo store is on, the underlying git "
                           "commits remain the immutable audit trail.")
    if shared:
        st.caption("Notes are shared with the whole team and every save is a "
                   "git commit in the repo (immutable audit trail). Names are "
                   "self-declared until OIDC sign-in is added via IT.")
    else:
        st.caption("Session-only mode: add a GITHUB_TOKEN secret (fine-grained, "
                   "Contents read/write on this repo) to make notes shared, "
                   "durable and fully audited via git history. Names are "
                   "self-declared until OIDC sign-in is added.")


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
    ui.section("Week's largest moves",
               "Core + extended universe · 24 tracked instruments")
    gainers, losers = markets.get_weekly_movers(top_n=4)
    if gainers or losers:
        st.markdown('<div class="card">' +
                    "".join(ui.mover_row(q) for q in gainers + losers) +
                    "</div>", unsafe_allow_html=True)
        ui.legend("1W % = last close vs the last close on/before 7 days "
                  "prior · published closes, yfinance")
    else:
        ui.empty_state("Weekly history unavailable from the free feed "
                       "right now.")


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
    ui.section("Feed status", "Live diagnostics per source")
    from data_sources import calendar_data as _cal, news as _news, sarb as _sarb
    rows = []
    strip_ok = sum(1 for q in markets.get_summary_strip() if q.ok)
    rows.append({"name": "yfinance markets", "ok": strip_ok > 0,
                 "detail": f"{strip_ok}/9 strip instruments returning data"})
    rows += _news.get_feed_status()
    rows.append(_cal.feed_status())
    rows.append(_sarb.feed_status())
    from data_sources import fred as _fred
    rows.append(_fred.feed_status())
    try:
        from data_sources import ai_enrich
        rows.append({"name": "AI classification",
                     "ok": ai_enrich.enabled(),
                     "detail": ((f"active via {ai_enrich.provider_label()} — "
                                 "model-primary: every displayed story is "
                                 "classified by the chain in batches; rules "
                                 "stand only if all providers fail")
                                if ai_enrich.enabled() else
                                "off — add LLM_API_KEY (Gemini), GROQ_API_KEY "
                                "or ANTHROPIC_API_KEY to enable")})
    except Exception:
        pass
    for r in rows:
        dot = ("#1E8052" if r["ok"] else "#B0212C")
        st.markdown(
            f'<div class="cal-row"><span style="width:10px;height:10px;'
            f'border-radius:50%;background:{dot};flex-shrink:0;"></span>'
            f'<span class="cty" style="width:240px;">{ui.esc(r["name"])}</span>'
            f'<span class="ev">{ui.esc(r["detail"])}</span></div>',
            unsafe_allow_html=True)
    st.caption("A red source means the provider is unreachable or empty right "
               "now — the app degrades to explicit 'unavailable' states, never "
               "substitute data.")

    ui.section("AI audit trail", "Admin only · every actual model invocation")
    admin_pw = None
    try:
        admin_pw = st.secrets.get("ADMIN_PASSWORD")
    except FileNotFoundError:
        pass
    if not admin_pw:
        st.caption("Not configured — add an ADMIN_PASSWORD secret to enable "
                   "the admin-gated audit view. Calls are being recorded "
                   "regardless once an AI provider is active.")
    elif not st.session_state.get("_admin_ok"):
        a1, a2, _ = st.columns([1.6, 0.6, 3])
        attempt = a1.text_input("Admin password", type="password",
                                key="_admin_try", label_visibility="collapsed",
                                placeholder="Admin password")
        if a2.button("Unlock") and attempt == admin_pw:
            st.session_state["_admin_ok"] = True
            st.rerun()
    else:
        from data_sources import ai_audit
        entries, durable = ai_audit.load()
        if not entries:
            st.caption("No AI calls recorded yet"
                       + ("." if durable else
                          " (session-only store — add GITHUB_TOKEN for a "
                          "durable, git-committed trail)."))
        else:
            ui.legend(f"{len(entries)} recorded calls · newest first · "
                      + ("durable — each entry is a git commit in the repo"
                         if durable else "session-only until GITHUB_TOKEN is set"))
            import pandas as _pd
            df = _pd.DataFrame([{k: v for k, v in e.items() if k != "titles"}
                                for e in entries[:200]])
            st.dataframe(df, hide_index=True, use_container_width=True)
            with st.expander("Headlines sent per call"):
                for e in entries[:30]:
                    st.markdown(f'<div class="rail-item"><b>{ui.esc(e["when"])}</b> · '
                                + ui.esc("; ".join(e.get("titles", [])[:6])) + "</div>",
                                unsafe_allow_html=True)
            st.download_button("Download full audit log (JSON)",
                               __import__("json").dumps(entries, indent=1),
                               file_name="ai_audit_log.json")

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

    ui.section("News keyword watchlist", "PM team · flagged on Market News and "
               "surfaced under Keyword Alerts on the Executive Summary")
    from data_sources import app_state as _apps
    kws = st.session_state.setdefault("news_watch_keywords", [])
    k1, k2 = st.columns([3, 0.8])
    new_kw = k1.text_input("Add keyword or phrase", key="kw_new",
                           placeholder="e.g. Eskom, rate decision, Naspers",
                           label_visibility="collapsed")
    if k2.button("Add keyword", disabled=not new_kw.strip()):
        if new_kw.strip().lower() not in [k.lower() for k in kws]:
            kws.append(new_kw.strip())
            _apps.persist("add news keyword")
        st.session_state.pop("kw_new", None)
        st.rerun()
    if kws:
        pick_rm = st.pills("Remove", [f"✕ {k}" for k in kws], default=None,
                           key="kw_rm", label_visibility="collapsed")
        if pick_rm:
            kws.remove(pick_rm[2:])
            _apps.persist("remove news keyword")
            st.rerun()
        st.caption("Matching uses the same typo-tolerant search as the news "
                   "filters. Alerts are in-app (flag + rail card); email/Teams "
                   "push needs SMTP or a webhook — future phase.")

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
    from data_sources import app_state
    if b1.button("Apply thresholds", type="primary"):
        st.session_state["alert_thresholds"] = new_t
        app_state.persist("update alert thresholds")
        st.toast("Alert thresholds updated"
                 + (" and saved for the team." if app_state.enabled() else "."))
        st.rerun()
    if b2.button("Reset to defaults"):
        st.session_state.pop("alert_thresholds", None)
        app_state.persist("reset alert thresholds")
        st.rerun()

    if not st.session_state.get("_admin_ok"):
        return  # secrets documentation is admin-only
    ui.section("Secrets", "Admin · Streamlit Cloud → App → Settings → Secrets")
    st.markdown(
        '<div class="card">'
        '<code>APP_PASSWORD = "..."</code> — access gate (required in production)<br>'
        '<code>TE_API_KEY = "user:key"</code> — optional; upgrades calendar to full '
        'country coverage incl. SA/India<br>'
        '<code>FRED_API_KEY = "..."</code> — optional, free (fred.stlouisfed.org); fills US/Euro-Area policy rates and the US 10Y from Fed/ECB series (120 req/min limit, used a handful of times per day)<br>'
        '<code>LLM_API_KEY = "..."</code> — optional; any OpenAI-compatible provider (defaults to Google Gemini free tier, model gemini-2.5-flash; override with LLM_API_BASE / LLM_MODEL for Groq, Databricks, Mistral)<br>'
        '<code>ANTHROPIC_API_KEY = "sk-ant-..."</code> — optional alternative; upgrades news '
        'sentiment/importance/region tagging and the hero rationale from keyword '
        'rules to model classification (no forecasting)</div>',
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
