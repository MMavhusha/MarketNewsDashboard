"""Weekly Key Events, Reports (weekly/monthly with real download), Settings."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import streamlit as st

from components import report_builder, ui
from data_sources import markets, news, notes_store

NAMED_SOURCES = [
    ("Bloomberg", "News, markets, corporate actions", "Public RSS wires / yfinance"),
    ("Reuters", "News wires", "Reuters via public RSS"),
    ("International Monetary Fund", "Macro comparisons, WEO", "World Bank Open Data (aligned series)"),
    ("Individual country central banks", "Policy rates, releases", "SARB Web API live (SA); others pending"),
    ("J.P. Morgan", "Research, FX forecasts", "Not available free — commentary derived from observed moves only"),
    ("RiscFlash", "Commodities & currencies", "yfinance (drop-in replacement ready)"),
    ("Trading Economics", "Calendar, indicators", "Forex Factory public feed; TE key upgrades coverage"),
]


def render_weekly_view():
    """The 'This week' view, embedded in Market News: curated 7-day stories,
    weekly movers, upcoming releases, and the shared editorial-notes system
    (this page's unique asset). Was the standalone Weekly Key Events page."""
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
                                placeholder="e.g. Jon Doe")
        c2.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)
        if c2.button("Set", disabled=not name_in.strip(),
                     use_container_width=True):
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
    # Upcoming releases live on Calendar & Alerts — don't reproduce the feed
    # here; point to the single source instead.
    ui.section("Upcoming releases", "Scheduled data & market closures")
    st.caption("The full scheduled agenda — data releases and market "
               "holidays across all covered regions — lives on the "
               "Calendar & Alerts page.")
    if st.button("Open Calendar & Alerts →", key="wk_goto_cal",
                 use_container_width=True):
        st.session_state["nav_to"] = "Calendar & Alerts"
        st.rerun()


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


def _admin_ok() -> bool:
    return bool(st.session_state.get("_admin_ok"))


# Only these accounts may unlock the admin area.
_ADMIN_EMAILS = {"ltshirangwana@riscura.com", "mmavhusha@riscura.com"}


def _admin_unlock_gate():
    """Admin gate: authorized email AND correct password, both required.
    Email is checked against an allowlist; password uses a timing-safe
    comparison (hmac) so it can't be probed by response timing."""
    import hmac
    try:
        admin_pw = st.secrets.get("ADMIN_PASSWORD")
    except FileNotFoundError:
        admin_pw = None
    if not admin_pw:
        st.caption("Admin area not configured — add an ADMIN_PASSWORD secret "
                   "to Streamlit Cloud to unlock developer diagnostics.")
        return
    st.caption("Restricted to authorized RisCura administrators. "
               "Both email and password are required.")
    e1, p1, b1 = st.columns([1.6, 1.2, 0.6])
    email = e1.text_input("Admin email", key="_admin_email",
                          label_visibility="collapsed",
                          placeholder="name@riscura.com")
    attempt = p1.text_input("Admin password", type="password",
                            key="_admin_try", label_visibility="collapsed",
                            placeholder="Admin password")
    if b1.button("Unlock", use_container_width=True):
        email_ok = email.strip().lower() in _ADMIN_EMAILS
        pw_ok = hmac.compare_digest(str(attempt), str(admin_pw))
        # Check both before responding; don't reveal which half failed.
        if email_ok and pw_ok:
            st.session_state["_admin_ok"] = True
            st.session_state["_admin_email"] = email.strip().lower()
            st.rerun()
        else:
            st.error("Access denied — email not authorized or password "
                     "incorrect.")


def _team_keyword_watchlist():
    ui.section("Keyword watchlist \u0026 alerts",
               "Standing alerts for topics your team tracks")
    st.caption("Add terms like Eskom, Fed, rate decision or Naspers and choose "
               "whether each watches news, the calendar, or both. Each becomes "
               "a standing alert on Calendar & Alerts with live match counts "
               "and one-click links to the exact stories or events \u2014 "
               "remembered across logins until you remove it. Matches are also "
               "flagged \u2691 on Market News and the Executive Summary.")
    from data_sources import app_state as _apps, watchlist as _wl
    if not _apps.enabled():
        st.warning("Shared storage is off (no GITHUB_TOKEN) — keywords, saved "
                   "articles and watchlist changes last for this session only "
                   "and won't be remembered at next login. Add a GITHUB_TOKEN "
                   "secret to persist them.", icon="⚠️")
    kws = _wl.get()
    a1, a2, a3 = st.columns([2.4, 1, 0.8])
    new_kw = a1.text_input("Add keyword or phrase", key="kw_new",
                           placeholder="e.g. Eskom, rate decision, Naspers",
                           label_visibility="collapsed")
    scope_label = a2.selectbox("Watch", ["News + Calendar", "News only",
                                         "Calendar only"], key="kw_scope",
                               label_visibility="collapsed")
    scope = {"News + Calendar": "both", "News only": "news",
             "Calendar only": "calendar"}[scope_label]
    if a3.button("Add", disabled=not new_kw.strip(), use_container_width=True):
        if new_kw.strip().lower() not in [k["term"].lower() for k in kws]:
            kws.append({"term": new_kw.strip(), "scope": scope})
            _wl.set_list(kws)
            _apps.persist("add watchlist keyword")
        st.session_state.pop("kw_new", None)
        st.rerun()
    if kws:
        _scope_txt = {"both": "news + calendar", "news": "news only",
                      "calendar": "calendar only"}
        for i, k in enumerate(kws):
            c1, c2 = st.columns([5, 0.7])
            c1.markdown(
                f'<div class="wl-item"><span class="wl-term">{ui.esc(k["term"])}</span>'
                f'<span class="wl-scope">{_scope_txt[k["scope"]]}</span></div>',
                unsafe_allow_html=True)
            if c2.button("Remove", key=f"wl_rm_{i}", use_container_width=True):
                kws.pop(i)
                _wl.set_list(kws)
                _apps.persist("remove watchlist keyword")
                st.rerun()


def _team_alert_thresholds():
    ui.section("Alert thresholds", "When an observed move raises an alert")
    st.caption("A move beyond the warning level raises a Warning alert; beyond "
               "the critical level, a Critical alert. Percent of prior close.")
    cur = dict(markets.get_thresholds())
    labels = {"index": "Indices", "fx": "FX", "commodity": "Commodities",
              "crypto": "Crypto"}
    cols = st.columns(4)
    new_t = {}
    for col, (k, lab) in zip(cols, labels.items()):
        with col:
            w, c = cur.get(k, markets.DEFAULT_THRESHOLDS[k])
            w2 = st.slider(f"{lab} \u2014 warning %", 0.5, 10.0, float(w), 0.25,
                           key=f"thr_w_{k}")
            c2 = st.slider(f"{lab} \u2014 critical %", w2, 15.0, max(float(c), w2),
                           0.25, key=f"thr_c_{k}")
            new_t[k] = (w2, c2)
    from data_sources import app_state
    b1, b2, _ = st.columns([1, 1, 4])
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


def _feed_status_panel():
    ui.section("Feed status", "Live diagnostics per data source")
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
        from data_sources import ai_enrich, ai_audit
        # Live health from this session's actual AI calls (the audit trail
        # already records provider/ok/latency per call), not a static string.
        entries, _ = ai_audit.load()
        recent = entries[:6]
        if recent:
            fails = sum(1 for e in recent if not e.get("ok", True))
            health = (f" \u2014 last {len(recent)} calls: {len(recent) - fails} ok"
                      + (f", {fails} failed/rate-limited (chain fell through)"
                         if fails else ", all healthy"))
        else:
            health = " \u2014 no calls yet this session"
        rows.append({"name": "AI classification",
                     "ok": ai_enrich.enabled() and (not recent or
                           any(e.get("ok", True) for e in recent)),
                     "detail": ((f"active via {ai_enrich.provider_label()}"
                                 + health)
                                if ai_enrich.enabled() else
                                "off \u2014 add LLM_API_KEY (Gemini), GROQ_API_KEY "
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
               "now \u2014 the app degrades to explicit 'unavailable' states, "
               "never substitute data.")


def _admin_call_log():
    from data_sources import obs
    cs = obs.call_summary()
    ui.section("API & action log",
               "Every external call and internal action this session")
    rows = obs.calls()
    if not rows:
        st.caption("No calls recorded yet this session. External API calls "
                   "(yfinance, SARB, FRED, World Bank, calendar, GitHub) and "
                   "internal actions (cache clears, saves) are timed and logged "
                   "here as they happen — cache hits are excluded so latency is "
                   "real work only.")
        return
    ui.legend(f"{cs['total']} events · {cs['api']} API calls · "
              f"{cs['fails']} failed · avg {cs['avg_ms']} ms · newest first")
    import pandas as _pd
    view = [{k: v for k, v in r.items() if not k.startswith("_")} for r in rows]
    st.dataframe(_pd.DataFrame(view), hide_index=True, use_container_width=True)
    if st.button("Clear call log", key="calls_clear"):
        obs.clear_calls()
        st.rerun()


def _admin_error_log():
    from data_sources import obs
    s = obs.summary()
    ui.section("System errors",
               "Captured fail-soft failures this session")
    errs = obs.errors()
    if not errs:
        st.caption("No errors captured this session. Data-fetch, feed-parse and "
                   "history failures are recorded here as they occur \u2014 the "
                   "app still degrades gracefully, but nothing fails silently.")
        return
    ui.legend(f"{s['total']} events \u00b7 {s['errors']} errors \u00b7 "
              f"{s['warnings']} warnings \u00b7 newest first \u00b7 session-scoped")
    import pandas as _pd
    st.dataframe(_pd.DataFrame(errs), hide_index=True, use_container_width=True)
    if st.button("Clear error log", key="obs_clear"):
        obs.clear()
        st.rerun()


def _admin_classification_debugger():
    ui.section("Classification debugger",
               "Paste any headline to see how it is classified")
    from data_sources import news as _news
    title = st.text_input("Headline", key="dbg_title",
                          placeholder="e.g. Iran warns U.S. of Hormuz red line")
    summary = st.text_input("Summary (optional)", key="dbg_summary",
                            placeholder="Optional supporting text")
    if title.strip():
        c = _news._classify(title.strip(), summary.strip(), "")
        relevant = _news._is_relevant(title.strip(), summary.strip())
        import pandas as _pd
        rows = [("Sentiment", c["sentiment"]), ("Importance", c["importance"]),
                ("Region", c["region"]), ("Asset", c["asset"]),
                ("Instruments", ", ".join(c["instruments"]) or "\u2014"),
                ("Tags", ", ".join(c["tags"]) or "\u2014"),
                ("Rule confident", "yes" if c["confident"] else "no (would go to model)"),
                ("Passes relevance gate", "yes" if relevant else "no (dropped)")]
        st.dataframe(_pd.DataFrame(rows, columns=["Field", "Rule verdict"]),
                     hide_index=True, use_container_width=True)
        st.caption("This shows the deterministic RULES verdict. In production "
                   "the model overrides these for displayed stories (chain: "
                   "Gemini \u2192 Groq \u2192 rules); this view is the fallback "
                   "and the ground truth for debugging keyword behaviour.")


def _admin_ai_audit():
    ui.section("AI audit trail", "Every actual model invocation")
    from data_sources import ai_audit
    entries, durable = ai_audit.load()
    if not entries:
        st.caption("No AI calls recorded yet"
                   + ("." if durable else
                      " (session-only store \u2014 add GITHUB_TOKEN for a "
                      "durable, git-committed trail)."))
        return
    ui.legend(f"{len(entries)} recorded calls \u00b7 newest first \u00b7 "
              + ("durable \u2014 each entry is a git commit in the repo"
                 if durable else "session-only until GITHUB_TOKEN is set"))
    import pandas as _pd
    df = _pd.DataFrame([{k: v for k, v in e.items() if k != "titles"}
                        for e in entries[:200]])
    st.dataframe(df, hide_index=True, use_container_width=True)
    with st.expander("Headlines sent per call"):
        for e in entries[:30]:
            st.markdown(f'<div class="rail-item"><b>{ui.esc(e["when"])}</b> \u00b7 '
                        + ui.esc("; ".join(e.get("titles", [])[:6])) + "</div>",
                        unsafe_allow_html=True)
    st.download_button("Download full audit log (JSON)",
                       __import__("json").dumps(entries, indent=1),
                       file_name="ai_audit_log.json")


def _admin_data_sources():
    ui.section("Data sources", "Target premium source \u2192 current free stand-in")
    for name, role, standin in NAMED_SOURCES:
        st.markdown(
            f'<div class="cal-row"><span class="cty" style="width:230px;">{ui.esc(name)}</span>'
            f'<span class="ev">{ui.esc(role)}</span>'
            f'<span class="cal-val" style="width:380px;text-align:left;">{ui.esc(standin)}</span></div>',
            unsafe_allow_html=True)
    st.caption("No trend extrapolation, predictive modelling or AI-generated "
               "market predictions anywhere. Each provider lives in "
               "data_sources/ behind a stable interface; swapping one does not "
               "touch the views.")


def _admin_secrets_and_cache():
    ui.section("Secrets", "Streamlit Cloud \u2192 App \u2192 Settings \u2192 Secrets")
    st.markdown(
        '<div class="card">'
        '<code>APP_PASSWORD</code> \u2014 access gate (required in production)<br>'
        '<code>ADMIN_PASSWORD</code> \u2014 unlocks this admin area<br>'
        '<code>GITHUB_TOKEN</code> \u2014 fine-grained PAT, Contents RW; enables '
        'shared notes, team state and the durable audit trail<br>'
        '<code>TE_API_KEY</code> \u2014 optional; full calendar country coverage incl. SA/India<br>'
        '<code>FRED_API_KEY</code> \u2014 optional, free; US/EA policy rates, US 10Y, CPI histories<br>'
        '<code>LLM_API_KEY</code> \u2014 Gemini (default primary), OpenAI-compatible<br>'
        '<code>GROQ_API_KEY</code> \u2014 free fallback tier in the classification chain<br>'
        '<code>ANTHROPIC_API_KEY</code> \u2014 optional alternative model provider'
        '</div>', unsafe_allow_html=True)
    st.caption("Values live only in Streamlit Cloud secrets, never in the repo. "
               "Presence is what matters here \u2014 values are never displayed.")
    c1, c2 = st.columns([1, 3])
    with c1:
        if st.button("Force refresh all data"):
            markets.clear_caches()
            st.rerun()
    with c2:
        st.caption("Cache TTLs \u2014 markets 5 min \u00b7 news 15 min \u00b7 "
                   "announcements 30 min \u00b7 calendar 60 min \u00b7 macro 24 h.")


def page_settings():
    # Team-facing configuration first: this is where PMs land and what they
    # actually change. Developer/admin diagnostics are gated below.
    _team_keyword_watchlist()
    _team_alert_thresholds()
    _feed_status_panel()

    ui.section("Admin \u0026 diagnostics", "Developer tools \u00b7 restricted access")
    if not _admin_ok():
        _admin_unlock_gate()
        return
    who = st.session_state.get("_admin_email", "admin")
    lc1, lc2 = st.columns([3, 0.8])
    lc1.caption(f"Signed in as {who} · admin unlocked for this session.")
    if lc2.button("Log out", use_container_width=True):
        st.session_state.pop("_admin_ok", None)
        st.session_state.pop("_admin_email", None)
        st.rerun()
    _admin_call_log()
    _admin_error_log()
    _admin_classification_debugger()
    _admin_ai_audit()
    _admin_data_sources()
    _admin_secrets_and_cache()
