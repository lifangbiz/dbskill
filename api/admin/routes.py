from __future__ import annotations

import hashlib
import secrets
from typing import List, Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import text

from api.admin.auth import (
    _ensure_default_admin,
    get_admin_username,
    require_admin,
    set_password_hash,
    verify_admin,
)
from api.services.audit import list_audit_logs
from api.services.models import ADMIN_DB_PATH, ApiKey, ApiKeyDatabase, AdminUser, Database, SessionLocal, init_admin_db
from dbskill.constants import DEFAULT_PORTS, SUPPORTED_DB_TYPES
from dbskill.utils import DatabaseConfig, create_sqlalchemy_engine


router = APIRouter(prefix="/admin", tags=["admin"])

templates = Jinja2Templates(directory=str(__file__).replace("routes.py", "templates"))


def get_db():
    init_admin_db()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class ApiKeyOut(BaseModel):
    prefix: str
    name: Optional[str]
    permission_level: str


@router.get("/api-keys", response_model=List[ApiKeyOut])
def list_api_keys(db=Depends(get_db)):
    keys = db.query(ApiKey).all()
    return [
        ApiKeyOut(prefix=k.prefix, name=k.name, permission_level=k.permission_level)
        for k in keys
    ]


# ---- 管理后台 UI（中英双语） ----

