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

import time
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import streamlit as st

_CAP = 200
_CALL_CAP = 300
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


# --------------------------------------------------------------------------
# Operational call log: one row per external API call or internal action,
# with latency and outcome. This is telemetry (ephemeral, session-scoped),
# deliberately separate from the durable AI audit trail (ai_audit.py) and
# from live health (feed_status). Cache HITS never reach here — only real
# work does, which is what makes latency meaningful.
# --------------------------------------------------------------------------
def record_call(source: str, kind: str, ok: bool, ms: int,
                detail: str = "") -> None:
    """kind: 'api' (external) or 'action' (internal). detail: error text or
    a short note (e.g. row count)."""
    try:
        entry = {
            "when": datetime.now(_SAST).strftime("%H:%M:%S"),
            "source": source, "kind": kind,
            "ok": "✓" if ok else "✕", "_ok": ok,
            "ms": ms, "detail": str(detail)[:200],
        }
        buf = st.session_state.setdefault("_obs_calls", [])
        buf.insert(0, entry)
        del buf[_CALL_CAP:]
    except Exception:
        pass


@contextmanager
def track(source: str, kind: str = "api"):
    """Time a call and record its outcome. Re-raises on error so callers keep
    their own fail-soft handling — this only observes:

        with obs.track("SARB Web API"):
            r = requests.get(...)

    On exception the event is logged as failed (with the error) and the
    exception propagates to the caller's existing try/except.
    """
    t0 = time.perf_counter()
    try:
        yield
        record_call(source, kind, True, int((time.perf_counter() - t0) * 1000))
    except Exception as e:  # noqa: BLE001
        record_call(source, kind, False,
                    int((time.perf_counter() - t0) * 1000),
                    f"{type(e).__name__}: {e}")
        raise


def note_action(source: str, detail: str = "") -> None:
    """Record an internal action that isn't a timed call (cache clear, save)."""
    record_call(source, "action", True, 0, detail)


def calls() -> list[dict]:
    return st.session_state.get("_obs_calls", [])


def clear_calls() -> None:
    st.session_state["_obs_calls"] = []


def call_summary() -> dict:
    buf = calls()
    api = [c for c in buf if c["kind"] == "api"]
    fails = sum(1 for c in api if not c["_ok"])
    lat = [c["ms"] for c in api if c["_ok"] and c["ms"] > 0]
    return {"total": len(buf), "api": len(api), "fails": fails,
            "avg_ms": int(sum(lat) / len(lat)) if lat else 0}
