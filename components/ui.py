"""HTML component builders rendered via st.markdown(unsafe_allow_html=True).
All styling lives in assets/styles.css."""
from __future__ import annotations

import html as _html

import streamlit as st


def esc(s: str) -> str:
    return _html.escape(str(s or ""))


def section(title: str, subtitle: str = ""):
    st.markdown(
        f'<div class="sec-h"><span class="t">{esc(title)}</span>'
        f'<span class="sec-rule"></span><span class="s">{esc(subtitle)}</span></div>',
        unsafe_allow_html=True,
    )


def badge(text: str, kind: str = "grey") -> str:
    return f'<span class="bdg bdg-{kind}">{esc(text)}</span>'


def sentiment_badge(s: str) -> str:
    return badge(s, {"Positive": "green", "Negative": "red"}.get(s, "grey"))


def importance_badge(s: str) -> str:
    return badge(s, {"High": "navy", "Medium": "amber"}.get(s, "grey"))


def chg_cls(v) -> str:
    if v is None:
        return "flat"
    return "up" if v > 0 else "dn" if v < 0 else "flat"


def fmt_chg(q) -> str:
    if q.change is None or q.change_pct is None:
        return "—"
    arrow = "▲" if q.change > 0 else "▼" if q.change < 0 else "•"
    return f"{arrow} {q.fmt.format(abs(q.change))} ({q.change_pct:+.2f}%)"


def market_card_html(q) -> str:
    if not q.ok:
        return (f'<div class="mkt-card mkt-na"><div class="nm">{esc(q.name)}</div>'
                f'<div class="vl" style="color:#909288;">—</div>'
                f'<div class="ts">retrying at next refresh</div></div>')
    return (
        f'<div class="mkt-card"><div class="nm">{esc(q.name)}</div>'
        f'<div class="vl num">{q.fmt.format(q.price)}</div>'
        f'<div class="ch {chg_cls(q.change)}">{fmt_chg(q)}</div>'
        f'<div class="ts">{esc(q.asof or "")}</div></div>'
    )


def news_card(item: dict, time_str: str):
    tags = " ".join(badge(t, "blue") for t in item.get("tags", []))
    st.markdown(
        f'''<div class="news-card">
        <div class="hl"><a href="{esc(item["link"])}" target="_blank">{esc(item["title"])}</a></div>
        <div class="sm">{esc(item["summary"])}</div>
        <div class="mt">
          {sentiment_badge(item["sentiment"])}{importance_badge(item["importance"])}
          {badge(item["region"], "grey")}{badge(item["asset"], "grey")}{tags}
        </div>
        <div class="mt"><b>{esc(item["source"])}</b> · {esc(time_str)}</div>
        </div>''',
        unsafe_allow_html=True,
    )


def alert_card(a: dict):
    sev = a["severity"]
    cls = {"Critical": "al-critical", "Warning": "al-warning"}.get(sev, "al-info")
    kind = {"Critical": "red", "Warning": "amber"}.get(sev, "blue")
    st.markdown(
        f'''<div class="alert {cls}">
        <div class="ti">{badge(sev, kind)} {esc(a["title"])}</div>
        <div class="ds">{esc(a["detail"])}</div>
        <div class="mt">Affected: <b>{esc(a["assets"])}</b> · {esc(a["asof"])}</div>
        </div>''',
        unsafe_allow_html=True,
    )


def cal_row(e: dict):
    imp = importance_badge(e["importance"])
    when = esc(e.get("time") or e["date"])
    exp, prev = esc(e["expected"]), esc(e["previous"])
    right = (f'Consensus <b>{exp}</b> · Previous <b>{prev}</b>'
             if (exp, prev) != ("—", "—") else
             '<span style="color:#909288;">no consensus published</span>')
    st.markdown(
        f'''<div class="cal-row">
        <span class="cty">{esc(e["country"])}</span>
        <span class="ev">{imp} {esc(e["event"])}</span>
        <span class="tm num">{when}</span>
        <span class="cal-val num" style="width:230px;">{right}</span>
        </div>''',
        unsafe_allow_html=True,
    )


def cal_day_header(day: str):
    st.markdown(f'<div class="cal-day">{esc(day)}</div>', unsafe_allow_html=True)


def legend(text: str):
    st.markdown(f'<div class="legend">{esc(text)}</div>', unsafe_allow_html=True)


def mover_row(q) -> str:
    return (f'<div class="mv-row"><span class="mv-nm">{esc(q.name)}</span>'
            f'<span class="mv-val num">{q.fmt.format(q.price)}</span>'
            f'<span class="mv-chg num {chg_cls(q.change_pct)}">{q.change_pct:+.2f}%</span></div>')


def empty_state(msg: str):
    st.markdown(f'<div class="empty">{esc(msg)}</div>', unsafe_allow_html=True)


def hero(item: dict, time_str: str):
    why = ("Elevated importance based on macro keywords and breadth of coverage; "
           f"most relevant to <b>{esc(item['asset'])}</b> in <b>{esc(item['region'])}</b>.")
    st.markdown(
        f'''<div class="hero">
        <div class="kicker">Top market story</div>
        <div class="hl">{esc(item["title"])}</div>
        <div class="sum">{esc(item["summary"])}</div>
        <div class="why"><b>Why it matters:</b> {why}</div>
        <div class="meta">{esc(item["source"])} · {esc(time_str)} &nbsp;·&nbsp;
        <a href="{esc(item["link"])}" target="_blank">Read more →</a></div>
        </div>''',
        unsafe_allow_html=True,
    )


def summary_row(q, spark_fig=None, key=""):
    """Widget-style row: name/sub | sparkline | value/%."""
    import streamlit as st  # local to avoid circulars at import time
    c1, c2, c3 = st.columns([2.2, 1.2, 1.2], vertical_alignment="center")
    from data_sources.markets import SUMMARY_SUBTITLES
    sub = SUMMARY_SUBTITLES.get(q.name, "")
    with c1:
        st.markdown(f'<div class="sum-nm">{esc(q.name)}</div>'
                    f'<div class="sum-sub">{esc(sub)}</div>',
                    unsafe_allow_html=True)
    with c2:
        if spark_fig is not None:
            st.plotly_chart(spark_fig, use_container_width=True,
                            config={"displayModeBar": False}, key=key)
    with c3:
        if q.ok:
            pct = (f'<div class="sum-pct {chg_cls(q.change_pct)}">'
                   f'{q.change_pct:+.2f}%</div>' if q.change_pct is not None else "")
            st.markdown(f'{pct}<div class="sum-val num">{q.fmt.format(q.price)}</div>'
                        f'<div class="sum-sub" style="text-align:right;">{esc(q.asof or "")}</div>',
                        unsafe_allow_html=True)
        else:
            st.markdown('<div class="sum-val" style="color:#909288;">—</div>'
                        '<div class="sum-sub" style="text-align:right;">retrying</div>',
                        unsafe_allow_html=True)
    st.markdown('<div class="row-sep"></div>', unsafe_allow_html=True)