I18N = {
    "en": {
        "title": "DBSkill Admin",
        "databases": "Databases",
        "accounts": "Accounts",
        "api_keys": "API Keys",
        "name": "Name",
        "permission": "Permission",
        "db_ref": "Default DB Alias",
        "assign_dbs": "Assign Databases",
        "alias": "Alias",
        "type": "Type",
        "host": "Host",
        "port": "Port",
        "user": "User",
        "password": "Password",
        "database": "Database",
        "create": "Create",
        "new_database": "New Database",
        "edit_database": "Edit Database",
        "new_account": "New Account",
        "new_api_key": "New API Key",
        "account_name": "Account Name",
        "prefix": "Prefix",
        "key": "Key",
        "key_name": "Key Name",
        "key_name_optional": "Optional",
        "permission_level": "Permission",
        "db_config_ref": "DB Config Ref",
        "db_config_ref_optional": "Optional",
        "assigned_databases": "Assigned Databases",
        "bound_keys": "Bound API Keys",
        "manage_databases": "Manage DBs",
        "assign_database": "Assign Database",
        "bind_database": "Bind Database",
        "unbind": "Unbind",
        "back_to_api_keys": "Back to API Keys",
        "back_to_databases": "Back to Databases",
        "generated_key": "Generated API Key",
        "edit": "Edit",
        "delete": "Delete",
        "revoke": "Revoke",
        "edit_account": "Edit Account",
        "save": "Save",
        "cancel": "Cancel",
        "login": "Login",
        "logout": "Logout",
        "username": "Username",
        "password": "Password",
        "change_password": "Change Password",
        "new_password": "New Password",
        "old_password": "Current Password",
        "password_changed": "Password changed successfully",
        "invalid_credentials": "Invalid username or password",
        "dashboard": "Dashboard",
        "prev_page": "Previous",
        "next_page": "Next",
        "page_x_of_y": "Page {page} of {total}",
        "click_to_toggle": "Click to toggle show/hide",
        "edit_key": "Edit",
        "regenerate_key": "Regenerate Key",
        "disable": "Disable",
        "enable": "Enable",
        "enabled": "Enabled",
        "disabled": "Disabled",
        "bind_selected": "Bind Selected",
        "status": "Status",
        "detail": "Detail",
        "all_databases_assigned": "All databases are already assigned.",
        "test_connection": "Test Connection",
        "connection_ok": "Connection successful",
        "connection_failed": "Connection failed",
        "audit_logs": "Audit Logs",
        "filter_by_database": "Database",
        "filter_by_api_key": "API Key",
        "filter_by_date": "Log date",
        "date_from": "From",
        "date_to": "To",
        "filter_apply": "Apply",
        "audit_time": "Time",
        "trace_id": "Trace ID",
        "path": "Path",
        "method": "Method",
        "client_ip": "Client IP",
        "sql_preview": "SQL",
        "no_audit_logs": "No audit logs.",
        "unnamed_keys": "Unnamed",
        "overview": "Overview",
        "data_source": "Data source",
        "total_entries": "Total: {n} entries",
        "password_leave_blank": "Leave blank to keep unchanged",
        "database_placeholder": "DB name or SQLite path",
        "default_db_alias_placeholder": "Optional default DB alias",
        "db_type_dm": "DM (达梦)",
        "db_type_kingbase": "KingbaseES (人大金仓)",
    },
    "zh": {
        "title": "DBSkill 管理后台",
        "databases": "数据库列表",
        "accounts": "账号列表",
        "api_keys": "API Key 列表",
        "name": "名称",
        "permission": "权限",
        "db_ref": "默认库别名",
        "assign_dbs": "分配数据库",
        "alias": "别名",
        "type": "类型",
        "host": "主机",
        "port": "端口",
        "user": "用户",
        "password": "密码",
        "database": "数据库",
        "create": "创建",
        "new_database": "新建数据库",
        "edit_database": "编辑数据库",
        "new_account": "新建账号",
        "new_api_key": "新建 API Key",
        "account_name": "账号名称",
        "prefix": "前缀",
        "key": "密钥",
        "key_name": "备注名",
        "key_name_optional": "选填",
        "permission_level": "权限",
        "db_config_ref": "DB 配置引用",
        "db_config_ref_optional": "选填",
        "assigned_databases": "分配数据库",
        "bound_keys": "绑定的 Key",
        "manage_databases": "管理库",
        "assign_database": "分配数据库",
        "bind_database": "绑定数据库",
        "unbind": "解绑",
        "back_to_api_keys": "返回 API Key 列表",
        "back_to_databases": "返回数据库列表",
        "generated_key": "生成的 API Key",
        "edit": "编辑",
        "delete": "删除",
        "revoke": "撤销",
        "edit_account": "编辑账号",
        "save": "保存",
        "cancel": "取消",
        "login": "登录",
        "logout": "退出",
        "username": "用户名",
        "password": "密码",
        "change_password": "修改密码",
        "new_password": "新密码",
        "old_password": "当前密码",
        "password_changed": "密码修改成功",
        "invalid_credentials": "用户名或密码错误",
        "dashboard": "控制台",
        "prev_page": "上一页",
        "next_page": "下一页",
        "page_x_of_y": "第 {page} 页，共 {total} 页",
        "click_to_toggle": "点击切换显示/隐藏",
        "edit_key": "编辑",
        "regenerate_key": "重新生成 Key",
        "disable": "禁用",
        "enable": "启用",
        "enabled": "已启用",
        "disabled": "已禁用",
        "bind_selected": "绑定所选",
        "status": "状态",
        "detail": "详情",
        "all_databases_assigned": "所有数据库已分配。",
        "test_connection": "测试连接",
        "connection_ok": "连接成功",
        "connection_failed": "连接失败",
        "audit_logs": "审计日志",
        "filter_by_database": "数据库",
        "filter_by_api_key": "API Key",
        "filter_by_date": "日志日期",
        "date_from": "起",
        "date_to": "止",
        "filter_apply": "筛选",
        "audit_time": "时间",
        "trace_id": "Trace ID",
        "path": "路径",
        "method": "方法",
        "client_ip": "客户端 IP",
        "sql_preview": "SQL",
        "no_audit_logs": "暂无审计日志。",
        "unnamed_keys": "未命名",
        "overview": "概览",
        "data_source": "数据源",
        "total_entries": "共 {n} 条",
        "password_leave_blank": "留空则不修改",
        "database_placeholder": "库名或 sqlite 路径",
        "default_db_alias_placeholder": "可选默认库别名",
        "db_type_dm": "达梦 DM",
        "db_type_kingbase": "人大金仓 KingbaseES",
    },
}


