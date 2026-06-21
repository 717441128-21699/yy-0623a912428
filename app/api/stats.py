from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.schemas import ApiResponse
from app.services.stats import get_channel_stats, get_store_stats, get_daily_trend
from app.models import ApiLog

router = APIRouter(prefix="/stats", tags=["统计查询"])


@router.get("/channels", response_model=ApiResponse, summary="按渠道查询有效率")
async def get_channel_statistics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    stats = get_channel_stats(db, start_date, end_date)
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "items": stats,
            "total_count": len(stats)
        }
    )


@router.get("/stores", response_model=ApiResponse, summary="按门店查看重复来源")
async def get_store_statistics(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    stats = get_store_stats(db, start_date, end_date)
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "items": stats,
            "total_count": len(stats)
        }
    )


@router.get("/trend", response_model=ApiResponse, summary="每日趋势统计")
async def get_daily_statistics(
    channel_code: Optional[str] = None,
    store_code: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    trend_data = get_daily_trend(db, channel_code, store_code, start_date, end_date)
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "trend": trend_data,
            "total_days": len(trend_data)
        }
    )


@router.get("/overview", response_model=ApiResponse, summary="总览统计")
async def get_overview_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db)
):
    channel_stats = get_channel_stats(db, start_date, end_date)
    
    total_leads = sum(s["total_leads"] for s in channel_stats)
    total_valid = sum(s["valid_leads"] for s in channel_stats)
    total_dup = sum(s["duplicate_leads"] for s in channel_stats)
    total_new = sum(s["new_leads"] for s in channel_stats)
    total_black = sum(s["blacklist_leads"] for s in channel_stats)
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "total_leads": total_leads,
            "valid_leads": total_valid,
            "duplicate_leads": total_dup,
            "new_leads": total_new,
            "blacklist_leads": total_black,
            "valid_rate": round(total_valid / total_leads * 100, 2) if total_leads > 0 else 0.0,
            "duplicate_rate": round(total_dup / total_leads * 100, 2) if total_leads > 0 else 0.0,
            "new_customer_rate": round(total_new / total_leads * 100, 2) if total_leads > 0 else 0.0,
            "channel_count": len(channel_stats)
        }
    )


@router.get("/api-logs", response_model=ApiResponse, summary="接口调用日志")
async def get_api_logs(
    channel_code: Optional[str] = None,
    api_path: Optional[str] = None,
    has_error: Optional[bool] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(ApiLog)
    
    if channel_code:
        query = query.filter(ApiLog.channel_code == channel_code)
    if api_path:
        query = query.filter(ApiLog.api_path.like(f"%{api_path}%"))
    if has_error is not None:
        query = query.filter(ApiLog.has_error == has_error)
    if start_date:
        query = query.filter(ApiLog.created_at >= start_date)
    if end_date:
        query = query.filter(ApiLog.created_at <= f"{end_date} 23:59:59")
    
    total = query.count()
    
    logs = query.order_by(ApiLog.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    log_list = []
    for log in logs:
        log_list.append({
            "id": log.id,
            "request_id": log.request_id,
            "api_path": log.api_path,
            "method": log.method,
            "channel_code": log.channel_code,
            "status_code": log.status_code,
            "process_time_ms": log.process_time_ms,
            "client_ip": log.client_ip,
            "has_error": log.has_error,
            "error_message": log.error_message,
            "created_at": log.created_at
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "list": log_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )
