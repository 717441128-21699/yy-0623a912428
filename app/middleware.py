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
        
        request_body = ""
        channel_code = None
        store_code = None
        
        try:
            body = await request.body()
            if body:
                request_body = body.decode("utf-8")
                try:
                    body_json = json.loads(request_body)
                    channel_code = body_json.get("channel_code")
                    store_code = body_json.get("store_code")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass
        except Exception:
            request_body = ""
        
        response = await call_next(request)
        
        process_time = int((time.time() - start_time) * 1000)
        
        if request.url.path.startswith("/api/v1/") and request.method != "OPTIONS":
            try:
                db = SessionLocal()
                
                summary_parts = []
                if request_body:
                    try:
                        body_json = json.loads(request_body)
                        if body_json.get("phone"):
                            summary_parts.append(f"phone:{body_json['phone']}")
                        if body_json.get("name"):
                            summary_parts.append(f"name:{body_json['name']}")
                        if body_json.get("channel_code"):
                            summary_parts.append(f"channel:{body_json['channel_code']}")
                        if body_json.get("store_code"):
                            summary_parts.append(f"store:{body_json['store_code']}")
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        pass
                
                query_params = dict(request.query_params)
                if query_params:
                    for key in ["channel_code", "store_code", "api_path", "has_error"]:
                        if key in query_params:
                            summary_parts.append(f"{key}:{query_params[key]}")
                
                request_summary = ", ".join(summary_parts[:5]) if summary_parts else None
                
                error_message = None
                if response.status_code >= 400:
                    error_message = f"HTTP {response.status_code}"
                
                db_log = log_api_call(
                    db=db,
                    request_id=request_id,
                    api_path=request.url.path,
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
                    has_error=response.status_code >= 400,
                    error_message=error_message,
                    request_summary=request_summary
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