def _get_lang(request: Request) -> str:
    lang = request.query_params.get("lang", "en")
    return lang if lang in I18N else "en"


# ---- 登录 / 登出 / 修改密码 ----

@router.get("/login", response_class=HTMLResponse)
def admin_login_page(request: Request, db=Depends(get_db)):
    _ensure_default_admin(db)
    if require_admin(request):
        return RedirectResponse(url="/admin/ui", status_code=303)
    lang = _get_lang(request)
    return templates.TemplateResponse("admin_login.html", {"request": request, "t": I18N[lang], "lang": lang})


@router.post("/login", response_class=HTMLResponse)
def admin_login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db=Depends(get_db),
):
    admin = verify_admin(username, password, db)
    if not admin:
        lang = _get_lang(request)
        return templates.TemplateResponse(
            "admin_login.html",
            {"request": request, "t": I18N[lang], "lang": lang, "error": I18N[lang]["invalid_credentials"]},
            status_code=401,
        )
    request.session["admin_username"] = admin.username
    return RedirectResponse(url="/admin/ui", status_code=303)


@router.post("/logout", response_class=HTMLResponse)
def admin_logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/admin/login", status_code=303)


@router.get("/ui/change-password", response_class=HTMLResponse)
def admin_change_password_form(
    request: Request,
    _: str = Depends(get_admin_username),
    db=Depends(get_db),
):
    lang = _get_lang(request)
    return templates.TemplateResponse(
        "admin_change_password.html",
        {"request": request, "t": I18N[lang], "lang": lang, "active_section": "dashboard"},
    )


@router.post("/ui/change-password", response_class=HTMLResponse)
def admin_change_password_submit(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...),
    admin_username: str = Depends(get_admin_username),
    db=Depends(get_db),
):
    admin = db.query(AdminUser).filter(AdminUser.username == admin_username).first()
    if not admin or not verify_admin(admin_username, old_password, db):
        lang = _get_lang(request)
        return templates.TemplateResponse(
            "admin_change_password.html",
            {"request": request, "t": I18N[lang], "lang": lang, "active_section": "dashboard", "error": I18N[lang]["invalid_credentials"]},
            status_code=400,
        )
    admin.password_hash = set_password_hash(new_password)
    db.commit()
    lang = _get_lang(request)
    return templates.TemplateResponse(
        "admin_change_password.html",
        {"request": request, "t": I18N[lang], "lang": lang, "active_section": "dashboard", "success": I18N[lang]["password_changed"]},
    )


@router.get("/ui", response_class=HTMLResponse)
def admin_ui_dashboard(request: Request, db=Depends(get_db), _: str = Depends(get_admin_username)):
    lang = _get_lang(request)
    databases = db.query(Database).all()
    keys = db.query(ApiKey).all()
    return templates.TemplateResponse(
        "admin_dashboard.html",
        {
            "request": request,
            "t": I18N[lang],
            "lang": lang,
            "active_section": "dashboard",
            "databases_count": len(databases),
            "api_keys_count": len(keys),
        },
    )


