"""
通过 token 获取当前账号可用的数据库列表。
"""

from typing import Any, List

from fastapi import APIRouter, Depends

from api.auth import ApiKey, get_current_api_key
from api.services.backend_db import list_databases_for_api_key


router = APIRouter(prefix="/databases", tags=["databases"])


@router.get("")
def list_databases(api_key: ApiKey = Depends(get_current_api_key)) -> dict[str, Any]:
    """
    返回当前 token 对应账号被分配的所有数据库（别名与权限）。
    客户端未配置固定 database 时，agent 可先调用此接口再执行 schema/query/execute。
    """
    items = list_databases_for_api_key(api_key.key_id)
    return {"data": items}
