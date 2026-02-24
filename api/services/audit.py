"""
Web API 侧审计：
- 记录每次请求的路径、方法、账号、IP、SQL 模板等；
- 与 Skill 侧本地审计互补；
- 使用 API 模式时仅写入数据库（admin.db），不写文件；
- 支持 retention_days 自动清理过期日志；
- 开关与保留天数从 server.yaml 的 api_audit 段读取。
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from fastapi import Request

from api.auth import ApiKey
from api.services.models import ApiAuditLog, SessionLocal, init_admin_db

logger = logging.getLogger(__name__)


def _safe_json_dumps(obj: Any) -> str:
    """序列化 params 为 JSON，对 datetime/UUID/Decimal 等用 str 兜底。"""
    def default(o: Any) -> Any:
        if hasattr(o, "isoformat"):
            return o.isoformat()
        return str(o)
    return json.dumps(obj, ensure_ascii=False, default=default)


@dataclass
class ApiAuditConfig:
    enabled: bool = True
    retention_days: int = 30


def _load_api_audit_config() -> ApiAuditConfig:
    root = Path(__file__).resolve().parents[2]
    path = root / "server.yaml"
    if not path.is_file():
        return ApiAuditConfig()
    import yaml
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    ac = raw.get("api_audit") or {}
    return ApiAuditConfig(
        enabled=bool(ac.get("enabled", True)),
        retention_days=int(ac.get("retention_days", 30)),
    )


API_AUDIT_CONFIG = _load_api_audit_config()

_last_cleanup_date: Optional[str] = None


def write_api_audit_log(
    request: Request,
    api_key: Optional[ApiKey],
    sql: Optional[str],
    params: Optional[Mapping[str, Any]],
    db_alias: Optional[str],
    trace_id: str,
) -> None:
    """将 API 审计记录写入数据库（不写文件）。"""
    if not API_AUDIT_CONFIG.enabled:
        return

    init_admin_db()
    now = datetime.now(timezone.utc)
    db = SessionLocal()
    try:
        params_str = _safe_json_dumps(dict(params or {}))
        row = ApiAuditLog(
            ts=now,
            trace_id=trace_id or "",
            path=request.url.path,
            method=request.method,
            client_ip=request.client.host if request.client else None,
            api_key_name=api_key.name if api_key else None,
            permission_level=api_key.permission_level if api_key else None,
            db_alias=db_alias,
            sql=sql,
            params=params_str,
        )
        db.add(row)
        db.commit()
        _prune_old_audit_logs_if_due()
    except Exception as e:
        logger.exception("write_api_audit_log failed: %s", e)
    finally:
        db.close()


def _prune_old_audit_logs_if_due() -> None:
    """按 retention_days 删除过期审计记录，最多每天执行一次。"""
    global _last_cleanup_date
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _last_cleanup_date == today:
        return
    _last_cleanup_date = today
    cutoff = datetime.now(timezone.utc) - timedelta(days=API_AUDIT_CONFIG.retention_days)
    db = SessionLocal()
    try:
        db.query(ApiAuditLog).filter(ApiAuditLog.ts < cutoff).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _row_to_entry(row: ApiAuditLog) -> dict[str, Any]:
    ts = row.ts
    try:
        params = json.loads(row.params) if row.params else {}
    except (TypeError, ValueError):
        params = {}
    return {
        "ts": ts.isoformat() if ts else "",
        "trace_id": row.trace_id or "",
        "path": row.path or "",
        "method": row.method or "",
        "client_ip": row.client_ip,
        "api_key_name": row.api_key_name,
        "permission_level": row.permission_level,
        "db_alias": row.db_alias,
        "sql": row.sql,
        "params": params,
    }


def list_audit_logs(
    db_session: Any,
    db_alias: Optional[str] = None,
    api_key_name: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[dict[str, Any]], int]:
    """
    从数据库分页查询 API 审计日志。
    支持按 db_alias、api_key_name、日志创建日期 date_from/date_to（YYYY-MM-DD）筛选。
    api_key_name 为 "__unnamed" 时表示筛选无备注名的 key（api_key_name 为空）。
    返回 (当前页条目列表, 总条数)。
    """
    qs = db_session.query(ApiAuditLog)
    db_match = (db_alias or "").strip()
    if db_match:
        qs = qs.filter(ApiAuditLog.db_alias == db_match)
    key_match = (api_key_name or "").strip()
    if key_match == "__unnamed":
        qs = qs.filter((ApiAuditLog.api_key_name == "") | (ApiAuditLog.api_key_name.is_(None)))
    elif key_match:
        qs = qs.filter(ApiAuditLog.api_key_name == key_match)
    date_from_s = (date_from or "").strip()
    if date_from_s:
        try:
            start = datetime.strptime(date_from_s, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            qs = qs.filter(ApiAuditLog.ts >= start)
        except ValueError:
            pass
    date_to_s = (date_to or "").strip()
    if date_to_s:
        try:
            end = datetime.strptime(date_to_s, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, microsecond=999999, tzinfo=timezone.utc
            )
            qs = qs.filter(ApiAuditLog.ts <= end)
        except ValueError:
            pass
    total = qs.count()
    qs = qs.order_by(ApiAuditLog.ts.desc()).offset((page - 1) * per_page).limit(per_page)
    rows = qs.all()
    entries = [_row_to_entry(r) for r in rows]
    return entries, total


__all__ = ["write_api_audit_log", "API_AUDIT_CONFIG", "list_audit_logs"]
