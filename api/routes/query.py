from typing import Any, Dict, List, Mapping, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from api.auth import ApiKey, require_permission
from api.services.audit import write_api_audit_log
from api.services.backend_db import get_db_config_for_api
from dbskill.scripts.query import run_query as skill_run_query


class QueryRequest(BaseModel):
    sql: str
    params: Optional[Mapping[str, Any]] = None
    db_alias: Optional[str] = None


router = APIRouter(prefix="/query", tags=["query"])


@router.post("", dependencies=[Depends(require_permission("readonly"))])
async def query_endpoint(
    request: Request,
    payload: QueryRequest,
    api_key: ApiKey = Depends(require_permission("readonly")),
) -> Dict[str, Any]:
    """
    只读查询接口，内部调用 Skill 的 run_query。库由后台分配。
    """
    try:
        db_cfg = get_db_config_for_api(api_key.key_id, payload.db_alias)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    trace_id = uuid.uuid4().hex

    try:
        rows: List[Dict[str, Any]] = skill_run_query(
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
        return {"data": rows, "trace_id": trace_id}
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
            detail=f"Query failed: {str(e)}",
        )


