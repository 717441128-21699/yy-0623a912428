from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.schemas import (
    LeadReceiveRequest, LeadDeduplicateResponse, ApiResponse,
    ReviewConfirmRequest
)
from app.services.deduplication import (
    deduplicate_lead, create_lead_record, update_existing_lead,
    create_duplicate_record, generate_request_id
)
from app.services.stats import update_daily_stats
from app.models import Lead, LeadDuplicate, LeadReview

router = APIRouter(prefix="/leads", tags=["线索管理"])


@router.post("/receive", response_model=ApiResponse, summary="接收并判重线索")
async def receive_lead(
    request: Request,
    lead_data: LeadReceiveRequest,
    db: Session = Depends(get_db)
):
    request_id = getattr(request.state, "request_id", generate_request_id())
    
    if not lead_data.phone and not lead_data.wechat_encrypted:
        raise HTTPException(status_code=400, detail="手机号和加密微信不能同时为空")
    
    result, existing_lead = deduplicate_lead(db, lead_data)
    
    is_new = result.is_new_customer and not result.is_blacklist
    is_duplicate = not result.is_new_customer and not result.is_blacklist
    is_valid_lead = not result.is_blacklist
    is_returning = result.is_returning and not result.is_blacklist
    
    if result.is_blacklist:
        new_lead = create_lead_record(db, lead_data, result)
        new_lead.lead_status = "blacklist"
        lead_id = new_lead.lead_id
    elif is_new:
        new_lead = create_lead_record(db, lead_data, result)
        new_lead.lead_status = "new"
        lead_id = new_lead.lead_id
    else:
        updated_lead = update_existing_lead(db, existing_lead, lead_data, result)
        lead_id = updated_lead.lead_id
        
        new_lead_record = create_lead_record(db, lead_data, result)
        
        dup_record = create_duplicate_record(
            db, existing_lead, new_lead_record.lead_id, result, lead_data
        )
    
    update_daily_stats(
        db=db,
        channel_code=lead_data.channel_code,
        store_code=lead_data.store_code,
        is_new=is_new,
        is_duplicate=is_duplicate,
        is_cross_store=result.is_cross_store,
        is_blacklist=result.is_blacklist,
        is_valid=is_valid_lead,
        is_returning=is_returning
    )
    
    db.commit()
    
    response_data = LeadDeduplicateResponse(
        request_id=request_id,
        lead_id=lead_id,
        result_type=result.result_type,
        result_description=result.result_description,
        suggested_action=result.suggested_action,
        match_score=result.match_score,
        duplicate_reason_code=result.duplicate_reason_code,
        duplicate_reason=result.duplicate_reason,
        is_new_customer=result.is_new_customer,
        is_blacklist=result.is_blacklist,
        is_cross_store=result.is_cross_store,
        is_returning=result.is_returning,
        attribution_channel=result.attribution_channel,
        attribution_store=result.attribution_store,
        attribution_type=result.attribution_type,
        original_lead_id=result.original_lead_id,
        original_channel=result.original_channel,
        original_store=result.original_store,
        original_lead_time=result.original_lead_time,
        conflict_duplicate_id=result.conflict_duplicate_id
    )
    
    return ApiResponse(
        code=0,
        message="success",
        data=response_data.model_dump(mode='json'),
        request_id=request_id
    )


