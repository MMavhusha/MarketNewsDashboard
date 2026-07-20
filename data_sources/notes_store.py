"""Durable, shared editorial notes stored in the app's own GitHub repo.

Requires a fine-grained personal access token in Streamlit Secrets:
    GITHUB_TOKEN = "github_pat_..."   (Contents: read/write on this repo only)
Optional overrides: GITHUB_REPO ("TshirangwanaL/MarketNewRetry"),
GITHUB_BRANCH ("main").

Why the repo as a store: durable and shared across every user session; every
save is a git commit, so the full audit trail is immutable and free; and the
API's SHA precondition gives optimistic concurrency — simultaneous edits are
detected, never silently overwritten. Falls back to session-only mode when no
token is configured.
"""
from __future__ import annotations

import base64
import json
import os

import requests
import streamlit as st

_PATH = "data/editorial_notes.json"


class Conflict(Exception):
    pass


def _cfg(key: str, default: str = "") -> str:
    try:
        v = st.secrets.get(key)
        if v:
            return v
    except FileNotFoundError:
        pass
    return os.environ.get(key, default)


def _token() -> str:
    return _cfg("GITHUB_TOKEN")


def _repo() -> str:
    return _cfg("GITHUB_REPO", "TshirangwanaL/MarketNewRetry")


def enabled() -> bool:
    return bool(_token())


def _url(path: str = _PATH) -> str:
    return f"https://api.github.com/repos/{_repo()}/contents/{path}"


def _headers() -> dict:
    return {"Authorization": f"Bearer {_token()}",
            "Accept": "application/vnd.github+json"}


def load_json(path: str, default):
    """Returns (obj, sha). (default, None) when the file doesn't exist yet."""
    r = requests.get(_url(path), headers=_headers(), timeout=15,
                     params={"ref": _cfg("GITHUB_BRANCH", "main")})
    if r.status_code == 404:
        return default, None
    r.raise_for_status()
    payload = r.json()
    return (json.loads(base64.b64decode(payload["content"]).decode()),
            payload["sha"])


def save_json(path: str, obj, sha: str | None, actor: str, action: str) -> str:
    body = {"message": f"{path}: {action} by {actor or 'unknown'}",
            "content": base64.b64encode(
                json.dumps(obj, ensure_ascii=False, indent=1).encode()).decode(),
            "branch": _cfg("GITHUB_BRANCH", "main")}
    if sha:
        body["sha"] = sha
    from data_sources import obs
    with obs.track(f"GitHub write · {path}"):
        r = requests.put(_url(path), headers=_headers(), json=body, timeout=15)
        if r.status_code == 409:
            raise Conflict(f"{path} changed since load")
        r.raise_for_status()
        return r.json()["content"]["sha"]


def load() -> tuple[list, str | None]:
    """Returns (notes, sha). ([], None) when the file doesn't exist yet."""
    r = requests.get(_url(), headers=_headers(), timeout=15,
                     params={"ref": _cfg("GITHUB_BRANCH", "main")})
    if r.status_code == 404:
        return [], None
    r.raise_for_status()
    payload = r.json()
    notes = json.loads(base64.b64decode(payload["content"]).decode())
    return notes, payload["sha"]


def save(notes: list, sha: str | None, actor: str, action: str) -> str:
    """Commits the notes file (see save_json)."""
    return save_json(_PATH, notes, sha, actor, action)


def _legacy_save(notes: list, sha: str | None, actor: str, action: str) -> str:
    """(kept for reference)"""
    body = {
        "message": f"editorial notes: {action} by {actor or 'unknown'}",
        "content": base64.b64encode(
            json.dumps(notes, ensure_ascii=False, indent=1).encode()).decode(),
        "branch": _cfg("GITHUB_BRANCH", "main"),
    }
    if sha:
        body["sha"] = sha
    r = requests.put(_url(), headers=_headers(), json=body, timeout=15)
    if r.status_code == 409:
        raise Conflict("notes changed since load")
    r.raise_for_status()
    return r.json()["content"]["sha"]
