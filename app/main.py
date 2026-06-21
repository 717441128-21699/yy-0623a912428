from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.database import engine, Base
from app.api import api_router
from app.middleware import LoggingMiddleware
from app.config import settings

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="医美连锁渠道线索判重服务 - 统一接入官网表单、广告平台、企微客服、CRM、小程序预约等入口",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.add_middleware(LoggingMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_exception_handler(request: Request, exc: SQLAlchemyError):
    return JSONResponse(
        status_code=500,
        content={
            "code": 500,
            "message": "数据库操作异常",
            "data": None,
            "request_id": getattr(request.state, "request_id", "")
        }
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "code": 400,
            "message": str(exc),
            "data": None,
            "request_id": getattr(request.state, "request_id", "")
        }
    )


@app.get("/", summary="服务健康检查")
async def health_check():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs"
    }


@app.get("/health", summary="健康检查端点")
async def health():
    return {"status": "ok", "service": "lead-deduplication"}


app.include_router(api_router, prefix=settings.API_PREFIX)
