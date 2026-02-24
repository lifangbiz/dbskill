"""
API 侧对配置与数据库连接的封装。

复用 `dbskill.utils` 中的配置解析与 Engine 创建逻辑，避免重复实现。
"""

from __future__ import annotations

from functools import lru_cache
from typing import Optional

from sqlalchemy.engine import Engine

from dbskill.utils import (
    AppConfig,
    DatabaseConfig,
    create_sqlalchemy_engine,
    get_database_config,
    load_config,
)


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    """
    懒加载并缓存 AppConfig，供 API 各处复用。
    """
    return load_config()


def get_db_config(db_alias: Optional[str] = None) -> DatabaseConfig:
    """
    获取单个数据库配置。
    """
    return get_database_config(get_app_config(), db_alias=db_alias)


@lru_cache(maxsize=None)
def get_db_engine(db_alias: Optional[str] = None) -> Engine:
    """
    为指定别名创建（并缓存） SQLAlchemy Engine，仅适用于 Direct 模式关系型数据库。
    """
    db_cfg = get_db_config(db_alias)
    return create_sqlalchemy_engine(db_cfg)


__all__ = ["get_app_config", "get_db_config", "get_db_engine"]

