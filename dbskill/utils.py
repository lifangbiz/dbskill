"""
Skill 公共工具模块

负责：
- 加载 config.yaml；
- 解析数据库配置、默认库、审计配置；
- 为 Direct 模式创建 SQLAlchemy Engine。

API 服务也可以复用这里的逻辑，避免重复实现。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional

import json
from datetime import datetime, timedelta, timezone

import yaml
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from dbskill.constants import DEFAULT_PORTS, DB_TYPES_FILE_ONLY, DB_TYPES_REQUIRING_HOST, SUPPORTED_DB_TYPES


@dataclass
class AuditConfig:
    enabled: bool = False
    log_dir: str = "./logs/audit"
    retention_days: int = 30


@dataclass
class DatabaseConfig:
    alias: str
    type: Optional[str] = None  # postgres/mysql/sqlite/...
    mode: str = "direct"  # direct | api
    permission: str = "readonly"  # readonly | write | full
    # direct 模式连接信息
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None
    # api 模式
    api_url: Optional[str] = None
    api_token: Optional[str] = None


@dataclass
class AppConfig:
    databases: Dict[str, DatabaseConfig]
    default_db: Optional[str]
    audit: AuditConfig


def _find_config_file(explicit_path: Optional[str] = None) -> Path:
    """
    查找配置文件（按优先级）：
    1. 显式路径；
    2. 项目根目录下的 config.yaml；
    3. dbskill 目录下的 config.yaml；
    4. dbskill 包所在目录的 config.yaml（当 dbskill 安装在 .cursor/skills/dbskill/ 等自包含目录时）。
    """
    if explicit_path:
        path = Path(explicit_path).expanduser()
        if path.is_file():
            return path
        raise FileNotFoundError(f"config file not found: {explicit_path}")

    # 本文件：dbskill/utils.py -> skill_dir = 包根（可能是项目根 dbskill，也可能是上层 repo 的 dbskill 目录）
    skill_dir = Path(__file__).resolve().parents[1]
    root = skill_dir.parent
    candidates = [
        skill_dir / "config.yaml",         # 包根下的 config（本仓库即项目根时 dbskill/config.yaml）
        root / "config.yaml",
        root / "dbskill" / "config.yaml",
        skill_dir.parent / "config.yaml",  # 自包含安装时：.cursor/skills/dbskill/config.yaml
    ]
    for p in candidates:
        if p.is_file():
            return p

    raise FileNotFoundError(
        "config.yaml not found. 可放在：项目根、dbskill/ 下、或本 dbskill 所在目录（如 .cursor/skills/dbskill/）"
    )


def validate_database_config(db_cfg: DatabaseConfig, alias: str) -> None:
    """
    按 mode 校验数据库配置是否完整、合法。
    - direct：必须含 type；postgres/mysql 需 host, port, user, password, database；sqlite 需 database。
    - api：必须含 api_url、api_token。
    """
    mode = (db_cfg.mode or "").strip().lower()
    if mode not in ("direct", "api"):
        raise ValueError(
            f"databases.{alias}: mode must be 'direct' or 'api', got {db_cfg.mode!r}"
        )

    if mode == "direct":
        db_type = (db_cfg.type or "").strip().lower()
        if not db_type:
            raise ValueError(f"databases.{alias}: direct mode requires 'type' ({', '.join(SUPPORTED_DB_TYPES)})")
        if db_type in DB_TYPES_REQUIRING_HOST:
            for key in ("host", "user"):
                val = getattr(db_cfg, key)
                if val is None or (isinstance(val, str) and not val.strip()):
                    raise ValueError(f"databases.{alias}: direct {db_type} requires '{key}'")
            # dm 可不填 database；其余类型必填
            if db_type != "dm":
                val = db_cfg.database
                if val is None or (isinstance(val, str) and not val.strip()):
                    raise ValueError(f"databases.{alias}: direct {db_type} requires 'database'")
            if db_cfg.port is not None and (not isinstance(db_cfg.port, int) or db_cfg.port <= 0):
                raise ValueError(f"databases.{alias}: direct {db_type} 'port' must be a positive integer")
        elif db_type in DB_TYPES_FILE_ONLY:
            if not db_cfg.database or (isinstance(db_cfg.database, str) and not db_cfg.database.strip()):
                raise ValueError(f"databases.{alias}: direct sqlite requires 'database' (file path)")
        else:
            raise ValueError(
                f"databases.{alias}: direct mode type must be one of {SUPPORTED_DB_TYPES!r}, got {db_type!r}"
            )
    else:  # api
        if not (db_cfg.api_url and db_cfg.api_url.strip()):
            raise ValueError(f"databases.{alias}: api mode requires 'api_url'")
        if not (db_cfg.api_token and db_cfg.api_token.strip()):
            raise ValueError(f"databases.{alias}: api mode requires 'api_token'")


def load_config(explicit_path: Optional[str] = None) -> AppConfig:
    """
    加载并解析 config.yaml，返回结构化配置对象。
    """
    path = _find_config_file(explicit_path)
    raw: Mapping[str, Any]
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    raw_databases = raw.get("databases") or {}
    databases: Dict[str, DatabaseConfig] = {}
    for alias, cfg in raw_databases.items():
        if not isinstance(cfg, Mapping):
            continue
        mode = cfg.get("mode")
        if mode is None or (isinstance(mode, str) and not mode.strip()):
            raise ValueError(f"databases.{alias}: 'mode' is required (direct or api)")
        mode = str(mode).strip().lower()
        if mode not in ("direct", "api"):
            raise ValueError(f"databases.{alias}: mode must be 'direct' or 'api', got {cfg.get('mode')!r}")

        db_cfg = DatabaseConfig(
            alias=alias,
            type=cfg.get("type"),
            mode=mode,
            permission=str(cfg.get("permission", "readonly")),
            host=cfg.get("host"),
            port=cfg.get("port"),
            user=cfg.get("user"),
            password=cfg.get("password"),
            database=cfg.get("database"),
            api_url=cfg.get("api_url"),
            api_token=cfg.get("api_token"),
        )
        validate_database_config(db_cfg, alias)
        databases[alias] = db_cfg

    default_db = raw.get("default_db")
    audit_raw = raw.get("audit") or {}
    log_dir_raw = str(audit_raw.get("log_dir", "./logs/audit"))
    log_dir_path = Path(log_dir_raw)
    if not log_dir_path.is_absolute():
        log_dir_path = (path.parent / log_dir_path).resolve()
    audit = AuditConfig(
        enabled=bool(audit_raw.get("enabled", False)),
        log_dir=str(log_dir_path),
        retention_days=int(audit_raw.get("retention_days", 30)),
    )

    return AppConfig(
        databases=databases,
        default_db=default_db,
        audit=audit,
    )


def get_database_config(
    app_config: AppConfig,
    db_alias: Optional[str] = None,
) -> DatabaseConfig:
    """
    根据别名获取单个数据库配置。未指定时：优先用 default_db；若未配置 default_db 且仅有一个库，则自动取该库。
    """
    alias = db_alias or app_config.default_db
    if not alias:
        if len(app_config.databases) == 1:
            alias = next(iter(app_config.databases.keys()))
        else:
            raise ValueError("no database alias specified and default_db is not set")
    try:
        return app_config.databases[alias]
    except KeyError as exc:
        raise ValueError(f"unknown database alias: {alias}") from exc


# Direct 模式 Engine 缓存，按连接 URL 复用，避免重复创建
_engine_cache: Dict[str, Engine] = {}


def _build_direct_connection_url(db_cfg: DatabaseConfig) -> str:
    """构建 Direct 模式连接 URL，用于 Engine 创建与缓存 key。"""
    db_type = (db_cfg.type or "").lower()
    user = db_cfg.user or ""
    password = db_cfg.password or ""
    host = db_cfg.host or "localhost"
    database = (db_cfg.database or "").strip()

    if db_type == "postgres":
        port = db_cfg.port or DEFAULT_PORTS.get("postgres", 5432)
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database or ''}"
    if db_type == "mysql" or db_type == "mariadb":
        port = db_cfg.port or DEFAULT_PORTS.get("mysql", 3306)
        return f"mysql+pymysql://{user}:{password}@{host}:{port}/{database or ''}"
    if db_type == "oracle":
        port = db_cfg.port or DEFAULT_PORTS.get("oracle", 1521)
        if database:
            return f"oracle+oracledb://{user}:{password}@{host}:{port}/?service_name={database}"
        return f"oracle+oracledb://{user}:{password}@{host}:{port}/"
    if db_type == "mssql":
        port = db_cfg.port or DEFAULT_PORTS.get("mssql", 1433)
        driver = "ODBC+Driver+17+for+SQL+Server"
        return f"mssql+pyodbc://{user}:{password}@{host}:{port}/{database or ''}?driver={driver}"
    if db_type == "db2":
        port = db_cfg.port or DEFAULT_PORTS.get("db2", 50000)
        return f"db2+ibm_db://{user}:{password}@{host}:{port}/{database or ''}"
    if db_type == "dm":
        port = db_cfg.port or DEFAULT_PORTS.get("dm", 5236)
        return f"dm://{user}:{password}@{host}:{port}/"
    if db_type == "kingbase":
        port = db_cfg.port or DEFAULT_PORTS.get("kingbase", 54321)
        return f"postgresql+psycopg2://{user}:{password}@{host}:{port}/{database or ''}"
    if db_type == "sqlite":
        database = db_cfg.database or ":memory:"
        if database == ":memory:":
            return "sqlite+pysqlite:///:memory:"
        return f"sqlite+pysqlite:///{database}"
    raise ValueError(f"unsupported database type for direct mode: {db_type!r}")


def create_sqlalchemy_engine(db_cfg: DatabaseConfig) -> Engine:
    """
    基于 DatabaseConfig 创建或复用 SQLAlchemy Engine。

    支持 postgres, mysql, mariadb, sqlite, oracle, mssql, db2, dm, kingbase。同一连接 URL 会复用缓存的 Engine。
    """
    if db_cfg.mode != "direct":
        raise ValueError("only direct mode databases can create SQLAlchemy engines")

    url = _build_direct_connection_url(db_cfg)
    if url not in _engine_cache:
        _engine_cache[url] = create_engine(url, future=True)
    return _engine_cache[url]


def _ensure_audit_dir(audit_cfg: AuditConfig) -> Path:
    path = Path(audit_cfg.log_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


_skill_audit_last_cleanup: Optional[str] = None


def _prune_audit_logs_if_due(audit_cfg: AuditConfig) -> None:
    """按 retention_days 清理过期日志，最多每天执行一次。"""
    global _skill_audit_last_cleanup
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if _skill_audit_last_cleanup == today:
        return
    _skill_audit_last_cleanup = today
    log_dir = Path(audit_cfg.log_dir)
    if not log_dir.is_dir():
        return
    cutoff = datetime.now(timezone.utc) - timedelta(days=audit_cfg.retention_days)
    for f in log_dir.glob("*.jsonl"):
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < cutoff:
                f.unlink()
        except OSError:
            pass


def write_audit_log(
    app_config: AppConfig,
    db_cfg: DatabaseConfig,
    sql: str,
    params: Optional[Mapping[str, Any]],
    rows_affected: Optional[int],
    source: str,
) -> None:
    """
    写入本地 JSONL 审计日志（Direct 模式）。
    """
    if not app_config.audit.enabled:
        return

    log_dir = _ensure_audit_dir(app_config.audit)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    log_file = log_dir / f"{day}.jsonl"

    record: Dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "db_alias": db_cfg.alias,
        "mode": db_cfg.mode,
        "sql": sql,
        "params": dict(params or {}),
        "rows_affected": rows_affected,
        "source": source,
    }

    with log_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False))
        f.write("\n")

    _prune_audit_logs_if_due(app_config.audit)


SQL_READONLY_PREFIXES: Iterable[str] = ("select", "with")
SQL_WRITE_PREFIXES: Iterable[str] = ("insert", "update", "delete")


def _strip_sql_leading_comments(sql: str) -> str:
    """去掉 SQL 开头的行注释和块注释，便于正确识别首词（如 SELECT/WITH）。"""
    lines: list[str] = []
    rest = sql.strip()
    while rest:
        if rest.startswith("--"):
            line, _, rest = rest.partition("\n")
            rest = rest.lstrip()
            continue
        if rest.startswith("/*"):
            end = rest.find("*/", 2)
            if end == -1:
                break
            rest = rest[end + 2 :].lstrip()
            continue
        break
    return rest


def _normalize_sql_prefix(sql: str) -> str:
    sql = _strip_sql_leading_comments(sql.strip())
    return sql.split(None, 1)[0].lower() if sql else ""


def ensure_readonly_sql(sql: str) -> None:
    prefix = _normalize_sql_prefix(sql)
    if not any(prefix.startswith(p) for p in SQL_READONLY_PREFIXES):
        raise ValueError("only SELECT/CTE queries are allowed in readonly mode")


def ensure_write_sql(sql: str, allow_delete: bool) -> None:
    prefix = _normalize_sql_prefix(sql)
    if not any(prefix.startswith(p) for p in SQL_WRITE_PREFIXES):
        raise ValueError("only INSERT/UPDATE/DELETE statements are allowed in execute mode")
    if prefix.startswith("delete") and not allow_delete:
        raise PermissionError("DELETE is only allowed for permission=full")


def check_permission_for_read(db_cfg: DatabaseConfig) -> None:
    if db_cfg.permission not in ("readonly", "write", "full"):
        raise PermissionError(f"invalid permission level: {db_cfg.permission}")


def check_permission_for_write(db_cfg: DatabaseConfig, sql: str) -> None:
    if db_cfg.permission not in ("write", "full"):
        raise PermissionError("write operations require permission=write or permission=full")
    allow_delete = db_cfg.permission == "full"
    ensure_write_sql(sql, allow_delete=allow_delete)


def run_direct_query(
    app_config: AppConfig,
    db_cfg: DatabaseConfig,
    sql: str,
    params: Optional[Mapping[str, Any]],
    source: str,
) -> list[dict[str, Any]]:
    """
    在 Direct 模式下执行只读查询。
    """
    if db_cfg.mode != "direct":
        raise ValueError("run_direct_query only supports direct mode databases")

    check_permission_for_read(db_cfg)
    ensure_readonly_sql(sql)

    engine = create_sqlalchemy_engine(db_cfg)
    with engine.connect() as conn:
        result = conn.execute(text(sql), params or {})
        rows = [dict(row) for row in result.mappings().all()]

    write_audit_log(
        app_config=app_config,
        db_cfg=db_cfg,
        sql=sql,
        params=params,
        rows_affected=None,
        source=source,
    )

    return rows


def run_direct_execute(
    app_config: AppConfig,
    db_cfg: DatabaseConfig,
    sql: str,
    params: Optional[Mapping[str, Any]],
    source: str,
) -> int:
    """
    在 Direct 模式下执行写操作，返回影响行数。
    """
    if db_cfg.mode != "direct":
        raise ValueError("run_direct_execute only supports direct mode databases")

    check_permission_for_write(db_cfg, sql)

    engine = create_sqlalchemy_engine(db_cfg)
    with engine.begin() as conn:
        result = conn.execute(text(sql), params or {})
        rowcount = int(result.rowcount or 0)

    write_audit_log(
        app_config=app_config,
        db_cfg=db_cfg,
        sql=sql,
        params=params,
        rows_affected=rowcount,
        source=source,
    )

    return rowcount


__all__ = [
    "AuditConfig",
    "DatabaseConfig",
    "AppConfig",
    "validate_database_config",
    "load_config",
    "get_database_config",
    "create_sqlalchemy_engine",
    "write_audit_log",
    "run_direct_query",
    "run_direct_execute",
]

