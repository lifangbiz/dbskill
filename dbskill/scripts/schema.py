"""
Schema 查询脚本（Direct / API 双模式的对外入口）。

当前实现 Direct 模式，针对关系型数据库（PostgreSQL/MySQL/SQLite）：
- 读取 config.yaml；
- 基于 db_alias/default_db 选择数据库；
- 查询元数据并返回表结构。

API 模式将在后续基于 HTTP 客户端接入。
"""

from typing import Any, Dict, List, Optional

from sqlalchemy import text

from dbskill.api_client import call_schema as api_call_schema
from dbskill.utils import (
    AppConfig,
    AuditConfig,
    DatabaseConfig,
    get_database_config,
    load_config,
    run_direct_query,
)


def _resolve_db(app_config: AppConfig, db_alias: Optional[str]) -> DatabaseConfig:
    return get_database_config(app_config, db_alias=db_alias)


def _normalize_schema_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """将可能为大写或别名的列名统一为 table_name, column_name, data_type。"""
    key_map = {
        "table_name": ("table_name", "TABLE_NAME", "TABNAME"),
        "column_name": ("column_name", "COLUMN_NAME", "COLNAME"),
        "data_type": ("data_type", "DATA_TYPE", "TYPENAME"),
    }
    out: Dict[str, Any] = {}
    for target, candidates in key_map.items():
        for c in candidates:
            if c in row and row[c] is not None:
                out[target] = row[c]
                break
    return out


def _normalize_schema_rows(db_type: str, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """将结果集列名统一为 table_name, column_name, data_type（MySQL/PostgreSQL 等可能返回大写列名）。"""
    return [_normalize_schema_row(r) for r in rows]


def _build_schema_query(db_cfg: DatabaseConfig, table: Optional[str]) -> str:
    db_type = (db_cfg.type or "").lower()
    if db_type == "postgres" or db_type == "kingbase":
        base = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = 'public'
        """
        if table:
            base += " AND table_name = :table_name"
        return base + " ORDER BY table_name, ordinal_position"
    if db_type == "mysql" or db_type == "mariadb":
        base = """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = DATABASE()
        """
        if table:
            base += " AND table_name = :table_name"
        return base + " ORDER BY table_name, ordinal_position"
    if db_type == "oracle" or db_type == "dm":
        base = """
        SELECT table_name, column_name, data_type
        FROM user_tab_columns
        """
        if table:
            base += " WHERE table_name = :table_name"
        return base + " ORDER BY table_name, column_id"
    if db_type == "mssql":
        base = """
        SELECT table_name, column_name, data_type
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'dbo'
        """
        if table:
            base += " AND table_name = :table_name"
        return base + " ORDER BY table_name, ordinal_position"
    if db_type == "db2":
        base = """
        SELECT TABNAME AS table_name, COLNAME AS column_name, TYPENAME AS data_type
        FROM SYSCAT.COLUMNS
        """
        if table:
            base += " WHERE TABNAME = :table_name"
        return base + " ORDER BY TABNAME, COLNO"
    if db_type == "sqlite":
        if not table:
            raise ValueError("sqlite schema query requires table name")
        return f"PRAGMA table_info({table})"
    raise ValueError(f"schema query not implemented for database type: {db_type!r}")


def get_schema(
    table: Optional[str] = None,
    db_alias: Optional[str] = None,
    db_cfg: Optional[DatabaseConfig] = None,
    config_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    获取指定库（及可选表）的 Schema 信息。
    若传入 db_cfg（如 API 服务端从后台解析），则直接使用，不再读 config。
    config_path 用于显式指定配置文件路径。
    """
    if db_cfg is not None:
        if db_cfg.mode != "direct":
            raise ValueError("injected db_cfg must be direct mode")
        app_cfg = AppConfig(databases={}, default_db=None, audit=AuditConfig(enabled=False))
    else:
        app_cfg = load_config(explicit_path=config_path)
        db_cfg = _resolve_db(app_cfg, db_alias)

    if db_cfg.mode == "api":
        if not db_cfg.api_url or not db_cfg.api_token:
            raise ValueError("API mode requires api_url and api_token in config")
        return api_call_schema(
            api_url=db_cfg.api_url,
            api_token=db_cfg.api_token,
            table=table,
            db_alias=db_alias or db_cfg.alias,
        )

    if db_cfg.mode != "direct":
        raise ValueError(f"unsupported database mode: {db_cfg.mode}")

    db_type = (db_cfg.type or "").lower()
    sql = _build_schema_query(db_cfg, table)

    if db_type == "sqlite":
        # sqlite 的 PRAGMA table_info 返回不同字段结构，这里单独处理
        rows = run_direct_query(
            app_config=app_cfg,
            db_cfg=db_cfg,
            sql=sql,
            params=None,
            source="skill.schema",
        )
        columns = [
            {"table_name": table, "column_name": r.get("name"), "data_type": r.get("type")}
            for r in rows
        ]
    else:
        params = {"table_name": table} if table else None
        rows = run_direct_query(
            app_config=app_cfg,
            db_cfg=db_cfg,
            sql=sql,
            params=params,
            source="skill.schema",
        )
        columns = _normalize_schema_rows(db_type, rows)

    return {
        "db_alias": db_cfg.alias,
        "table": table,
        "columns": columns,
    }


__all__ = ["get_schema"]

