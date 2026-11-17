"""Minimal Procore API client for the Developer Sandbox.

Auth follows Procore's Quick Start (authorization code flow with the
out of band redirect URI, sandbox only). Tokens are stored in .tokens.json,
which is git ignored.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

import requests

LOGIN_URL = os.getenv("PROCORE_LOGIN_URL", "https://login-sandbox.procore.com")
API_URL = os.getenv("PROCORE_API_URL", "https://sandbox.procore.com")
REDIRECT_URI = "urn:ietf:wg:oauth:2.0:oob"
TOKEN_FILE = Path(os.getenv("PROCORE_TOKEN_FILE", ".tokens.json"))


def _client() -> tuple[str, str]:
    cid, secret = os.getenv("PROCORE_CLIENT_ID"), os.getenv("PROCORE_CLIENT_SECRET")
    if not cid or not secret:
        raise SystemExit("Set PROCORE_CLIENT_ID and PROCORE_CLIENT_SECRET (see .env.example).")
    return cid, secret


def authorize_url() -> str:
    cid, _ = _client()
    query = urlencode({"response_type": "code", "client_id": cid, "redirect_uri": REDIRECT_URI})
    return f"{LOGIN_URL}/oauth/authorize?{query}"


def _save(tokens: dict) -> dict:
    tokens["obtained_at"] = int(time.time())
    TOKEN_FILE.write_text(json.dumps(tokens, indent=2))
    return tokens


def exchange_code(code: str) -> dict:
    cid, secret = _client()
    resp = requests.post(f"{LOGIN_URL}/oauth/token/", data={
        "grant_type": "authorization_code", "code": code.strip(),
        "client_id": cid, "client_secret": secret, "redirect_uri": REDIRECT_URI,
    }, timeout=30)
    resp.raise_for_status()
    return _save(resp.json())


def _refresh(tokens: dict) -> dict:
    cid, secret = _client()
    resp = requests.post(f"{LOGIN_URL}/oauth/token/", data={
        "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
        "client_id": cid, "client_secret": secret, "redirect_uri": REDIRECT_URI,
    }, timeout=30)
    resp.raise_for_status()
    return _save(resp.json())


def _access_token() -> str:
    if not TOKEN_FILE.exists():
        raise SystemExit("No token yet. Run: python -m health_check auth")
    tokens = json.loads(TOKEN_FILE.read_text())
    age = time.time() - tokens.get("obtained_at", 0)
    if age > tokens.get("expires_in", 0) - 120:
        tokens = _refresh(tokens)
    return tokens["access_token"]


class Procore:
    def __init__(self, company_id: int | None = None):
        self.company_id = company_id
        self.session = requests.Session()
        self.session.headers["Authorization"] = f"Bearer {_access_token()}"
        if company_id:
            self.session.headers["Procore-Company-Id"] = str(company_id)

    def get_all(self, path: str, params: dict | None = None, per_page: int = 100) -> list[dict]:
        """GET every page of a list endpoint."""
        results, page = [], 1
        while True:
            query = {**(params or {}), "page": page, "per_page": per_page}
            resp = self.session.get(f"{API_URL}{path}", params=query, timeout=30)
            resp.raise_for_status()
            batch = resp.json()
            if not isinstance(batch, list):
                return [batch]
            results.extend(batch)
            if len(batch) < per_page:
                return results
            page += 1

    def companies(self) -> list[dict]:
        return self.get_all("/rest/v1.0/companies")

    def projects(self) -> list[dict]:
        return self.get_all("/rest/v1.1/projects", {"company_id": self.company_id})

    def rfis(self, project_id: int) -> list[dict]:
        return self.get_all(f"/rest/v1.0/projects/{project_id}/rfis")

    def submittals(self, project_id: int) -> list[dict]:
        return self.get_all(f"/rest/v1.1/projects/{project_id}/submittals")