@router.get("/list", response_model=ApiResponse, summary="线索列表查询")
async def get_lead_list(
    channel_code: Optional[str] = None,
    store_code: Optional[str] = None,
    city: Optional[str] = None,
    lead_status: Optional[str] = None,
    review_status: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(Lead)
    
    if channel_code:
        query = query.filter(Lead.channel_code == channel_code)
    if store_code:
        query = query.filter(Lead.store_code == store_code)
    if city:
        query = query.filter(Lead.city == city)
    if lead_status:
        query = query.filter(Lead.lead_status == lead_status)
    if review_status:
        query = query.filter(Lead.review_status == review_status)
    if start_date:
        query = query.filter(Lead.created_at >= start_date)
    if end_date:
        query = query.filter(Lead.created_at <= f"{end_date} 23:59:59")
    
    total = query.count()
    
    leads = query.order_by(Lead.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    lead_list = []
    for lead in leads:
        lead_list.append({
            "lead_id": lead.lead_id,
            "phone": lead.phone,
            "name": lead.name,
            "city": lead.city,
            "intended_project": lead.intended_project,
            "channel_code": lead.channel_code,
            "store_code": lead.store_code,
            "lead_status": lead.lead_status,
            "attribution_type": lead.attribution_type,
            "total_lead_count": lead.total_lead_count,
            "is_cross_store": lead.is_cross_store,
            "is_returning": lead.is_returning,
            "review_status": lead.review_status,
            "reviewed_by": lead.reviewed_by,
            "reviewed_at": lead.reviewed_at,
            "created_at": lead.created_at,
            "last_lead_time": lead.last_lead_time
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "list": lead_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.get("/{lead_id}", response_model=ApiResponse, summary="线索详情")
async def get_lead_detail(lead_id: str, db: Session = Depends(get_db)):
    lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    
    duplicates = db.query(LeadDuplicate).filter(
        (LeadDuplicate.lead_id == lead_id) | (LeadDuplicate.duplicate_lead_id == lead_id)
    ).order_by(LeadDuplicate.created_at.desc()).all()
    
    dup_list = []
    for dup in duplicates:
        dup_list.append({
            "id": dup.id,
            "lead_id": dup.lead_id,
            "duplicate_lead_id": dup.duplicate_lead_id,
            "duplicate_type": dup.duplicate_type,
            "duplicate_reason": dup.duplicate_reason,
            "duplicate_reason_code": dup.duplicate_reason_code,
            "match_score": dup.match_score,
            "is_confirmed": dup.is_confirmed,
            "confirm_result": dup.confirm_result,
            "confirm_remark": dup.confirm_remark,
            "final_owner_channel": dup.final_owner_channel,
            "final_owner_store": dup.final_owner_store,
            "is_cross_store": dup.is_cross_store,
            "original_store": dup.original_store,
            "duplicate_store": dup.duplicate_store,
            "created_at": dup.created_at
        })
    
    reviews = db.query(LeadReview).filter(
        LeadReview.lead_id == lead_id
    ).order_by(LeadReview.created_at.desc()).all()
    
    review_list = []
    for r in reviews:
        review_list.append({
            "id": r.id,
            "duplicate_id": r.duplicate_id,
            "reviewer": r.reviewer,
            "review_result": r.review_result,
            "review_remark": r.review_remark,
            "final_owner_channel": r.final_owner_channel,
            "final_owner_store": r.final_owner_store,
            "created_at": r.created_at
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "lead_id": lead.lead_id,
            "phone": lead.phone,
            "wechat_encrypted": lead.wechat_encrypted,
            "name": lead.name,
            "city": lead.city,
            "intended_project": lead.intended_project,
            "ad_plan": lead.ad_plan,
            "landing_page": lead.landing_page,
            "channel_code": lead.channel_code,
            "store_code": lead.store_code,
            "lead_status": lead.lead_status,
            "attribution_type": lead.attribution_type,
            "first_channel_code": lead.first_channel_code,
            "first_store_code": lead.first_store_code,
            "first_lead_time": lead.first_lead_time,
            "last_channel_code": lead.last_channel_code,
            "last_store_code": lead.last_store_code,
            "last_lead_time": lead.last_lead_time,
            "total_lead_count": lead.total_lead_count,
            "is_cross_store": lead.is_cross_store,
            "is_returning": lead.is_returning,
            "review_status": lead.review_status,
            "reviewed_by": lead.reviewed_by,
            "reviewed_at": lead.reviewed_at,
            "remark": lead.remark,
            "created_at": lead.created_at,
            "duplicates": dup_list,
            "reviews": review_list
        }
    )


@router.get("/duplicates/list", response_model=ApiResponse, summary="重复冲突列表")
async def get_duplicate_list(
    channel_code: Optional[str] = None,
    store_code: Optional[str] = None,
    is_confirmed: Optional[bool] = None,
    is_cross_store: Optional[bool] = None,
    confirm_result: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(LeadDuplicate)
    
    if channel_code:
        query = query.filter(
            (LeadDuplicate.original_channel == channel_code) | 
            (LeadDuplicate.duplicate_channel == channel_code)
        )
    if store_code:
        query = query.filter(
            (LeadDuplicate.original_store == store_code) | 
            (LeadDuplicate.duplicate_store == store_code)
        )
    if is_confirmed is not None:
        query = query.filter(LeadDuplicate.is_confirmed == is_confirmed)
    if is_cross_store is not None:
        query = query.filter(LeadDuplicate.is_cross_store == is_cross_store)
    if confirm_result:
        query = query.filter(LeadDuplicate.confirm_result == confirm_result)
    if start_date:
        query = query.filter(LeadDuplicate.created_at >= start_date)
    if end_date:
        query = query.filter(LeadDuplicate.created_at <= f"{end_date} 23:59:59")
    
    total = query.count()
    
    duplicates = query.order_by(LeadDuplicate.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    dup_list = []
    for dup in duplicates:
        dup_list.append({
            "id": dup.id,
            "lead_id": dup.lead_id,
            "duplicate_lead_id": dup.duplicate_lead_id,
            "duplicate_type": dup.duplicate_type,
            "duplicate_reason": dup.duplicate_reason,
            "duplicate_reason_code": dup.duplicate_reason_code,
            "match_score": dup.match_score,
            "is_confirmed": dup.is_confirmed,
            "confirm_result": dup.confirm_result,
            "confirm_remark": dup.confirm_remark,
            "confirmed_by": dup.confirmed_by,
            "confirmed_at": dup.confirmed_at,
            "final_owner_channel": dup.final_owner_channel,
            "final_owner_store": dup.final_owner_store,
            "is_cross_store": dup.is_cross_store,
            "original_store": dup.original_store,
            "duplicate_store": dup.duplicate_store,
            "original_channel": dup.original_channel,
            "duplicate_channel": dup.duplicate_channel,
            "created_at": dup.created_at
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "list": dup_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.post("/duplicates/review", response_model=ApiResponse, summary="人工复核重复冲突")
async def review_duplicate(
    review_data: ReviewConfirmRequest,
    db: Session = Depends(get_db)
):
    dup = db.query(LeadDuplicate).filter(LeadDuplicate.id == review_data.duplicate_id).first()
    if not dup:
        raise HTTPException(status_code=404, detail="重复记录不存在")
    
    if dup.is_confirmed:
        raise HTTPException(status_code=400, detail="该记录已复核，不能重复操作")
    
    dup.is_confirmed = True
    dup.confirmed_by = review_data.reviewer or "system"
    dup.confirmed_at = datetime.now()
    dup.confirm_result = review_data.review_result
    dup.confirm_remark = review_data.review_remark
    
    lead = db.query(Lead).filter(Lead.lead_id == dup.lead_id).first()
    
    if review_data.review_result == "confirmed":
        if lead:
            lead.lead_status = "allocated"
            lead.review_status = "confirmed"
            lead.reviewed_by = review_data.reviewer or "system"
            lead.reviewed_at = datetime.now()
        
        dup.final_owner_channel = lead.channel_code if lead else dup.original_channel
        dup.final_owner_store = lead.store_code if lead else dup.original_store
    
    elif review_data.review_result == "rejected":
        if lead:
            lead.review_status = "rejected"
            lead.reviewed_by = review_data.reviewer or "system"
            lead.reviewed_at = datetime.now()
            lead.lead_status = "new"
        
        dup.final_owner_channel = None
        dup.final_owner_store = None
    
    elif review_data.review_result == "reassigned":
        final_channel = review_data.final_owner_channel or dup.original_channel
        final_store = review_data.final_owner_store or dup.original_store
        
        dup.final_owner_channel = final_channel
        dup.final_owner_store = final_store
        
        if lead:
            lead.channel_code = final_channel
            lead.store_code = final_store
            lead.lead_status = "allocated"
            lead.review_status = "reassigned"
            lead.reviewed_by = review_data.reviewer or "system"
            lead.reviewed_at = datetime.now()
    
    review = LeadReview(
        duplicate_id=dup.id,
        lead_id=dup.lead_id,
        reviewer=review_data.reviewer or "system",
        review_result=review_data.review_result,
        review_remark=review_data.review_remark,
        final_owner_channel=dup.final_owner_channel,
        final_owner_store=dup.final_owner_store
    )
    db.add(review)
    
    related_dups = db.query(LeadDuplicate).filter(
        LeadDuplicate.lead_id == dup.lead_id,
        LeadDuplicate.is_confirmed == False,
        LeadDuplicate.id != dup.id
    ).all()
    
    for related in related_dups:
        related.final_owner_channel = dup.final_owner_channel
        related.final_owner_store = dup.final_owner_store
    
    db.commit()
    
    return ApiResponse(
        code=0,
        message="复核成功",
        data={
            "duplicate_id": dup.id,
            "review_result": review_data.review_result,
            "final_owner_channel": dup.final_owner_channel,
            "final_owner_store": dup.final_owner_store,
            "lead_status": lead.lead_status if lead else None,
            "review_status": lead.review_status if lead else None
        }
    )
