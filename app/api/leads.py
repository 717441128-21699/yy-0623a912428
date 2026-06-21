from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
from datetime import datetime

from app.database import get_db
from app.schemas import (
    LeadReceiveRequest, LeadDeduplicateResponse, ApiResponse,
    ReviewConfirmRequest, BatchReviewRequest, MarkReturningRequest
)
from app.services.deduplication import (
    deduplicate_lead, create_lead_record, update_existing_lead,
    create_duplicate_record, generate_request_id, hash_phone
)
from app.services.stats import update_daily_stats
from app.models import Lead, LeadDuplicate, LeadReview, CustomerArchive

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
    elif existing_lead is None:
        new_lead = create_lead_record(db, lead_data, result)
        new_lead.lead_status = "new"
        new_lead.is_returning = True
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
        original_source_channel=result.original_source_channel,
        original_source_store=result.original_source_store,
        last_visit_date=result.last_visit_date,
        customer_level=result.customer_level,
        followup_suggestion=result.followup_suggestion,
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
            "final_owner_channel": lead.channel_code if lead.lead_status == "allocated" else None,
            "final_owner_store": lead.store_code if lead.lead_status == "allocated" else None,
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


@router.get("/duplicates/todo-summary", response_model=ApiResponse, summary="复核待办统计")
async def get_review_todo_summary(
    channel_code: Optional[str] = None,
    store_code: Optional[str] = None,
    db: Session = Depends(get_db)
):
    base_query = db.query(LeadDuplicate).filter(LeadDuplicate.is_confirmed == False)
    
    if channel_code:
        base_query = base_query.filter(
            (LeadDuplicate.original_channel == channel_code) |
            (LeadDuplicate.duplicate_channel == channel_code)
        )
    if store_code:
        base_query = base_query.filter(
            (LeadDuplicate.original_store == store_code) |
            (LeadDuplicate.duplicate_store == store_code)
        )
    
    total = base_query.count()
    
    by_type = db.query(
        LeadDuplicate.duplicate_type, func.count(LeadDuplicate.id)
    ).filter(LeadDuplicate.is_confirmed == False).group_by(LeadDuplicate.duplicate_type).all()
    
    by_channel = []
    if not channel_code:
        chan_rows = db.query(
            LeadDuplicate.original_channel, func.count(LeadDuplicate.id)
        ).filter(LeadDuplicate.is_confirmed == False).group_by(LeadDuplicate.original_channel).all()
        for row in chan_rows:
            by_channel.append({"channel_code": row[0], "count": row[1]})
    
    by_store = []
    if not store_code:
        store_rows = db.query(
            LeadDuplicate.original_store, func.count(LeadDuplicate.id)
        ).filter(
            LeadDuplicate.is_confirmed == False,
            LeadDuplicate.original_store.isnot(None)
        ).group_by(LeadDuplicate.original_store).all()
        for row in store_rows:
            by_store.append({"store_code": row[0], "count": row[1]})
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "total_pending": total,
            "by_duplicate_type": [{"duplicate_type": r[0], "count": r[1]} for r in by_type],
            "by_channel": by_channel,
            "by_store": by_store
        }
    )


