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
               color: str = NAVY) -> go.Figure:
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
        xaxis=dict(gridcolor=GRID, zeroline=False),
        yaxis=dict(gridcolor=GRID, zeroline=False),
        showlegend=False,
    )
    return fig


def multi_line(df: pd.DataFrame, title: str = "", height: int = 320) -> go.Figure:
    palette = ["#FF671D", "#1F3864", "#909288", "#2A8B7C", "#B0212C", "#F2C84A"]  # brand chart order (Ice too light on white)
    fig = go.Figure()
    for i, col in enumerate(df.columns):
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col], mode="lines", name=str(col),
            line=dict(width=2, color=palette[i % len(palette)]),
        ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=TEXT, family="Lato")),
        height=height, margin=dict(l=10, r=10, t=36 if title else 10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Lato", size=11, color=TEXT),
        xaxis=dict(gridcolor=GRID, zeroline=False),
        yaxis=dict(gridcolor=GRID, zeroline=False),
        legend=dict(orientation="h", y=-0.18, font=dict(size=10.5)),
    )
    return fig


def bar_years(pairs: list[tuple[int, float]], title: str = "",
              height: int = 260) -> go.Figure:
    years = [p[0] for p in pairs]
    vals = [p[1] for p in pairs]
    colors = [GREEN if v >= 0 else RED for v in vals]
    fig = go.Figure(go.Bar(x=years, y=vals, marker_color=colors,
                           hovertemplate="%{x}: %{y:,.2f}<extra></extra>"))
    fig.update_layout(
        title=dict(text=title, font=dict(size=13, color=TEXT, family="Lato")),
        height=height, margin=dict(l=10, r=10, t=36 if title else 10, b=10),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Lato", size=11, color=TEXT),
        xaxis=dict(gridcolor=GRID, zeroline=False, type="category"),
        yaxis=dict(gridcolor=GRID, zeroline=True, zerolinecolor="#D0D5DD"),
        showlegend=False,
    )
    return fig
