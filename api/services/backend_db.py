"""
API 模式：从后台（admin.db）解析数据库配置。

根据当前 API Key 的分配关系返回可用库列表或单个库配置。
"""

from __future__ import annotations

from typing import List

from dbskill.utils import DatabaseConfig

from api.services.models import ApiKey as DbApiKey, init_admin_db, SessionLocal


def list_databases_for_api_key(api_key_id: int) -> List[dict]:
    """
    返回该 API Key 被分配的所有数据库（别名与权限）。
    用于 GET /databases 接口。
    """
    init_admin_db()
    db = SessionLocal()
    try:
        key = db.query(DbApiKey).filter(DbApiKey.id == api_key_id).first()
        if not key:
            return []
        return [
            {"alias": a.database.alias, "permission": a.permission_level}
            for a in key.assignments
        ]
    finally:
        db.close()


def get_db_config_for_api(api_key_id: int, db_alias: str | None) -> DatabaseConfig:
    """
    根据 API Key 与库别名解析数据库配置；校验该 Key 是否被分配该库。
    若 db_alias 为空且 Key 仅有一个库则使用该库；否则用 db_config_ref 或必须指定 db_alias。
    """
    init_admin_db()
    db = SessionLocal()
    try:
        key = db.query(DbApiKey).filter(DbApiKey.id == api_key_id).first()
        if not key:
            raise ValueError("api key not found")
        assignments = list(key.assignments)
        if not assignments:
            raise ValueError("api key has no database assigned")
        alias = db_alias or (key.db_config_ref if key.db_config_ref else None)
        if not alias and len(assignments) == 1:
            alias = assignments[0].database.alias
        if not alias:
            raise ValueError("db_alias required when key has multiple databases or no default")
        for a in assignments:
            d = a.database
            if d.alias == alias:
                return DatabaseConfig(
                    alias=d.alias,
                    type=d.type,
                    mode="direct",
                    permission=a.permission_level or "readonly",
                    host=d.host,
                    port=d.port,
                    user=d.user,
                    password=d.password,
                    database=d.database,
                )
        raise ValueError(f"database not allowed for this token: {alias!r}")
    finally:
        db.close()
