"""Lightweight in-memory observability — an error ring buffer.

The app fails soft everywhere (``except Exception``) so a single dead feed
never takes the page down. The cost of that resilience is that failures are
invisible: nothing is recorded when yfinance rate-limits, a feed 404s, or an
API key lapses. This module captures those events in a capped in-memory ring
so the admin page can surface them, without changing the fail-soft behaviour.

Session-scoped by design: errors are operational signal for the current
session, not durable audit (that is ai_audit.py). Recording never raises.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

_CAP = 200
_SAST = ZoneInfo("Africa/Johannesburg")


def record(where: str, exc: BaseException | str, level: str = "error") -> None:
    """Record a captured failure. `where` is a short call-site label."""
    try:
        detail = (exc if isinstance(exc, str)
                  else f"{type(exc).__name__}: {exc}")
        entry = {
            "when": datetime.now(_SAST).strftime("%H:%M:%S"),
            "where": where, "level": level, "detail": str(detail)[:300],
        }
        buf = st.session_state.setdefault("_obs_errors", [])
        buf.insert(0, entry)
        del buf[_CAP:]
    except Exception:
        pass  # observability must never break the app


@contextmanager
def guard(where: str, level: str = "error"):
    """Wrap a fail-soft block so its exception is captured, not swallowed:

        with obs.guard("markets.get_intraday"):
            ...risky work...

    Behaves exactly like ``except Exception: pass`` for control flow — the
    block is suppressed on error — but the error is now visible to admins.
    """
    try:
        yield
    except Exception as e:  # noqa: BLE001 - intentional fail-soft, now logged
        record(where, e, level)


def errors() -> list[dict]:
    return st.session_state.get("_obs_errors", [])


def clear() -> None:
    st.session_state["_obs_errors"] = []


def summary() -> dict:
    buf = errors()
    return {"total": len(buf),
            "errors": sum(1 for e in buf if e["level"] == "error"),
            "warnings": sum(1 for e in buf if e["level"] == "warning")}
