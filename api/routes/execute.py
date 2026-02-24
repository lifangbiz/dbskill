from typing import Any, Dict, Mapping, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from api.auth import ApiKey, require_permission
from api.services.audit import write_api_audit_log
from api.services.backend_db import get_db_config_for_api
from dbskill.scripts.execute import run_execute as skill_run_execute


class ExecuteRequest(BaseModel):
    sql: str
    params: Optional[Mapping[str, Any]] = None
    db_alias: Optional[str] = None


def _sql_is_delete(sql: str) -> bool:
    prefix = sql.strip().split(None, 1)[0].lower() if sql.strip() else ""
    return prefix.startswith("delete")


router = APIRouter(prefix="/execute", tags=["execute"])


@router.post("", dependencies=[Depends(require_permission("write"))])
async def execute_endpoint(
    request: Request,
    payload: ExecuteRequest,
    api_key: ApiKey = Depends(require_permission("write")),
) -> Dict[str, Any]:
    """
    写操作接口，内部调用 Skill 的 run_execute。库由后台分配。
    DELETE 仅 full 权限允许。
    """
    if _sql_is_delete(payload.sql) and api_key.permission_level != "full":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="DELETE requires full permission")

    try:
        db_cfg = get_db_config_for_api(api_key.key_id, payload.db_alias)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    trace_id = uuid.uuid4().hex

    try:
        affected = skill_run_execute(
            sql=payload.sql,
            params=payload.params,
            db_cfg=db_cfg,
        )
        write_api_audit_log(
            request=request,
            api_key=api_key,
            sql=payload.sql,
            params=payload.params,
            db_alias=db_cfg.alias,
            trace_id=trace_id,
        )
        return {"data": {"rows_affected": affected}, "trace_id": trace_id}
    except PermissionError as e:
        write_api_audit_log(
            request=request,
            api_key=api_key,
            sql=payload.sql,
            params=payload.params,
            db_alias=db_cfg.alias,
            trace_id=trace_id,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        write_api_audit_log(
            request=request,
            api_key=api_key,
            sql=payload.sql,
            params=payload.params,
            db_alias=db_cfg.alias,
            trace_id=trace_id,
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        write_api_audit_log(
            request=request,
            api_key=api_key,
            sql=payload.sql,
            params=payload.params,
            db_alias=db_cfg.alias,
            trace_id=trace_id,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execute failed: {str(e)}",
        )


