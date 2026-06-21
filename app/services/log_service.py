import json
import time
from datetime import datetime
from sqlalchemy.orm import Session
from app.models import ApiLog
from typing import Optional


def log_api_call(db: Session, request_id: str, api_path: str, method: str,
                 request_params: dict, response_data: dict, status_code: int,
                 process_time_ms: int, client_ip: Optional[str] = None,
                 user_agent: Optional[str] = None, channel_code: Optional[str] = None,
                 store_code: Optional[str] = None, has_error: bool = False,
                 error_message: Optional[str] = None):
    log = ApiLog(
        request_id=request_id,
        api_path=api_path,
        method=method,
        channel_code=channel_code,
        store_code=store_code,
        request_params=json.dumps(request_params, ensure_ascii=False) if request_params else None,
        response_data=json.dumps(response_data, ensure_ascii=False) if response_data else None,
        status_code=status_code,
        process_time_ms=process_time_ms,
        client_ip=client_ip,
        user_agent=user_agent,
        has_error=has_error,
        error_message=error_message
    )
    db.add(log)
    db.flush()
    return log
