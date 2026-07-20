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
    instr = "".join(badge(i.upper(), "orange")
                    for i in (item.get("instruments") or [])[:3])
    st.markdown(
        f'''<div class="news-card">
        <div class="hl"><a href="{esc(item["link"])}" target="_blank">{esc(item["title"])}</a></div>
        <div class="sm">{esc(item["summary"])}</div>
        <div class="mt">
          {sentiment_badge(item["sentiment"])}{importance_badge(item["importance"])}
          {instr}{badge(item["region"], "grey")}{badge(item["asset"], "grey")}{tags}
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
    right = (f'<div>Consensus <b>{exp}</b></div>'
             f'<div>Previous <b>{prev}</b></div>')
    sev = {"High": "tl-high", "Medium": "tl-med"}.get(e["importance"], "")
    st.markdown(
        f'''<div class="tl-row">
        <span class="tl-time num">{when}</span>
        <span class="tl-dot {sev}"></span>
        <span class="tl-body"><span class="cty">{esc(e["country"])}</span>
        {imp} {esc(e["event"])}</span>
        <span class="cal-val num" style="width:210px;">{right}</span>
        </div>''',
        unsafe_allow_html=True,
    )


def cal_day_header(day: str):
    st.markdown(f'<div class="cal-day">{esc(day)}</div>', unsafe_allow_html=True)


def legend(text: str):
    st.markdown(f'<div class="legend">{esc(text)}</div>', unsafe_allow_html=True)


def num_or_none(v):
    """Parse a displayable number (possibly a formatted string) to float."""
    try:
        return float(str(v).replace(",", "").replace("%", "").strip())
    except (TypeError, ValueError):
        return None


def spark_svg(vals, w: int = 150, h: int = 30, dot: str = "") -> str:
    """Thin neutral inline-SVG sparkline (brand rule: orange is emphasis only,
    so trend lines stay graphite). Optional endpoint dot colour carries the
    window's direction. Each line is normalised to its own range."""
    vals = [float(v) for v in vals]
    if len(vals) > 40:  # downsample for smoothness and payload size
        step = len(vals) / 40.0
        vals = [vals[int(i * step)] for i in range(40)] + [vals[-1]]
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1.0
    n = len(vals) - 1
    pts = " ".join(f"{i * (w - 8) / n + 4:.1f},"
                   f"{h - 4 - (v - lo) / rng * (h - 8):.1f}"
                   for i, v in enumerate(vals))
    lx = (w - 8) + 4
    ly = h - 4 - (vals[-1] - lo) / rng * (h - 8)
    dot_svg = (f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="2.6" fill="{dot}"/>'
               if dot else "")
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'xmlns="http://www.w3.org/2000/svg"><polyline points="{pts}" '
            f'fill="none" stroke="#6B6D64" stroke-width="1.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/>{dot_svg}</svg>')


def mover_row(q) -> str:
    return (f'<div class="mv-row"><span class="mv-nm">{esc(q.name)}</span>'
            f'<span class="mv-val num">{q.fmt.format(q.price)}</span>'
            f'<span class="mv-chg num {chg_cls(q.change_pct)}">{q.change_pct:+.2f}%</span></div>')


def empty_state(msg: str):
    st.markdown(f'<div class="empty">{esc(msg)}</div>', unsafe_allow_html=True)


def hero(item: dict, time_str: str):
    why = esc(item.get("why")) if item.get("why") else (
        "Elevated importance based on macro keywords and breadth of coverage; "
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


def summary_row(q, spark_fig=None, key="", period=""):
    """Widget-style row: name/sub | sparkline | value/%. The chart period
    ('1D'/'1M') is shown in the subtitle, never over the chart."""
    import streamlit as st  # local to avoid circulars at import time
    c1, c2, c3 = st.columns([2.2, 1.2, 1.2], vertical_alignment="center")
    from data_sources.markets import SUMMARY_SUBTITLES
    sub = SUMMARY_SUBTITLES.get(q.name, "")
    chip = f'<span class="pbdg">{esc(period)}</span>' if period else ""
    with c1:
        st.markdown(f'<div class="sum-nm">{esc(q.name)} {chip}</div>'
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


def tl_row(e: dict):
    """Timeline row for the economic calendar: time gutter, impact dot, card.
    Market-holiday rows render distinctly (no consensus/previous fields)."""
    import streamlit as st
    if e.get("is_holiday"):
        st.markdown(
            f'''<div class="tl-row tl-holiday">
            <div class="tl-gutter num">—</div>
            <div class="tl-line"><span class="tl-dot"></span></div>
            <div class="tl-card">
              <span class="t-cty">{esc(e["country"])}</span>
              <span class="t-ev">{esc(e["event"])}</span>
              <span class="t-hol">MARKET CLOSED</span>
            </div></div>''',
            unsafe_allow_html=True)
        return
    sev = ("tl-high" if e["importance"] == "High"
           else "tl-medium" if e["importance"] == "Medium" else "")
    mover = e["importance"] == "High"  # market-moving flag on the card
    flag = '<span class="t-mover">MARKET-MOVING</span>' if mover else ""
    st.markdown(
        f'''<div class="tl-row {sev}{' tl-mover' if mover else ''}">
        <div class="tl-gutter num">{esc((e.get("time") or "")[:5])}</div>
        <div class="tl-line"><span class="tl-dot"></span></div>
        <div class="tl-card">
          <span class="t-cty">{esc(e["country"])}</span>
          <span class="t-ev">{esc(e["event"])}{flag}</span>
          <span class="t-vals num">Consensus <b>{esc(e["expected"])}</b><br>
          Previous <b>{esc(e["previous"])}</b></span>
        </div></div>''',
        unsafe_allow_html=True)


def cal_mini(e: dict):
    """Compact stacked event card for narrow columns (exec summary rail)."""
    edge = {"High": "#FF671D", "Medium": "#F2C84A"}.get(e["importance"], "#E2E3E0")
    exp, prev = esc(e["expected"]), esc(e["previous"])
    st.markdown(
        f'''<div style="background:#FFFFFF;border:1px solid #E2E3E0;
        border-left:3px solid {edge};border-radius:8px;padding:8px 10px;
        margin-bottom:6px;">
        <div style="font-size:11px;color:#909288;">
        {esc(e.get("time") or e["date"])} · <b style="color:#212322;">{esc(e["country"])}</b></div>
        <div style="font-size:12px;font-weight:700;color:#212322;line-height:1.3;
        margin:2px 0;">{esc(e["event"])}</div>
        <div style="font-size:11px;color:#6B6D64;" class="num">
        Cons {exp} · Prev {prev}</div></div>''',
        unsafe_allow_html=True)
