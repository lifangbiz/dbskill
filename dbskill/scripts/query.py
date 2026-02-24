"""
只读查询脚本（Direct / API 双模式的对外入口）。

当前实现 Direct 模式：
- 读取 config.yaml；
- 基于 db_alias/default_db 选择数据库；
- 校验权限与 SQL 类型（仅允许 SELECT/CTE）；
- 执行参数化查询；
- 写入本地审计日志（如启用）。

API 模式将在后续基于 HTTP 客户端接入。
"""

from typing import Any, Dict, List, Mapping, Optional

from dbskill.api_client import call_query as api_call_query
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


def run_query(
    sql: str,
    params: Optional[Mapping[str, Any]] = None,
    db_alias: Optional[str] = None,
    db_cfg: Optional[DatabaseConfig] = None,
    config_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    执行只读查询。

    :param sql: 参数化 SQL 模板（仅允许 SELECT/CTE），占位符使用 :name 形式
    :param params: 参数字典
    :param db_alias: 可选数据库别名，默认使用 default_db
    :param db_cfg: 可选；若传入（如 API 服务端从后台解析）则直接使用
    :param config_path: 可选；显式指定 config.yaml 路径，用于自动发现失败时
    """
    if db_cfg is not None:
        if db_cfg.mode != "direct":
            raise ValueError("injected db_cfg must be direct mode")
        app_cfg = AppConfig(databases={}, default_db=None, audit=AuditConfig(enabled=False))
    else:
        app_cfg = load_config(explicit_path=config_path)
        db_cfg = _resolve_db(app_cfg, db_alias)

    if db_cfg.mode == "direct":
        return run_direct_query(
            app_config=app_cfg,
            db_cfg=db_cfg,
            sql=sql,
            params=params,
            source="skill.query",
        )

    if db_cfg.mode == "api":
        if not db_cfg.api_url or not db_cfg.api_token:
            raise ValueError("API mode requires api_url and api_token in config")
        return api_call_query(
            api_url=db_cfg.api_url,
            api_token=db_cfg.api_token,
            sql=sql,
            params=params,
            db_alias=db_alias or db_cfg.alias,
        )

    raise ValueError(f"unsupported database mode: {db_cfg.mode}")


__all__ = ["run_query"]