@router.get("/duplicates/todo", response_model=ApiResponse, summary="复核待办列表（按条件筛选未复核记录）")
async def get_review_todo_list(
    channel_code: Optional[str] = None,
    store_code: Optional[str] = None,
    duplicate_type: Optional[str] = None,
    is_cross_store: Optional[bool] = None,
    min_match_score: Optional[float] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(LeadDuplicate).filter(LeadDuplicate.is_confirmed == False)
    
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
    if duplicate_type:
        query = query.filter(LeadDuplicate.duplicate_type == duplicate_type)
    if is_cross_store is not None:
        query = query.filter(LeadDuplicate.is_cross_store == is_cross_store)
    if min_match_score is not None:
        query = query.filter(LeadDuplicate.match_score >= min_match_score)
    if start_date:
        query = query.filter(LeadDuplicate.created_at >= start_date)
    if end_date:
        query = query.filter(LeadDuplicate.created_at <= f"{end_date} 23:59:59")
    
    total = query.count()
    
    duplicates = query.order_by(LeadDuplicate.match_score.desc(), LeadDuplicate.created_at.desc()).offset(
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


def _apply_review_logic(db: Session, dup: LeadDuplicate, review_result: str,
                        review_remark: Optional[str], reviewer: str,
                        final_owner_channel: Optional[str], final_owner_store: Optional[str]):
    dup.is_confirmed = True
    dup.confirmed_by = reviewer
    dup.confirmed_at = datetime.now()
    dup.confirm_result = review_result
    dup.confirm_remark = review_remark
    
    lead = db.query(Lead).filter(Lead.lead_id == dup.lead_id).first()
    
    if review_result == "confirmed":
        if lead:
            lead.lead_status = "allocated"
            lead.review_status = "confirmed"
            lead.reviewed_by = reviewer
            lead.reviewed_at = datetime.now()
        dup.final_owner_channel = lead.channel_code if lead else dup.original_channel
        dup.final_owner_store = lead.store_code if lead else dup.original_store
    
    elif review_result == "rejected":
        if lead:
            lead.review_status = "rejected"
            lead.reviewed_by = reviewer
            lead.reviewed_at = datetime.now()
            lead.lead_status = "new"
        dup.final_owner_channel = None
        dup.final_owner_store = None
    
    elif review_result == "reassigned":
        final_channel = final_owner_channel or dup.original_channel
        final_store = final_owner_store or dup.original_store
        dup.final_owner_channel = final_channel
        dup.final_owner_store = final_store
        if lead:
            lead.channel_code = final_channel
            lead.store_code = final_store
            lead.lead_status = "allocated"
            lead.review_status = "reassigned"
            lead.reviewed_by = reviewer
            lead.reviewed_at = datetime.now()
    
    review_rec = LeadReview(
        duplicate_id=dup.id,
        lead_id=dup.lead_id,
        reviewer=reviewer,
        review_result=review_result,
        review_remark=review_remark,
        final_owner_channel=dup.final_owner_channel,
        final_owner_store=dup.final_owner_store
    )
    db.add(review_rec)
    
    related_dups = db.query(LeadDuplicate).filter(
        LeadDuplicate.lead_id == dup.lead_id,
        LeadDuplicate.is_confirmed == False,
        LeadDuplicate.id != dup.id
    ).all()
    for related in related_dups:
        related.final_owner_channel = dup.final_owner_channel
        related.final_owner_store = dup.final_owner_store
    
    return dup, lead


@router.post("/duplicates/batch-review", response_model=ApiResponse, summary="批量复核重复冲突")
async def batch_review_duplicates(
    batch_data: BatchReviewRequest,
    db: Session = Depends(get_db)
):
    reviewer = batch_data.reviewer or "system"
    dups = db.query(LeadDuplicate).filter(
        LeadDuplicate.id.in_(batch_data.duplicate_ids),
        LeadDuplicate.is_confirmed == False
    ).all()
    
    if not dups:
        raise HTTPException(status_code=404, detail="未找到可复核的记录")
    
    skipped_ids = list(set(batch_data.duplicate_ids) - set(d.id for d in dups))
    success_count = 0
    results = []
    
    for dup in dups:
        try:
            processed_dup, lead = _apply_review_logic(
                db, dup, batch_data.review_result, batch_data.review_remark,
                reviewer, batch_data.final_owner_channel, batch_data.final_owner_store
            )
            success_count += 1
            results.append({
                "duplicate_id": processed_dup.id,
                "lead_id": processed_dup.lead_id,
                "review_result": batch_data.review_result,
                "final_owner_channel": processed_dup.final_owner_channel,
                "final_owner_store": processed_dup.final_owner_store
            })
        except Exception:
            continue
    
    db.commit()
    
    return ApiResponse(
        code=0,
        message=f"批量复核完成，成功{success_count}条，跳过{len(skipped_ids)}条（已复核或不存在）",
        data={
            "success_count": success_count,
            "skipped_count": len(skipped_ids),
            "skipped_ids": skipped_ids,
            "results": results
        }
    )


@router.post("/{lead_id}/mark-returning", response_model=ApiResponse, summary="给线索打老客标签/取消标签")
async def mark_lead_returning(
    lead_id: str,
    mark_data: MarkReturningRequest,
    db: Session = Depends(get_db)
):
    lead = db.query(Lead).filter(Lead.lead_id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail="线索不存在")
    
    lead.is_returning = mark_data.is_returning
    if mark_data.remark and not lead.remark:
        lead.remark = mark_data.remark
    elif mark_data.remark:
        lead.remark = (lead.remark or "") + "\n" + mark_data.remark
    
    if mark_data.is_returning:
        if mark_data.original_source_channel and not lead.first_channel_code:
            lead.first_channel_code = mark_data.original_source_channel
        if mark_data.original_source_store and not lead.first_store_code:
            lead.first_store_code = mark_data.original_source_store
        
        if lead.phone:
            phone_hash = hash_phone(lead.phone)
            archive = db.query(CustomerArchive).filter(CustomerArchive.phone_hash == phone_hash).first()
            if not archive:
                archive = CustomerArchive(
                    phone=lead.phone,
                    phone_hash=phone_hash,
                    name=lead.name,
                    city=lead.city,
                    original_source_channel=mark_data.original_source_channel or lead.first_channel_code or lead.channel_code,
                    original_source_store=mark_data.original_source_store or lead.first_store_code or lead.store_code,
                    first_visit_date=mark_data.last_visit_date or lead.first_lead_time or lead.created_at,
                    last_visit_date=mark_data.last_visit_date or lead.last_lead_time or lead.created_at,
                    total_visit_count=lead.total_lead_count or 1,
                    suggested_followup=mark_data.suggested_followup,
                    remark=mark_data.remark
                )
                db.add(archive)
            else:
                if mark_data.suggested_followup:
                    archive.suggested_followup = mark_data.suggested_followup
                if mark_data.last_visit_date:
                    archive.last_visit_date = mark_data.last_visit_date
                archive.total_visit_count = (archive.total_visit_count or 0) + 1
    
    db.commit()
    
    return ApiResponse(
        code=0,
        message="操作成功",
        data={
            "lead_id": lead.lead_id,
            "is_returning": lead.is_returning,
            "operator": mark_data.operator or "system"
        }
    )
