import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status

from api.auth import ApiKey, require_permission
from api.services.audit import write_api_audit_log
from api.services.backend_db import get_db_config_for_api
from dbskill.scripts.schema import get_schema as skill_get_schema


router = APIRouter(prefix="/schema", tags=["schema"])


def _schema_audit(
    request: Request,
    api_key: ApiKey,
    db_cfg: Any,
    trace_id: str,
    table: Optional[str] = None,
) -> None:
    write_api_audit_log(
        request=request,
        api_key=api_key,
        sql=None,
        params={"table": table} if table else None,
        db_alias=db_cfg.alias,
        trace_id=trace_id,
    )


@router.get("", dependencies=[Depends(require_permission("readonly"))])
async def get_schema_endpoint(
    request: Request,
    table: Optional[str] = None,
    db_alias: Optional[str] = None,
    api_key: ApiKey = Depends(require_permission("readonly")),
) -> Dict[str, Any]:
    """
    通过 Skill 脚本获取数据库表结构。库由后台分配，db_alias 可选（不传时用账号唯一库或默认库）。
    """
    try:
        db_cfg = get_db_config_for_api(api_key.key_id, db_alias)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    trace_id = uuid.uuid4().hex
    try:
        data = skill_get_schema(table=table, db_cfg=db_cfg)
        _schema_audit(request, api_key, db_cfg, trace_id, table)
        return {"data": data, "trace_id": trace_id}
    except PermissionError as e:
        _schema_audit(request, api_key, db_cfg, trace_id, table)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        _schema_audit(request, api_key, db_cfg, trace_id, table)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        _schema_audit(request, api_key, db_cfg, trace_id, table)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Schema failed: {str(e)}",
        )


