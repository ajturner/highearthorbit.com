"""HTTP session with retries and a clear error message on failure."""
from __future__ import annotations

import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "highearthorbit-content-sync/1.0 (+https://highearthorbit.com)"


def session(auth: tuple[str, str] | None = None, headers: dict | None = None) -> requests.Session:
    s = requests.Session()
    retry = Retry(total=4, backoff_factor=1.5, status_forcelist=(429, 500, 502, 503, 504), allowed_methods=None)
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.mount("http://", HTTPAdapter(max_retries=retry))
    s.headers["User-Agent"] = USER_AGENT
    if headers:
        s.headers.update(headers)
    if auth:
        s.auth = auth
    return s


def require_env(*names: str) -> list[str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise SystemExit(f"Missing environment variable(s): {', '.join(missing)}")
    return [os.environ[n] for n in names]


def check(resp: requests.Response) -> requests.Response:
    if resp.status_code >= 400:
        detail = resp.text[:500]
        raise RuntimeError(f"{resp.request.method} {resp.url} -> {resp.status_code}: {detail}")
    return resp
