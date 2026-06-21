import time
import json
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.services.log_service import log_api_call
from app.services.deduplication import generate_request_id
import re


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        request_id = generate_request_id()
        
        request.state.request_id = request_id
        
        client_ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        
        try:
            body = await request.body()
            request_body = body.decode("utf-8") if body else ""
        except:
            request_body = ""
        
        response = await call_next(request)
        
        process_time = int((time.time() - start_time) * 1000)
        
        if request.url.path.startswith("/api/v1/") and request.method != "OPTIONS":
            try:
                db = SessionLocal()
                
                channel_code = None
                store_code = None
                
                path = request.url.path
                
                db_log = log_api_call(
                    db=db,
                    request_id=request_id,
                    api_path=path,
                    method=request.method,
                    request_params={
                        "query": dict(request.query_params),
                        "body": request_body[:2000] if request_body else None
                    },
                    response_data={},
                    status_code=response.status_code,
                    process_time_ms=process_time,
                    client_ip=client_ip,
                    user_agent=user_agent,
                    channel_code=channel_code,
                    store_code=store_code,
                    has_error=response.status_code >= 400
                )
                db.commit()
                db.close()
            except Exception as e:
                print(f"Log error: {e}")
        
        response.headers["X-Request-ID"] = request_id
        return response


def validate_phone(phone: str) -> bool:
    if not phone:
        return False
    return bool(re.match(r'^1[3-9]\d{9}$', phone))


def validate_lead_data(data: dict) -> tuple:
    phone = data.get("phone")
    wechat = data.get("wechat_encrypted")
    
    if not phone and not wechat:
        return False, "手机号和加密微信不能同时为空"
    
    if phone and not validate_phone(phone):
        return False, "手机号格式不正确"
    
    if not data.get("channel_code"):
        return False, "渠道编码不能为空"
    
    return True, None