@router.get("/ui/databases", response_class=HTMLResponse)
def admin_ui_databases(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    lang = _get_lang(request)
    total = db.query(Database).count()
    offset = (page - 1) * per_page
    databases = db.query(Database).order_by(Database.id.desc()).offset(offset).limit(per_page).all()
    for d in databases:
        _ = list(d.key_assignments)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    return templates.TemplateResponse(
        "admin_databases.html",
        {
            "request": request,
            "t": I18N[lang],
            "lang": lang,
            "active_section": "databases",
            "databases": databases,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/ui/audit-logs", response_class=HTMLResponse)
def admin_ui_audit_logs(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db_alias: Optional[str] = Query(None),
    api_key: Optional[str] = Query(None, alias="api_key"),
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    lang = _get_lang(request)
    entries_page, total = list_audit_logs(
        db_session=db,
        db_alias=db_alias,
        api_key_name=api_key,
        date_from=date_from,
        date_to=date_to,
        page=page,
        per_page=per_page,
    )
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    databases = db.query(Database).order_by(Database.alias).all()
    api_keys = db.query(ApiKey).order_by(ApiKey.id).all()
    return templates.TemplateResponse(
        "admin_audit_logs.html",
        {
            "request": request,
            "t": I18N[lang],
            "lang": lang,
            "active_section": "audit_logs",
            "entries": entries_page,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
            "filter_db_alias": db_alias or "",
            "filter_api_key": api_key or "",
            "filter_date_from": date_from or "",
            "filter_date_to": date_to or "",
            "databases": databases,
            "api_keys": api_keys,
            "admin_db_path": str(ADMIN_DB_PATH),
        },
    )


@router.get("/ui/databases/new", response_class=HTMLResponse)
def admin_ui_new_database_form(request: Request, db=Depends(get_db), _: str = Depends(get_admin_username)):
    lang = _get_lang(request)
    return templates.TemplateResponse(
        "admin_database_new.html",
        {"request": request, "t": I18N[lang], "lang": lang, "active_section": "databases"},
    )


class TestConnectionBody(BaseModel):
    type: str = "postgres"
    host: Optional[str] = None
    port: Optional[int] = None
    user: Optional[str] = None
    password: Optional[str] = None
    database: Optional[str] = None


@router.post("/api/databases/{database_id}/test-connection")
def admin_api_test_database_connection_by_id(
    database_id: int,
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    """Test database connection using stored config. Returns { \"ok\": true } or { \"ok\": false, \"error\": \"...\" }."""
    database = db.query(Database).filter(Database.id == database_id).first()
    if not database:
        return {"ok": False, "error": "Database not found"}
    db_type = (database.type or "").strip().lower()
    if db_type not in SUPPORTED_DB_TYPES:
        return {"ok": False, "error": f"Unsupported type: {database.type}"}
    if db_type == "sqlite":
        if not (database.database or "").strip():
            return {"ok": False, "error": "Database path is required for SQLite"}
        cfg = DatabaseConfig(
            alias="test",
            type="sqlite",
            mode="direct",
            host=None,
            port=None,
            user=None,
            password=None,
            database=(database.database or "").strip(),
        )
    else:
        host = (database.host or "").strip() or "localhost"
        port = database.port if database.port is not None else DEFAULT_PORTS.get(db_type, 5432)
        user = (database.user or "").strip()
        password = database.password or ""
        database_name = (database.database or "").strip()
        if db_type != "dm" and not database_name:
            return {"ok": False, "error": "Database name is required"}
        cfg = DatabaseConfig(
            alias="test",
            type=db_type,
            mode="direct",
            host=host,
            port=port,
            user=user,
            password=password,
            database=database_name or None,
        )
    try:
        engine = create_sqlalchemy_engine(cfg)
        probe_sql = "SELECT 1 FROM DUAL" if db_type in ("oracle", "dm") else "SELECT 1"
        with engine.connect() as conn:
            conn.execute(text(probe_sql))
        engine.dispose()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.post("/api/databases/test-connection")
def admin_api_test_database_connection(
    body: TestConnectionBody,
    _: str = Depends(get_admin_username),
):
    """Test database connection without saving. Returns { \"ok\": true } or { \"ok\": false, \"error\": \"...\" }."""
    db_type = (body.type or "").strip().lower()
    if db_type not in SUPPORTED_DB_TYPES:
        return {"ok": False, "error": f"Unsupported type: {body.type}"}
    if db_type == "sqlite":
        if not (body.database or "").strip():
            return {"ok": False, "error": "Database path is required for SQLite"}
        cfg = DatabaseConfig(
            alias="test",
            type="sqlite",
            mode="direct",
            host=None,
            port=None,
            user=None,
            password=None,
            database=(body.database or "").strip(),
        )
    else:
        host = (body.host or "").strip() or "localhost"
        port = body.port if body.port is not None else DEFAULT_PORTS.get(db_type, 5432)
        user = (body.user or "").strip()
        password = body.password or ""
        database = (body.database or "").strip()
        if db_type != "dm" and not database:
            return {"ok": False, "error": "Database name is required"}
        cfg = DatabaseConfig(
            alias="test",
            type=db_type,
            mode="direct",
            host=host,
            port=port,
            user=user,
            password=password,
            database=database or None,
        )
    try:
        engine = create_sqlalchemy_engine(cfg)
        probe_sql = "SELECT 1 FROM DUAL" if db_type in ("oracle", "dm") else "SELECT 1"
        with engine.connect() as conn:
            conn.execute(text(probe_sql))
        engine.dispose()
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@router.get("/ui/api-keys", response_class=HTMLResponse)
def admin_ui_api_keys(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    lang = _get_lang(request)
    total = db.query(ApiKey).count()
    offset = (page - 1) * per_page
    keys = db.query(ApiKey).order_by(ApiKey.id.desc()).offset(offset).limit(per_page).all()
    for k in keys:
        _ = list(k.assignments)
    total_pages = (total + per_page - 1) // per_page if total > 0 else 1
    return templates.TemplateResponse(
        "admin_api_keys.html",
        {
            "request": request,
            "t": I18N[lang],
            "lang": lang,
            "active_section": "api_keys",
            "api_keys": keys,
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": total_pages,
        },
    )


@router.get("/ui/api-keys/new", response_class=HTMLResponse)
def admin_ui_new_api_key_form(request: Request, db=Depends(get_db), _: str = Depends(get_admin_username)):
    lang = _get_lang(request)
    return templates.TemplateResponse(
        "admin_api_key_new.html",
        {"request": request, "t": I18N[lang], "lang": lang, "active_section": "api_keys"},
    )


@router.post("/ui/api-keys", response_class=HTMLResponse)
def admin_ui_create_api_key(
    request: Request,
    name: str = Form(...),
    lang: Optional[str] = Form(None),
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    raw_key = "sk_" + secrets.token_urlsafe(24)
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    api_key = ApiKey(
        key_hash=key_hash,
        raw_key=raw_key,
        permission_level="readonly",
        name=name.strip(),
    )
    db.add(api_key)
    db.commit()
    qs = f"generated_key={raw_key}"
    if lang and lang in I18N:
        qs += f"&lang={lang}"
    return RedirectResponse(url=f"/admin/ui/api-keys?{qs}", status_code=303)


@router.get("/ui/api-keys/{key_id}", response_class=HTMLResponse)
def admin_ui_api_key_detail(
    key_id: int,
    request: Request,
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        return RedirectResponse(url="/admin/ui/api-keys", status_code=303)
    _ = list(api_key.assignments)
    bound_ids = {a.database_id for a in api_key.assignments}
    all_dbs = db.query(Database).all()
    unbound_databases = [d for d in all_dbs if d.id not in bound_ids]
    lang = _get_lang(request)
    return templates.TemplateResponse(
        "admin_api_key_detail.html",
        {
            "request": request,
            "t": I18N[lang],
            "lang": lang,
            "active_section": "api_keys",
            "api_key": api_key,
            "unbound_databases": unbound_databases,
        },
    )


@router.get("/ui/api-keys/{key_id}/edit", response_class=HTMLResponse)
def admin_ui_edit_api_key(
    key_id: int,
    request: Request,
    _: str = Depends(get_admin_username),
):
    lang = _get_lang(request)
    return RedirectResponse(url=f"/admin/ui/api-keys/{key_id}?lang={lang}", status_code=302)


@router.get("/ui/api-keys/{key_id}/databases", response_class=HTMLResponse)
def admin_ui_api_key_databases_redirect(
    key_id: int,
    request: Request,
    _: str = Depends(get_admin_username),
):
    lang = _get_lang(request)
    return RedirectResponse(url=f"/admin/ui/api-keys/{key_id}?lang={lang}", status_code=302)


@router.post("/ui/api-keys/{key_id}/update", response_class=HTMLResponse)
def admin_ui_update_api_key(
    key_id: int,
    request: Request,
    name: str = Form(""),
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        return RedirectResponse(url="/admin/ui/api-keys", status_code=303)
    api_key.name = name.strip() or None
    db.commit()
    lang = _get_lang(request)
    return RedirectResponse(url=f"/admin/ui/api-keys/{key_id}?lang={lang}", status_code=303)


@router.post("/ui/api-keys/{key_id}/regenerate", response_class=HTMLResponse)
def admin_ui_regenerate_api_key(
    key_id: int,
    request: Request,
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        return RedirectResponse(url="/admin/ui/api-keys", status_code=303)
    raw_key = "sk_" + secrets.token_urlsafe(24)
    api_key.key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    api_key.raw_key = raw_key
    db.commit()
    lang = _get_lang(request)
    qs = f"generated_key={raw_key}&lang={lang}" if lang else f"generated_key={raw_key}"
    return RedirectResponse(url=f"/admin/ui/api-keys/{key_id}?{qs}", status_code=303)


@router.post("/ui/api-keys/{key_id}/toggle-enabled", response_class=HTMLResponse)
def admin_ui_toggle_api_key_enabled(
    key_id: int,
    request: Request,
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        return RedirectResponse(url="/admin/ui/api-keys", status_code=303)
    api_key.enabled = not api_key.enabled
    db.commit()
    lang = _get_lang(request)
    return RedirectResponse(url=f"/admin/ui/api-keys/{key_id}?lang={lang}", status_code=303)


@router.post("/ui/api-keys/{key_id}/delete", response_class=HTMLResponse)
def admin_ui_revoke_api_key(
    key_id: int,
    request: Request,
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if api_key:
        db.delete(api_key)
        db.commit()
    lang = _get_lang(request)
    return RedirectResponse(url=f"/admin/ui/api-keys?lang={lang}", status_code=303)


@router.post("/ui/api-keys/{key_id}/databases", response_class=HTMLResponse)
def admin_ui_api_key_bind_database(
    key_id: int,
    request: Request,
    permission_level: str = Form("readonly"),
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        return RedirectResponse(url="/admin/ui/api-keys", status_code=303)
    try:
        raw_ids = request.form.getlist("database_id")
    except Exception:
        raw_ids = []
    database_ids = []
    for x in raw_ids:
        try:
            database_ids.append(int(x))
        except (TypeError, ValueError):
            pass
    bound_ids = {a.database_id for a in api_key.assignments}
    for database_id in database_ids:
        if database_id in bound_ids:
            continue
        database = db.query(Database).filter(Database.id == database_id).first()
        if database:
            db.add(ApiKeyDatabase(api_key_id=key_id, database_id=database_id, permission_level=permission_level))
            bound_ids.add(database_id)
    db.commit()
    lang = _get_lang(request)
    return RedirectResponse(url=f"/admin/ui/api-keys/{key_id}?lang={lang}", status_code=303)


@router.post("/ui/api-keys/{key_id}/databases/unbind", response_class=HTMLResponse)
def admin_ui_api_key_unbind_database(
    key_id: int,
    request: Request,
    database_id: int = Form(...),
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    assignment = db.query(ApiKeyDatabase).filter(
        ApiKeyDatabase.api_key_id == key_id,
        ApiKeyDatabase.database_id == database_id,
    ).first()
    if assignment:
        db.delete(assignment)
        db.commit()
    lang = _get_lang(request)
    return RedirectResponse(url=f"/admin/ui/api-keys/{key_id}?lang={lang}", status_code=303)


# ---- 数据库 CRUD（API 模式：后台维护连接信息并分配给账号） ----

def _parse_port(v: Optional[str]) -> Optional[int]:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return int(v)
    except ValueError:
        return None


@router.post("/ui/databases", response_class=HTMLResponse)
def admin_ui_create_database(
    request: Request,
    alias: str = Form(...),
    type: str = Form("postgres"),
    host: Optional[str] = Form(None),
    port: Optional[str] = Form(None),
    user: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    database: Optional[str] = Form(None),
    lang: Optional[str] = Form(None),
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    d = Database(
        alias=alias.strip(),
        type=type.strip(),
        host=host.strip() if host else None,
        port=_parse_port(port),
        user=user.strip() if user else None,
        password=password if password else None,
        database=database.strip() if database else None,
        permission_level="readonly",
    )
    db.add(d)
    db.commit()
    url = "/admin/ui/databases"
    if lang and lang in I18N:
        url += f"?lang={lang}"
    return RedirectResponse(url=url, status_code=303)


@router.get("/ui/databases/{database_id}", response_class=HTMLResponse)
def admin_ui_database_detail(
    database_id: int,
    request: Request,
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    database = db.query(Database).filter(Database.id == database_id).first()
    if not database:
        return RedirectResponse(url="/admin/ui/databases", status_code=303)
    _ = list(database.key_assignments)
    lang = _get_lang(request)
    return templates.TemplateResponse(
        "admin_database_detail.html",
        {"request": request, "t": I18N[lang], "lang": lang, "active_section": "databases", "database": database},
    )


@router.get("/ui/databases/{database_id}/edit", response_class=HTMLResponse)
def admin_ui_edit_database_form(
    database_id: int,
    request: Request,
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    database = db.query(Database).filter(Database.id == database_id).first()
    if not database:
        return RedirectResponse(url="/admin/ui/databases", status_code=303)
    lang = _get_lang(request)
    return templates.TemplateResponse(
        "admin_database_edit.html",
        {"request": request, "t": I18N[lang], "lang": lang, "active_section": "databases", "database": database},
    )


@router.post("/ui/databases/{database_id}/edit", response_class=HTMLResponse)
def admin_ui_update_database(
    database_id: int,
    alias: str = Form(...),
    type: str = Form("postgres"),
    host: Optional[str] = Form(None),
    port: Optional[str] = Form(None),
    user: Optional[str] = Form(None),
    password: Optional[str] = Form(None),
    database: Optional[str] = Form(None),
    permission_level: str = Form("readonly"),
    lang: Optional[str] = Form(None),
    db=Depends(get_db),
    _: str = Depends(get_admin_username),
):
    d = db.query(Database).filter(Database.id == database_id).first()
    if not d:
        return RedirectResponse(url="/admin/ui/databases", status_code=303)
    d.alias = alias.strip()
    d.type = type.strip()
    d.host = host.strip() if host else None
    d.port = _parse_port(port)
    d.user = user.strip() if user else None
    if password:
        d.password = password
    d.database = database.strip() if database else None
    d.permission_level = permission_level
    db.commit()
    redirect_lang = (lang and lang in I18N) and lang or "en"
    return RedirectResponse(url=f"/admin/ui/databases/{database_id}?lang={redirect_lang}", status_code=303)


@router.post("/ui/databases/{database_id}/delete", response_class=HTMLResponse)
def admin_ui_delete_database(database_id: int, db=Depends(get_db), _: str = Depends(get_admin_username)):
    d = db.query(Database).filter(Database.id == database_id).first()
    if d:
        db.delete(d)
        db.commit()
    return RedirectResponse(url="/admin/ui/databases", status_code=303)

