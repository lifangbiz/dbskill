"""
管理后台所用的数据库模型（API Key 直接绑定权限与数据库，无 Account）。

- 使用独立 SQLite 文件，路径优先级：环境变量 ADMIN_DB_PATH > server.yaml 的 admin_db.path > 默认 ./admin.db；
- Database：后台维护的库连接，可被多个 API Key 分配；
- ApiKey：直接拥有 permission_level、db_config_ref、以及分配的 databases。
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text, create_engine, text
from sqlalchemy.orm import declarative_base, relationship, sessionmaker


def _get_admin_db_path() -> Path:
    """admin.db 路径：环境变量 ADMIN_DB_PATH > server.yaml admin_db.path > 默认项目根/admin.db。"""
    if os.environ.get("ADMIN_DB_PATH"):
        return Path(os.environ["ADMIN_DB_PATH"]).resolve()
    base = Path(__file__).resolve().parents[2]
    server_path = base / "server.yaml"
    if server_path.is_file():
        import yaml
        with server_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        path_val = (raw.get("admin_db") or {}).get("path")
        if path_val:
            p = Path(path_val)
            if not p.is_absolute():
                p = (base / p).resolve()
            return p
    return base / "admin.db"


BASE_DIR = Path(__file__).resolve().parents[2]
ADMIN_DB_PATH = _get_admin_db_path()

DATABASE_URL = f"sqlite:///{ADMIN_DB_PATH}"

engine = create_engine(DATABASE_URL, future=True)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

Base = declarative_base()


class Database(Base):
    """API 模式：后台添加的数据库连接配置，可分配给多个 API Key。"""

    __tablename__ = "databases"

    id = Column(Integer, primary_key=True, index=True)
    alias = Column(String(100), unique=True, nullable=False, index=True)
    type = Column(String(32), nullable=False)  # postgres | mysql | mariadb | sqlite | oracle | mssql | db2 | dm | kingbase
    host = Column(String(256), nullable=True)
    port = Column(Integer, nullable=True)
    user = Column(String(256), nullable=True)
    password = Column(String(256), nullable=True)
    database = Column(String(256), nullable=True)  # 库名或 sqlite 文件路径
    permission_level = Column(String(16), nullable=False, default="readonly")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    key_assignments = relationship(
        "ApiKeyDatabase",
        back_populates="database",
        cascade="all, delete-orphan",
    )


class ApiKeyDatabase(Base):
    """API Key 与数据库的关联，每个关联有独立权限。"""

    __tablename__ = "api_key_databases"

    api_key_id = Column(Integer, ForeignKey("api_keys.id"), primary_key=True)
    database_id = Column(Integer, ForeignKey("databases.id"), primary_key=True)
    permission_level = Column(String(16), nullable=False, default="readonly")

    api_key = relationship("ApiKey", back_populates="assignments")
    database = relationship("Database", back_populates="key_assignments")


class ApiKey(Base):
    """API Key：可访问数据库列表由 assignments 决定，每库单独权限。只存 raw_key，prefix 由 raw_key 派生。"""

    __tablename__ = "api_keys"

    id = Column(Integer, primary_key=True, index=True)
    key_hash = Column(String(128), nullable=False)
    raw_key = Column(String(80), nullable=False)  # 完整 key
    permission_level = Column(String(16), nullable=False, default="readonly")
    db_config_ref = Column(String(100), nullable=True)  # 可选默认库别名
    name = Column(String(100), nullable=True)  # 可选备注，便于管理
    enabled = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    assignments = relationship(
        "ApiKeyDatabase",
        back_populates="api_key",
        cascade="all, delete-orphan",
    )

    @property
    def prefix(self) -> str:
        """由 raw_key 前 8 位派生，用于展示。"""
        return (self.raw_key or "")[:8]


class AdminUser(Base):
    """管理后台管理员账号，用于登录。"""

    __tablename__ = "admin_users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class ApiAuditLog(Base):
    """Web API 审计日志（/query、/execute 等请求），仅存数据库。"""

    __tablename__ = "api_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    ts = Column(DateTime(timezone=True), nullable=False, index=True)
    trace_id = Column(String(64), nullable=False)
    path = Column(String(512), nullable=False)
    method = Column(String(16), nullable=True)
    client_ip = Column(String(64), nullable=True)
    api_key_name = Column(String(100), nullable=True)
    permission_level = Column(String(16), nullable=True)
    db_alias = Column(String(100), nullable=True)
    sql = Column(Text, nullable=True)
    params = Column(Text, nullable=True)  # JSON 字符串


def _ensure_column(conn, table: str, column: str, col_def: str) -> None:
    r = conn.execute(text(f"SELECT 1 FROM pragma_table_info({repr(table)}) WHERE name = {repr(column)}"))
    if r.fetchone() is None:
        conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
        conn.commit()


def _migrate_api_keys_drop_prefix(conn) -> None:
    """移除 prefix 列，只保留 raw_key。无 raw_key 的旧数据不迁移。"""
    r = conn.execute(text("SELECT 1 FROM pragma_table_info('api_keys') WHERE name = 'prefix'"))
    if r.fetchone() is None:
        return
    conn.execute(text("""
        CREATE TABLE api_keys_new (
            id INTEGER NOT NULL PRIMARY KEY,
            key_hash VARCHAR(128) NOT NULL,
            raw_key VARCHAR(80) NOT NULL,
            permission_level VARCHAR(16) NOT NULL DEFAULT 'readonly',
            db_config_ref VARCHAR(100),
            name VARCHAR(100),
            created_at DATETIME
        )
    """))
    conn.execute(text("""
        INSERT INTO api_keys_new (id, key_hash, raw_key, permission_level, db_config_ref, name, created_at)
        SELECT id, key_hash, raw_key, permission_level, db_config_ref, name, created_at
        FROM api_keys
        WHERE raw_key IS NOT NULL AND raw_key != ''
    """))
    conn.execute(text("DELETE FROM api_key_databases WHERE api_key_id NOT IN (SELECT id FROM api_keys_new)"))
    conn.execute(text("DROP TABLE api_keys"))
    conn.execute(text("ALTER TABLE api_keys_new RENAME TO api_keys"))
    conn.commit()


def _migrate_api_keys_drop_account_id(conn) -> None:
    """若 api_keys 存在 account_id 列则用建新表方式移除（避免 FK 导致 DROP COLUMN 失败）。"""
    r = conn.execute(text("SELECT 1 FROM pragma_table_info('api_keys') WHERE name = 'account_id'"))
    if r.fetchone() is None:
        return
    conn.execute(text("""
        CREATE TABLE api_keys_new (
            id INTEGER NOT NULL PRIMARY KEY,
            key_hash VARCHAR(128) NOT NULL,
            prefix VARCHAR(16) NOT NULL,
            permission_level VARCHAR(16) NOT NULL DEFAULT 'readonly',
            db_config_ref VARCHAR(100),
            name VARCHAR(100),
            created_at DATETIME
        )
    """))
    conn.execute(text("""
        INSERT INTO api_keys_new (id, key_hash, prefix, permission_level, db_config_ref, name, created_at)
        SELECT id, key_hash, prefix, COALESCE(permission_level, 'readonly'), db_config_ref, name, created_at
        FROM api_keys
    """))
    conn.execute(text("DROP TABLE api_keys"))
    conn.execute(text("ALTER TABLE api_keys_new RENAME TO api_keys"))
    conn.commit()


def init_admin_db() -> None:
    """创建管理后台所需的表。"""
    Base.metadata.create_all(bind=engine)
    with engine.connect() as conn:
        _ensure_column(conn, "api_keys", "permission_level", "VARCHAR(16) NOT NULL DEFAULT 'readonly'")
        _ensure_column(conn, "api_keys", "db_config_ref", "VARCHAR(100)")
        _ensure_column(conn, "api_keys", "raw_key", "VARCHAR(80)")
        _ensure_column(conn, "api_keys", "name", "VARCHAR(100)")
        _ensure_column(conn, "api_keys", "enabled", "BOOLEAN NOT NULL DEFAULT 1")
        _migrate_api_keys_drop_account_id(conn)
        _migrate_api_keys_drop_prefix(conn)
        _ensure_column(conn, "api_key_databases", "permission_level", "VARCHAR(16) NOT NULL DEFAULT 'readonly'")


__all__ = ["ApiKey", "ApiKeyDatabase", "AdminUser", "ApiAuditLog", "Database", "SessionLocal", "init_admin_db"]
