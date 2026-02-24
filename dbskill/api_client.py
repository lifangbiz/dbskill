"""
Skill 侧的 API 模式 HTTP 客户端。

调用 DBSkill Web 服务的 /schema、/query、/execute 接口。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Mapping, Optional
from urllib.error import HTTPError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class ApiClientError(Exception):
    """API 请求失败（4xx/5xx 或网络错误），detail 可含服务端返回信息。"""
    def __init__(self, message: str, status_code: Optional[int] = None, body: Optional[str] = None):
        self.status_code = status_code
        self.body = body
        super().__init__(message)


def _request(
    base_url: str,
    path: str,
    token: str,
    method: str = "GET",
    body: Optional[dict] = None,
) -> dict:
    url = urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body_str: Optional[str] = None
        try:
            body_str = e.read().decode("utf-8", errors="replace")
        except Exception:
            pass
        msg = f"API request failed: {e.code} {e.reason}"
        if body_str:
            try:
                detail = json.loads(body_str).get("detail", body_str)
                msg += f" — {detail}"
            except Exception:
                msg += f" — {body_str[:500]}"
        raise ApiClientError(msg, status_code=e.code, body=body_str) from e


def call_list_databases(api_url: str, api_token: str) -> List[Dict[str, Any]]:
    """调用 GET /databases，返回当前 token 可用的数据库列表 [{alias, permission}, ...]。"""
    result = _request(api_url, "/databases", api_token, method="GET")
    return result.get("data", [])


def call_schema(
    api_url: str,
    api_token: str,
    table: Optional[str] = None,
    db_alias: Optional[str] = None,
) -> Dict[str, Any]:
    """调用 GET /schema，返回 schema 数据。"""
    params = []
    if table:
        params.append(f"table={table}")
    if db_alias:
        params.append(f"db_alias={db_alias}")
    path = "/schema" + ("?" + "&".join(params) if params else "")
    result = _request(api_url, path, api_token, method="GET")
    tid = result.get("trace_id")
    if tid:
        logger.info("trace_id: %s", tid)
    return result.get("data", {})


def call_query(
    api_url: str,
    api_token: str,
    sql: str,
    params: Optional[Mapping[str, Any]] = None,
    db_alias: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """调用 POST /query，返回行列表。"""
    body = {"sql": sql, "params": dict(params or {}), "db_alias": db_alias}
    result = _request(api_url, "/query", api_token, method="POST", body=body)
    tid = result.get("trace_id")
    if tid:
        logger.info("trace_id: %s", tid)
    return result.get("data", [])


def call_execute(
    api_url: str,
    api_token: str,
    sql: str,
    params: Optional[Mapping[str, Any]] = None,
    db_alias: Optional[str] = None,
) -> int:
    """调用 POST /execute，返回影响行数。"""
    body = {"sql": sql, "params": dict(params or {}), "db_alias": db_alias}
    result = _request(api_url, "/execute", api_token, method="POST", body=body)
    tid = result.get("trace_id")
    if tid:
        logger.info("trace_id: %s", tid)
    return result.get("data", {}).get("rows_affected", 0)


__all__ = ["ApiClientError", "call_schema", "call_query", "call_execute", "call_list_databases"]
