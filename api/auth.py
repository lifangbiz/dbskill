"""
API Key 鉴权与权限模型。

从 admin.db 读取 ApiKey（直接带权限），Token 参与鉴权。
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status

from api.services.models import ApiKey as DbApiKey, init_admin_db, SessionLocal


@dataclass
class ApiKey:
    key: str
    key_id: int
    permission_level: str  # readonly | write | full
    name: Optional[str] = None  # 可选备注


def _lookup_api_key(token: str) -> Optional[ApiKey]:
    """从 admin.db 根据 token 查找 ApiKey。"""
    init_admin_db()
    key_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    db = SessionLocal()
    try:
        db_key = db.query(DbApiKey).filter(DbApiKey.key_hash == key_hash).first()
        if not db_key or not getattr(db_key, "enabled", True):
            return None
        return ApiKey(
            key=token,
            key_id=db_key.id,
            permission_level=db_key.permission_level,
            name=db_key.name,
        )
    finally:
        db.close()


def _get_api_key(authorization: Optional[str]) -> ApiKey:
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing Authorization header")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Authorization header")
    token = authorization[len("Bearer ") :].strip()
    api_key = _lookup_api_key(token)
    if not api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API token")
    return api_key


def get_current_api_key(authorization: Optional[str] = Header(default=None)) -> ApiKey:
    return _get_api_key(authorization)


def require_permission(required: str):
    """
    返回一个依赖，用于检查 API Key 权限：
    - readonly 只允许 schema/query；
    - write 允许 schema/query + INSERT/UPDATE；
    - full 允许所有（含 DELETE）。
    """
    levels = ("readonly", "write", "full")
    if required not in levels:
        raise ValueError(f"invalid required permission: {required}")

    def dependency(api_key: ApiKey = Depends(get_current_api_key)) -> ApiKey:
        current_idx = levels.index(api_key.permission_level)
        required_idx = levels.index(required)
        if current_idx < required_idx:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Permission denied")
        return api_key

    return dependency


__all__ = ["ApiKey", "get_current_api_key", "require_permission"]
