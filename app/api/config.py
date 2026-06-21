from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime

from app.database import get_db
from app.schemas import (
    ApiResponse, ChannelCreate, StoreCreate, BlacklistCreate,
    DedupRuleCreate, DedupRuleUpdate, DedupRuleTryoutRequest,
    CustomerArchiveCreate, CustomerArchiveBatchImport
)
from app.models import Channel, Store, Blacklist, DedupRule, CustomerArchive
from app.services.deduplication import hash_phone, deduplicate_lead, get_rules_by_key, get_active_rules

router = APIRouter(prefix="/config", tags=["配置管理"])


@router.get("/channels", response_model=ApiResponse, summary="渠道列表")
async def get_channels(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Channel)
    if is_active is not None:
        query = query.filter(Channel.is_active == is_active)
    
    channels = query.order_by(Channel.priority.desc()).all()
    
    channel_list = []
    for ch in channels:
        channel_list.append({
            "id": ch.id,
            "channel_code": ch.channel_code,
            "channel_name": ch.channel_name,
            "channel_type": ch.channel_type,
            "priority": ch.priority,
            "is_active": ch.is_active,
            "description": ch.description,
            "created_at": ch.created_at
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={"list": channel_list, "total": len(channel_list)}
    )


@router.post("/channels", response_model=ApiResponse, summary="新增渠道")
async def create_channel(
    channel_data: ChannelCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(Channel).filter(
        Channel.channel_code == channel_data.channel_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="渠道编码已存在")
    
    channel = Channel(
        channel_code=channel_data.channel_code,
        channel_name=channel_data.channel_name,
        channel_type=channel_data.channel_type,
        priority=channel_data.priority,
        description=channel_data.description,
        is_active=True
    )
    
    db.add(channel)
    db.commit()
    db.refresh(channel)
    
    return ApiResponse(
        code=0,
        message="创建成功",
        data={"channel_code": channel.channel_code}
    )


@router.put("/channels/{channel_code}", response_model=ApiResponse, summary="更新渠道")
async def update_channel(
    channel_code: str,
    channel_data: ChannelCreate,
    db: Session = Depends(get_db)
):
    channel = db.query(Channel).filter(Channel.channel_code == channel_code).first()
    if not channel:
        raise HTTPException(status_code=404, detail="渠道不存在")
    
    channel.channel_name = channel_data.channel_name
    channel.channel_type = channel_data.channel_type
    channel.priority = channel_data.priority
    channel.description = channel_data.description
    
    db.commit()
    
    return ApiResponse(code=0, message="更新成功")


@router.get("/stores", response_model=ApiResponse, summary="门店列表")
async def get_stores(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(Store)
    if is_active is not None:
        query = query.filter(Store.is_active == is_active)
    
    stores = query.order_by(Store.store_code).all()
    
    store_list = []
    for s in stores:
        store_list.append({
            "id": s.id,
            "store_code": s.store_code,
            "store_name": s.store_name,
            "city": s.city,
            "is_active": s.is_active,
            "created_at": s.created_at
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={"list": store_list, "total": len(store_list)}
    )


@router.post("/stores", response_model=ApiResponse, summary="新增门店")
async def create_store(
    store_data: StoreCreate,
    db: Session = Depends(get_db)
):
    existing = db.query(Store).filter(
        Store.store_code == store_data.store_code
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="门店编码已存在")
    
    store = Store(
        store_code=store_data.store_code,
        store_name=store_data.store_name,
        city=store_data.city,
        is_active=True
    )
    
    db.add(store)
    db.commit()
    db.refresh(store)
    
    return ApiResponse(
        code=0,
        message="创建成功",
        data={"store_code": store.store_code}
    )


@router.get("/blacklist", response_model=ApiResponse, summary="黑名单列表")
async def get_blacklist(
    black_type: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(Blacklist)
    
    if black_type:
        query = query.filter(Blacklist.black_type == black_type)
    if is_active is not None:
        query = query.filter(Blacklist.is_active == is_active)
    
    total = query.count()
    items = query.order_by(Blacklist.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    item_list = []
    for item in items:
        item_list.append({
            "id": item.id,
            "black_type": item.black_type,
            "black_value": item.black_value,
            "phone_plain": item.phone_plain,
            "reason": item.reason,
            "is_active": item.is_active,
            "created_at": item.created_at
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "list": item_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.post("/blacklist", response_model=ApiResponse, summary="新增黑名单")
async def create_blacklist(
    blacklist_data: BlacklistCreate,
    db: Session = Depends(get_db)
):
    black_type = blacklist_data.black_type
    black_value = None
    phone_plain = None
    
    if black_type == "phone":
        if not blacklist_data.phone:
            raise HTTPException(status_code=400, detail="手机号黑名单必须提供 phone 字段")
        black_value = hash_phone(blacklist_data.phone)
        phone_plain = blacklist_data.phone
    elif black_type == "wechat":
        if not blacklist_data.wechat_encrypted:
            raise HTTPException(status_code=400, detail="微信黑名单必须提供 wechat_encrypted 字段")
        black_value = blacklist_data.wechat_encrypted
    else:
        raise HTTPException(status_code=400, detail="black_type 只支持 phone 或 wechat")
    
    existing = db.query(Blacklist).filter(
        Blacklist.black_type == black_type,
        Blacklist.black_value == black_value
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该黑名单已存在")
    
    black = Blacklist(
        black_type=black_type,
        black_value=black_value,
        phone_plain=phone_plain,
        reason=blacklist_data.reason,
        is_active=True
    )
    
    db.add(black)
    db.commit()
    db.refresh(black)
    
    return ApiResponse(
        code=0,
        message="添加成功",
        data={
            "id": black.id,
            "black_type": black_type,
            "phone_plain": phone_plain
        }
    )


@router.delete("/blacklist/{black_id}", response_model=ApiResponse, summary="删除黑名单")
async def delete_blacklist(
    black_id: int,
    db: Session = Depends(get_db)
):
    black = db.query(Blacklist).filter(Blacklist.id == black_id).first()
    if not black:
        raise HTTPException(status_code=404, detail="黑名单记录不存在")
    
    black.is_active = False
    db.commit()
    
    return ApiResponse(code=0, message="已删除")


@router.get("/dedup-rules", response_model=ApiResponse, summary="判重规则列表（按 rule_key 分组展示版本）")
async def get_dedup_rules(
    rule_key: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DedupRule)
    if rule_key:
        query = query.filter(DedupRule.rule_key == rule_key)
    if status:
        query = query.filter(DedupRule.status == status)
    
    rules = query.order_by(DedupRule.rule_key, DedupRule.version.desc()).all()
    
    rule_list = []
    for r in rules:
        rule_list.append({
            "id": r.id,
            "rule_name": r.rule_name,
            "rule_key": r.rule_key,
            "version": r.version,
            "phone_weight": r.phone_weight,
            "wechat_weight": r.wechat_weight,
            "name_weight": r.name_weight,
            "city_weight": r.city_weight,
            "confirmed_threshold": r.confirmed_threshold,
            "suspected_threshold": r.suspected_threshold,
            "status": r.status,
            "is_active": r.is_active,
            "published_by": r.published_by,
            "published_at": r.published_at,
            "description": r.description,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={"list": rule_list, "total": len(rule_list)}
    )


@router.post("/dedup-rules", response_model=ApiResponse, summary="新建判重规则（自动版本号+1，状态为draft）")
async def create_dedup_rule(
    rule_data: DedupRuleCreate,
    db: Session = Depends(get_db)
):
    existing_name = db.query(DedupRule).filter(DedupRule.rule_name == rule_data.rule_name).first()
    if existing_name:
        raise HTTPException(status_code=400, detail="规则名称已存在")
    
    if rule_data.suspected_threshold >= rule_data.confirmed_threshold:
        raise HTTPException(status_code=400, detail="疑似阈值必须小于确认阈值")
    
    last_rule = db.query(DedupRule).filter(
        DedupRule.rule_key == rule_data.rule_key
    ).order_by(DedupRule.version.desc()).first()
    
    next_version = (last_rule.version + 1) if last_rule else 1
    
    rule = DedupRule(
        rule_name=rule_data.rule_name,
        rule_key=rule_data.rule_key,
        version=next_version,
        phone_weight=rule_data.phone_weight,
        wechat_weight=rule_data.wechat_weight,
        name_weight=rule_data.name_weight,
        city_weight=rule_data.city_weight,
        confirmed_threshold=rule_data.confirmed_threshold,
        suspected_threshold=rule_data.suspected_threshold,
        description=rule_data.description,
        status="draft",
        is_active=False
    )
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return ApiResponse(
        code=0,
        message="创建成功（草稿状态，需发布后生效）",
        data={"rule_key": rule.rule_key, "version": rule.version, "status": rule.status}
    )


@router.put("/dedup-rules/{rule_key}", response_model=ApiResponse, summary="更新指定 rule_key 的最新版本规则（仅draft可修改）")
async def update_dedup_rule(
    rule_key: str,
    rule_data: DedupRuleUpdate,
    version: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DedupRule).filter(DedupRule.rule_key == rule_key)
    if version is not None:
        query = query.filter(DedupRule.version == version)
    else:
        query = query.order_by(DedupRule.version.desc())
    rule = query.first()
    
    if not rule:
        raise HTTPException(status_code=404, detail="判重规则不存在")
    
    if rule.status not in ("draft",):
        raise HTTPException(status_code=400, detail="仅草稿状态规则可修改，请先创建新版本")
    
    if rule_data.rule_name is not None:
        existing_name = db.query(DedupRule).filter(
            DedupRule.rule_name == rule_data.rule_name,
            DedupRule.id != rule.id
        ).first()
        if existing_name:
            raise HTTPException(status_code=400, detail="规则名称已存在")
        rule.rule_name = rule_data.rule_name
    
    if rule_data.phone_weight is not None:
        rule.phone_weight = rule_data.phone_weight
    if rule_data.wechat_weight is not None:
        rule.wechat_weight = rule_data.wechat_weight
    if rule_data.name_weight is not None:
        rule.name_weight = rule_data.name_weight
    if rule_data.city_weight is not None:
        rule.city_weight = rule_data.city_weight
    
    if rule_data.confirmed_threshold is not None:
        rule.confirmed_threshold = rule_data.confirmed_threshold
    if rule_data.suspected_threshold is not None:
        rule.suspected_threshold = rule_data.suspected_threshold
    
    if rule.suspected_threshold >= rule.confirmed_threshold:
        raise HTTPException(status_code=400, detail="疑似阈值必须小于确认阈值")
    
    if rule_data.description is not None:
        rule.description = rule_data.description
    if rule_data.is_active is not None:
        rule.is_active = rule_data.is_active
    
    db.commit()
    
    return ApiResponse(
        code=0,
        message="更新成功",
        data={"rule_key": rule.rule_key, "version": rule.version, "status": rule.status}
    )


@router.put("/dedup-rules/{rule_key}/publish", response_model=ApiResponse, summary="发布指定规则版本（发布后对所有新线索生效，其他版本标记为archived）")
async def publish_dedup_rule(
    rule_key: str,
    version: Optional[int] = None,
    published_by: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DedupRule).filter(DedupRule.rule_key == rule_key)
    if version is not None:
        query = query.filter(DedupRule.version == version)
    else:
        query = query.order_by(DedupRule.version.desc())
    target_rule = query.first()
    
    if not target_rule:
        raise HTTPException(status_code=404, detail="判重规则不存在")
    
    all_rules = db.query(DedupRule).all()
    for r in all_rules:
        r.status = "archived" if r.id != target_rule.id else "published"
        r.is_active = (r.id == target_rule.id)
    
    target_rule.published_by = published_by or "system"
    target_rule.published_at = datetime.now()
    
    db.commit()
    
    return ApiResponse(
        code=0,
        message="发布成功，后续新线索将按该版本规则判重",
        data={
            "published_rule_key": target_rule.rule_key,
            "published_version": target_rule.version,
            "published_at": target_rule.published_at.isoformat() if target_rule.published_at else None
        }
    )


@router.put("/dedup-rules/{rule_key}/activate", response_model=ApiResponse, summary="激活指定判重规则（同时停用其他规则，兼容旧接口）")
async def activate_dedup_rule(
    rule_key: str,
    db: Session = Depends(get_db)
):
    rule = db.query(DedupRule).filter(DedupRule.rule_key == rule_key).order_by(DedupRule.version.desc()).first()
    if not rule:
        raise HTTPException(status_code=404, detail="判重规则不存在")
    
    all_rules = db.query(DedupRule).all()
    for r in all_rules:
        r.is_active = (r.rule_key == rule_key)
        if r.id == rule.id:
            r.status = "published"
            r.published_by = r.published_by or "system"
            r.published_at = r.published_at or datetime.now()
    
    db.commit()
    
    return ApiResponse(
        code=0,
        message="已激活指定规则",
        data={"active_rule_key": rule_key, "active_version": rule.version}
    )


@router.post("/dedup-rules/tryout", response_model=ApiResponse, summary="规则试算：用样例线索验证指定/自定义规则命中结果，不写入数据库")
async def tryout_dedup_rules(
    tryout_data: DedupRuleTryoutRequest,
    db: Session = Depends(get_db)
):
    if tryout_data.custom_rules:
        custom = tryout_data.custom_rules
        if custom.suspected_threshold >= custom.confirmed_threshold:
            raise HTTPException(status_code=400, detail="自定义规则疑似阈值必须小于确认阈值")
        rules = {
            "phone_weight": custom.phone_weight,
            "wechat_weight": custom.wechat_weight,
            "name_weight": custom.name_weight,
            "city_weight": custom.city_weight,
            "confirmed_threshold": custom.confirmed_threshold,
            "suspected_threshold": custom.suspected_threshold,
            "rule_key": "custom",
            "version": 0,
        }
        rule_info = {
            "source": "custom_rules",
            "rule_key": "custom",
            "version": 0,
            "rule_name": custom.rule_name
        }
    elif tryout_data.rule_key:
        rules = get_rules_by_key(db, tryout_data.rule_key)
        if not rules:
            raise HTTPException(status_code=404, detail=f"指定的规则 {tryout_data.rule_key} 不存在")
        rule_info = {
            "source": "saved_rule",
            "rule_key": rules.get("rule_key"),
            "version": rules.get("version")
        }
    else:
        rules = get_active_rules(db)
        rule_info = {
            "source": "published_default",
            "rule_key": rules.get("rule_key"),
            "version": rules.get("version")
        }
    
    results = []
    for idx, sample in enumerate(tryout_data.sample_leads):
        result, best_match = deduplicate_lead(db, sample, custom_rules=rules)
        results.append({
            "sample_index": idx,
            "sample_phone": sample.phone,
            "sample_name": sample.name,
            "sample_channel": sample.channel_code,
            "sample_store": sample.store_code,
            "result_type": result.result_type,
            "result_description": result.result_description,
            "suggested_action": result.suggested_action,
            "match_score": result.match_score,
            "duplicate_reason_code": result.duplicate_reason_code,
            "is_new_customer": result.is_new_customer,
            "is_returning": result.is_returning,
            "is_cross_store": result.is_cross_store,
            "is_blacklist": result.is_blacklist,
            "attribution_channel": result.attribution_channel,
            "attribution_store": result.attribution_store,
            "original_lead_id": result.original_lead_id,
            "original_source_channel": result.original_source_channel,
            "original_source_store": result.original_source_store,
            "last_visit_date": result.last_visit_date.isoformat() if result.last_visit_date else None,
            "customer_level": result.customer_level,
            "followup_suggestion": result.followup_suggestion
        })
    
    summary = {}
    for r in results:
        rt = r["result_type"]
        summary[rt] = summary.get(rt, 0) + 1
    
    return ApiResponse(
        code=0,
        message="试算完成",
        data={
            "rule_info": rule_info,
            "total_samples": len(results),
            "result_summary": summary,
            "results": results
        }
    )


@router.get("/customer-archives", response_model=ApiResponse, summary="客户档案列表")
async def get_customer_archives(
    phone: Optional[str] = None,
    city: Optional[str] = None,
    original_source_channel: Optional[str] = None,
    customer_level: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db)
):
    query = db.query(CustomerArchive)
    
    if phone:
        ph = hash_phone(phone)
        query = query.filter(CustomerArchive.phone_hash == ph)
    if city:
        query = query.filter(CustomerArchive.city == city)
    if original_source_channel:
        query = query.filter(CustomerArchive.original_source_channel == original_source_channel)
    if customer_level:
        query = query.filter(CustomerArchive.customer_level == customer_level)
    if is_active is not None:
        query = query.filter(CustomerArchive.is_active == is_active)
    
    total = query.count()
    
    archives = query.order_by(CustomerArchive.last_visit_date.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()
    
    arc_list = []
    for a in archives:
        arc_list.append({
            "id": a.id,
            "phone": a.phone,
            "name": a.name,
            "city": a.city,
            "original_source_channel": a.original_source_channel,
            "original_source_store": a.original_source_store,
            "first_visit_date": a.first_visit_date,
            "last_visit_date": a.last_visit_date,
            "total_visit_count": a.total_visit_count,
            "customer_level": a.customer_level,
            "suggested_followup": a.suggested_followup,
            "remark": a.remark,
            "is_active": a.is_active,
            "created_at": a.created_at
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={
            "list": arc_list,
            "total": total,
            "page": page,
            "page_size": page_size
        }
    )


@router.post("/customer-archives", response_model=ApiResponse, summary="新增单个客户档案")
async def create_customer_archive(
    archive_data: CustomerArchiveCreate,
    db: Session = Depends(get_db)
):
    if not archive_data.phone and not archive_data.wechat_encrypted:
        raise HTTPException(status_code=400, detail="手机号和加密微信不能同时为空")
    
    phone_hash = hash_phone(archive_data.phone) if archive_data.phone else None
    
    existing = None
    if phone_hash:
        existing = db.query(CustomerArchive).filter(CustomerArchive.phone_hash == phone_hash).first()
    if not existing and archive_data.wechat_encrypted:
        existing = db.query(CustomerArchive).filter(
            CustomerArchive.wechat_encrypted == archive_data.wechat_encrypted
        ).first()
    
    if existing:
        raise HTTPException(status_code=400, detail="该客户档案已存在")
    
    archive = CustomerArchive(
        phone=archive_data.phone,
        phone_hash=phone_hash,
        wechat_encrypted=archive_data.wechat_encrypted,
        name=archive_data.name,
        city=archive_data.city,
        original_source_channel=archive_data.original_source_channel,
        original_source_store=archive_data.original_source_store,
        first_visit_date=archive_data.first_visit_date,
        last_visit_date=archive_data.last_visit_date,
        total_visit_count=archive_data.total_visit_count,
        customer_level=archive_data.customer_level,
        suggested_followup=archive_data.suggested_followup,
        remark=archive_data.remark,
        is_active=True
    )
    
    db.add(archive)
    db.commit()
    db.refresh(archive)
    
    return ApiResponse(
        code=0,
        message="创建成功",
        data={"id": archive.id, "phone": archive.phone, "name": archive.name}
    )


@router.post("/customer-archives/batch-import", response_model=ApiResponse, summary="批量导入客户档案（CRM历史客户）")
async def batch_import_customer_archives(
    import_data: CustomerArchiveBatchImport,
    db: Session = Depends(get_db)
):
    success_count = 0
    skip_count = 0
    error_count = 0
    errors = []
    
    for idx, cust in enumerate(import_data.customers):
        try:
            if not cust.phone and not cust.wechat_encrypted:
                skip_count += 1
                errors.append({"index": idx, "reason": "手机号和加密微信同时为空"})
                continue
            
            phone_hash = hash_phone(cust.phone) if cust.phone else None
            
            existing = None
            if phone_hash:
                existing = db.query(CustomerArchive).filter(CustomerArchive.phone_hash == phone_hash).first()
            if not existing and cust.wechat_encrypted:
                existing = db.query(CustomerArchive).filter(
                    CustomerArchive.wechat_encrypted == cust.wechat_encrypted
                ).first()
            
            if existing and not import_data.overwrite:
                skip_count += 1
                continue
            
            if existing and import_data.overwrite:
                existing.name = cust.name or existing.name
                existing.city = cust.city or existing.city
                if cust.original_source_channel:
                    existing.original_source_channel = cust.original_source_channel
                if cust.original_source_store:
                    existing.original_source_store = cust.original_source_store
                if cust.first_visit_date:
                    existing.first_visit_date = cust.first_visit_date
                if cust.last_visit_date:
                    existing.last_visit_date = cust.last_visit_date
                if cust.total_visit_count:
                    existing.total_visit_count = cust.total_visit_count
                if cust.customer_level:
                    existing.customer_level = cust.customer_level
                if cust.suggested_followup:
                    existing.suggested_followup = cust.suggested_followup
                if cust.remark:
                    existing.remark = (existing.remark or "") + "\n" + cust.remark
                success_count += 1
            else:
                archive = CustomerArchive(
                    phone=cust.phone,
                    phone_hash=phone_hash,
                    wechat_encrypted=cust.wechat_encrypted,
                    name=cust.name,
                    city=cust.city,
                    original_source_channel=cust.original_source_channel,
                    original_source_store=cust.original_source_store,
                    first_visit_date=cust.first_visit_date,
                    last_visit_date=cust.last_visit_date,
                    total_visit_count=cust.total_visit_count,
                    customer_level=cust.customer_level,
                    suggested_followup=cust.suggested_followup,
                    remark=cust.remark,
                    is_active=True
                )
                db.add(archive)
                success_count += 1
        
        except Exception as e:
            error_count += 1
            errors.append({"index": idx, "reason": str(e)})
    
    db.commit()
    
    return ApiResponse(
        code=0,
        message=f"批量导入完成：成功{success_count}条，跳过{skip_count}条，失败{error_count}条",
        data={
            "success_count": success_count,
            "skip_count": skip_count,
            "error_count": error_count,
            "errors": errors[:10]
        }
    )


@router.delete("/customer-archives/{archive_id}", response_model=ApiResponse, summary="停用客户档案")
async def deactivate_customer_archive(
    archive_id: int,
    db: Session = Depends(get_db)
):
    archive = db.query(CustomerArchive).filter(CustomerArchive.id == archive_id).first()
    if not archive:
        raise HTTPException(status_code=404, detail="客户档案不存在")
    
    archive.is_active = False
    db.commit()
    
    return ApiResponse(code=0, message="已停用")
