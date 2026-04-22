from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def request_json(
    url: str,
    body: dict[str, Any] | None,
    timeout: int,
    headers: dict[str, str] | None = None,
    method: str = "POST",
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json"}
    if headers:
        request_headers.update(headers)

    request_data = None
    if body is not None:
        request_data = json.dumps(body).encode("utf-8")

    req = Request(url=url, data=request_data, headers=request_headers, method=method)
    with urlopen(req, timeout=timeout) as response:
        raw = response.read().decode("utf-8")
        if not raw.strip():
            return {}
        return json.loads(raw)


def http_error_detail(prefix: str, exc: HTTPError) -> str:
    raw = ""
    try:
        raw = exc.read().decode("utf-8", errors="replace").strip()
    except Exception:
        raw = ""

    if raw:
        if len(raw) > 500:
            raw = raw[:500] + "...(truncated)"
        return f"{prefix}: HTTP {exc.code}, body={raw}"
    return f"{prefix}: {exc}"
