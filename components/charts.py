"""Plotly builders themed to the design system."""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

NAVY = "#003B71"      # Anthracite
BLUE = "#26B7E6"      # Bright cyan (brand chart #8)
GREEN = "#1E8052"     # Forest green (brand)
RED = "#B0212C"       # Burgundy (brand)
GRID = "#ECECEA"
TEXT = "#4C4D52"


def sparkline(values: list[float], height: int = 42,
              label: str = "") -> go.Figure:
    color = GREEN if values and values[-1] >= values[0] else RED
    fig = go.Figure(go.Scatter(
        y=values, mode="lines", line=dict(width=1.6, color=color),
        fill="tozeroy", fillcolor=color.replace(")", "") + "" if False else
        ("rgba(30,128,82,.08)" if color == GREEN else "rgba(176,33,44,.08)"),
        hoverinfo="skip",
    ))
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False), yaxis=dict(visible=False),
        showlegend=False,
    )
    if values:
        lo, hi = min(values), max(values)
        pad = (hi - lo) * 0.1 or 1
        fig.update_yaxes(range=[lo - pad, hi + pad])
    if label:
        fig.add_annotation(x=0, y=1, xref="paper", yref="paper", text=label,
                           showarrow=False, xanchor="left", yanchor="top",
                           font=dict(size=8.5, color="#B9BBB4", family="Lato"))
    return fig


def intraday_spark(values: list[float], prev_close: float,
                   height: int = 42) -> go.Figure:
    """Windows-widget style: today's session line vs dashed prior close."""
    up = values[-1] >= prev_close
    color = GREEN if up else RED
    fig = go.Figure(go.Scatter(
        y=values, mode="lines", line=dict(width=1.8, color=color),
        hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=[len(values) - 1], y=[values[-1]], mode="markers",
                             marker=dict(size=5, color=color), hoverinfo="skip"))
    fig.add_hline(y=prev_close, line_dash="dot", line_width=1,
                  line_color="#B9BBB4")
    lo = min(min(values), prev_close)
    hi = max(max(values), prev_close)
    pad = (hi - lo) * 0.15 or 1
    fig.update_layout(
        height=height, margin=dict(l=0, r=0, t=0, b=0),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, range=[lo - pad, hi + pad]),
        showlegend=False)
    fig.add_annotation(x=0, y=1, xref="paper", yref="paper", text="1D",
                       showarrow=False, xanchor="left", yanchor="top",
                       font=dict(size=8.5, color="#B9BBB4", family="Lato"))
    return fig


def line_chart(series: pd.Series, title: str = "", height: int = 300,
               color: str = NAVY, y_title: str = "") -> go.Figure:
    fig = go.Figure(go.Scatter(
        x=series.index, y=series.values, mode="lines",
        line=dict(width=2, color=color),
        hovertemplate="%{x|%d %b %Y}<br>%{y:,.2f}<extra></extra>",
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=TEXT, family="Lato")),
        height=height, margin=dict(l=10, r=10, t=36 if title else 10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Lato", size=11, color=TEXT),
        xaxis=dict(gridcolor=GRID, zeroline=False, title=dict(text="Date", font=dict(size=11))),
        yaxis=dict(gridcolor=GRID, zeroline=False, title=dict(text=y_title, font=dict(size=11))),
        showlegend=False,
    )
    return fig


def multi_line(df: pd.DataFrame, title: str = "", height: int = 340,
               y_title: str = "", highlight: str = "South Africa") -> go.Figure:
    """Editorial comparison: highlighted series in RisCura orange, peers in
    muted greys, direct end-of-line labels instead of a legend."""
    muted = ["#B9BBB4", "#9FA199", "#C9CBC4", "#8A8C84", "#AFB6C4"]
    fig = go.Figure()
    _labels: list = []
    mi = 0
    for col in df.columns:
        series = df[col].dropna()
        if series.empty:
            continue
        hl = str(col) == highlight
        color = "#FF671D" if hl else muted[mi % len(muted)]
        if not hl:
            mi += 1
        fig.add_trace(go.Scatter(
            x=series.index, y=series.values, mode="lines", name=str(col),
            line=dict(width=3 if hl else 1.8, color=color, shape="spline",
                      smoothing=0.6),
            hovertemplate=f"{col} · %{{x}}: %{{y:,.2f}}<extra></extra>",
        ))
        # collect for collision-free labelling after all traces are known
        _labels.append((float(series.values[-1]), series.index[-1],
                        str(col), hl))
    # spread end labels so they never overlap
    if _labels:
        ys = [l[0] for l in _labels]
        span = (max(ys) - min(ys)) or 1.0
        gap = span * max(0.10, 16.0 / max(height - 90, 120))
        order = sorted(_labels, key=lambda l: l[0])
        placed = []
        for y, *_ in order:
            placed.append(y if not placed else max(y, placed[-1] + gap))
        overflow = placed[-1] - (max(ys) + span * 0.05)
        if overflow > 0:  # keep labels inside the plot: shift the stack down
            placed = [p - overflow for p in placed]
        for (y, x, name, hl), y_adj in zip(order, placed):
            fig.add_annotation(
                x=x, y=y_adj, text=f"<b>{name}</b>" if hl else name,
                font=dict(size=10.5, color="#FF671D" if hl else "#8A8C84",
                          family="Lato"),
                showarrow=False, xanchor="left", xshift=6, yanchor="middle")
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=TEXT, family="Lato")),
        height=height, margin=dict(l=10, r=110, t=36 if title else 10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Lato", size=11, color=TEXT),
        xaxis=dict(showgrid=False, zeroline=False,
                   title=dict(text="Year", font=dict(size=11))),
        yaxis=dict(gridcolor=GRID, zeroline=False,
                   title=dict(text=y_title, font=dict(size=11))),
        showlegend=False,
    )
    return fig


def bar_years(pairs: list[tuple[int, float]], title: str = "",
              height: int = 260, y_title: str = "%") -> go.Figure:
    """Annual observations: neutral bars, latest year emphasised in RisCura
    orange (level series carry no good/bad meaning, so no green/red)."""
    years = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]
    colors = ["#C9CBC4"] * len(vals)
    if colors:
        colors[-1] = "#FF671D"
    fig = go.Figure(go.Bar(x=years, y=vals, marker_color=colors,
                           hovertemplate="%{x}: %{y:,.2f}<extra></extra>"))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=TEXT, family="Lato")),
        height=height, margin=dict(l=10, r=10, t=36 if title else 10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Lato", size=11, color=TEXT),
        xaxis=dict(showgrid=False, zeroline=False, type="category",
                   title=dict(text="Year", font=dict(size=11))),
        yaxis=dict(gridcolor=GRID, zeroline=True, zerolinecolor="#C9CBC4",
                   title=dict(text=y_title, font=dict(size=11))),
        showlegend=False,
    )
    return fig
