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


def sparkline(values: list[float], height: int = 42) -> go.Figure:
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
        fig.add_annotation(
            x=series.index[-1], y=float(series.values[-1]),
            text=f"<b>{col}</b>" if hl else str(col),
            font=dict(size=10.5, color="#FF671D" if hl else "#8A8C84",
                      family="Lato"),
            showarrow=False, xanchor="left", xshift=6)
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
