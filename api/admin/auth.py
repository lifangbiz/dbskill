"""管理后台登录鉴权。"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, Request
from fastapi.responses import RedirectResponse
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from api.services.models import AdminUser, SessionLocal, init_admin_db


class AdminLoginRequired(Exception):
    """未登录时由依赖抛出，由 exception_handler 转为 303 重定向。"""
    def __init__(self, url: str = "/admin/login"):
        self.url = url
        super().__init__(url)


# 使用 pbkdf2_sha256，无密码长度限制，passlib 内置无需 bcrypt 依赖
pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")


def _get_db():
    init_admin_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _ensure_default_admin(db: Session) -> None:
    """若不存在任何管理员，则创建默认 admin（密码来自环境变量 ADMIN_PASSWORD，默认 admin123）。"""
    if db.query(AdminUser).first():
        return
    password = os.environ.get("ADMIN_PASSWORD", "admin123")
    admin = AdminUser(
        username="admin",
        password_hash=pwd_context.hash(password),
    )
    db.add(admin)
    db.commit()


def verify_admin(username: str, password: str, db: Session) -> Optional[AdminUser]:
    admin = db.query(AdminUser).filter(AdminUser.username == username).first()
    if not admin:
        return None
    if not pwd_context.verify(password, admin.password_hash):
        return None
    return admin


def set_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def require_admin(request: Request) -> Optional[str]:
    """从 session 中获取已登录的 admin 用户名，未登录返回 None。"""
    return request.session.get("admin_username")


def get_admin_username(request: Request) -> str:
    """依赖：未登录则抛出 AdminLoginRequired，由 exception_handler 重定向到登录页。"""
    username = require_admin(request)
    if not username:
        raise AdminLoginRequired("/admin/login")
    return username
