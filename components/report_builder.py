"""Builds a self-contained, RisCura-branded HTML report from live data.
Weekly = Executive Summary only; Monthly = full pack. The file downloads via
st.download_button and prints cleanly to PDF from any browser."""
from __future__ import annotations

import html as _html
from datetime import datetime, timezone

from data_sources import calendar_data, macro, markets, news


def _e(s) -> str:
    return _html.escape(str(s or ""))


_CSS = """
body{font-family:Lato,'Segoe UI',Roboto,sans-serif;color:#212322;margin:0;
background:#FFFFFF;}
.page{max-width:960px;margin:0 auto;padding:28px 34px;}
.head{border-bottom:3px solid #FF671D;padding-bottom:14px;margin-bottom:22px;}
.logo{font-size:24px;font-weight:900;color:#003B71;}
.logo span{color:#FF671D;}
.sub{font-size:12px;color:#909288;letter-spacing:1.4px;text-transform:uppercase;}
h2{font-size:15px;color:#003B71;text-transform:uppercase;letter-spacing:1px;
border-bottom:1px solid #E2E3E0;padding-bottom:5px;margin:26px 0 10px 0;}
table{width:100%;border-collapse:collapse;font-size:12px;}
th{background:#F2F2F2;color:#003B71;text-align:left;padding:6px 9px;
border-bottom:2px solid #E2E3E0;font-size:10.5px;text-transform:uppercase;
letter-spacing:.6px;}
td{padding:6px 9px;border-bottom:1px solid #F2F2F2;font-variant-numeric:tabular-nums;}
.up{color:#1E8052;font-weight:700;}.dn{color:#B0212C;font-weight:700;}
.item{margin-bottom:11px;}
.item .t{font-weight:700;font-size:12.5px;color:#212322;}
.item .s{font-size:11.5px;color:#4C4D52;}
.item .m{font-size:10px;color:#909288;}
.note{font-size:10.5px;color:#909288;margin-top:4px;}
.disc{font-size:10px;color:#909288;border-top:1px solid #E2E3E0;margin-top:30px;
padding-top:10px;font-style:italic;}
@media print{.page{padding:0;}}
"""


def _chg(q) -> str:
    if q.change_pct is None:
        return "<td>—</td>"
    cls = "up" if q.change_pct > 0 else "dn" if q.change_pct < 0 else ""
    return f'<td class="{cls}">{q.change_pct:+.2f}%</td>'


def _quotes_table(quotes, title: str) -> str:
    rows = "".join(
        f"<tr><td>{_e(q.name)}</td>"
        + (f"<td>{q.fmt.format(q.price)}</td>{_chg(q)}<td>{_e(q.asof or '')}</td>"
           if q.ok else "<td colspan=3>unavailable</td>") + "</tr>"
        for q in quotes)
    return (f"<h2>{_e(title)}</h2><table><tr><th>Instrument</th><th>Last</th>"
            f"<th>Move</th><th>As at</th></tr>{rows}</table>")


def _news_block(items, n: int, title: str) -> str:
    blocks = "".join(
        f'<div class="item"><div class="t">{_e(i["title"])}</div>'
        f'<div class="s">{_e(i["summary"])}</div>'
        f'<div class="m">{_e(i["source"])} · {_e(i["region"])} · {_e(i["asset"])} · '
        f'{_e(i["importance"])} importance · {_e(i["sentiment"])}</div></div>'
        for i in items[:n])
    return f"<h2>{_e(title)}</h2>{blocks or '<div class=note>No stories available.</div>'}"


def build_report(monthly: bool) -> str:
    now = datetime.now(timezone.utc)
    kind = "Monthly Full Pack" if monthly else "Weekly Executive Summary"
    items = news.get_news()
    parts = [f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>RisCura Market News — {kind}</title><style>{_CSS}</style></head>
<body><div class="page">
<div class="head"><div class="logo">Ris<span>Cura</span> Market News</div>
<div class="sub">{kind} · Produced {now.strftime('%d %B %Y')} ·
Sources as attributed per section</div></div>"""]

    # Executive summary content (both modes)
    parts.append(_news_block(items, 5, "Top stories"))
    parts.append(_quotes_table(markets.get_summary_strip(), "Global market summary"))
    alerts = markets.get_shock_alerts()
    if alerts:
        rows = "".join(f"<tr><td>{_e(a['severity'])}</td><td>{_e(a['title'])}</td>"
                       f"<td>{_e(a['asof'])}</td></tr>" for a in alerts)
        parts.append(f"<h2>Market shock alerts</h2><table><tr><th>Severity</th>"
                     f"<th>Event</th><th>As at</th></tr>{rows}</table>"
                     f"<div class='note'>Rule-based on observed session moves; "
                     f"no forecasting.</div>")
    cal = calendar_data.get_calendar()
    if cal:
        rows = "".join(f"<tr><td>{_e(e['country'])}</td><td>{_e(e['event'])}</td>"
                       f"<td>{_e(e['date'])}</td><td>{_e(e['expected'])}</td>"
                       f"<td>{_e(e['previous'])}</td></tr>" for e in cal[:14])
        parts.append(f"<h2>Economic calendar — next 7 days</h2><table>"
                     f"<tr><th>Country</th><th>Event</th><th>Date</th><th>Expected</th>"
                     f"<th>Previous</th></tr>{rows}</table>")

    if monthly:
        parts.append(_quotes_table(markets.get_commodities(), "Commodities"))
        parts.append(_quotes_table(markets.get_fx(), "Currencies vs USD"))
        matrix = macro.wb_latest_matrix()
        head = "".join(f"<th>{_e(r)}</th>" for r in macro.REGIONS)
        body = ""
        for ind, per_region in matrix.items():
            cells = "".join(
                f"<td>{v:,.2f} <span style='color:#909288'>({y})</span></td>"
                if (cell := per_region.get(r)) and (y := cell[0]) is not None
                and (v := cell[1]) is not None else "<td>—</td>"
                for r in macro.REGIONS)
            body += f"<tr><td><b>{_e(ind)}</b></td>{cells}</tr>"
        parts.append(f"<h2>Regional macro comparison</h2><table>"
                     f"<tr><th>Indicator</th>{head}</tr>{body}</table>"
                     f"<div class='note'>World Bank Open Data, latest available "
                     f"annual observation per country.</div>")
        parts.append(_news_block(
            [i for i in items if i["importance"] == "High"], 8,
            "Weekly key events"))

    parts.append("<div class='disc'>This content is based on supplied information "
                 "and existing documents. It may contain inaccuracies and should "
                 "always be reviewed by a human before submission.</div>"
                 "</div></body></html>")
    return "".join(parts)
