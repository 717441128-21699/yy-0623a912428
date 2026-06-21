from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.schemas import ApiResponse, ChannelCreate, StoreCreate, BlacklistCreate, DedupRuleCreate, DedupRuleUpdate
from app.models import Channel, Store, Blacklist, DedupRule
from app.services.deduplication import hash_phone

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


@router.get("/dedup-rules", response_model=ApiResponse, summary="判重规则列表")
async def get_dedup_rules(
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    query = db.query(DedupRule)
    if is_active is not None:
        query = query.filter(DedupRule.is_active == is_active)
    
    rules = query.order_by(DedupRule.id).all()
    
    rule_list = []
    for r in rules:
        rule_list.append({
            "id": r.id,
            "rule_name": r.rule_name,
            "rule_key": r.rule_key,
            "phone_weight": r.phone_weight,
            "wechat_weight": r.wechat_weight,
            "name_weight": r.name_weight,
            "city_weight": r.city_weight,
            "confirmed_threshold": r.confirmed_threshold,
            "suspected_threshold": r.suspected_threshold,
            "is_active": r.is_active,
            "description": r.description,
            "created_at": r.created_at,
            "updated_at": r.updated_at
        })
    
    return ApiResponse(
        code=0,
        message="success",
        data={"list": rule_list, "total": len(rule_list)}
    )


@router.post("/dedup-rules", response_model=ApiResponse, summary="新增判重规则")
async def create_dedup_rule(
    rule_data: DedupRuleCreate,
    db: Session = Depends(get_db)
):
    existing_key = db.query(DedupRule).filter(DedupRule.rule_key == rule_data.rule_key).first()
    if existing_key:
        raise HTTPException(status_code=400, detail="规则编码已存在")
    
    existing_name = db.query(DedupRule).filter(DedupRule.rule_name == rule_data.rule_name).first()
    if existing_name:
        raise HTTPException(status_code=400, detail="规则名称已存在")
    
    if rule_data.suspected_threshold >= rule_data.confirmed_threshold:
        raise HTTPException(status_code=400, detail="疑似阈值必须小于确认阈值")
    
    rule = DedupRule(
        rule_name=rule_data.rule_name,
        rule_key=rule_data.rule_key,
        phone_weight=rule_data.phone_weight,
        wechat_weight=rule_data.wechat_weight,
        name_weight=rule_data.name_weight,
        city_weight=rule_data.city_weight,
        confirmed_threshold=rule_data.confirmed_threshold,
        suspected_threshold=rule_data.suspected_threshold,
        description=rule_data.description,
        is_active=True
    )
    
    db.add(rule)
    db.commit()
    db.refresh(rule)
    
    return ApiResponse(
        code=0,
        message="创建成功",
        data={"rule_key": rule.rule_key}
    )


@router.put("/dedup-rules/{rule_key}", response_model=ApiResponse, summary="更新判重规则")
async def update_dedup_rule(
    rule_key: str,
    rule_data: DedupRuleUpdate,
    db: Session = Depends(get_db)
):
    rule = db.query(DedupRule).filter(DedupRule.rule_key == rule_key).first()
    if not rule:
        raise HTTPException(status_code=404, detail="判重规则不存在")
    
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
        data={"rule_key": rule.rule_key, "is_active": rule.is_active}
    )


@router.put("/dedup-rules/{rule_key}/activate", response_model=ApiResponse, summary="激活指定判重规则（同时停用其他规则）")
async def activate_dedup_rule(
    rule_key: str,
    db: Session = Depends(get_db)
):
    rule = db.query(DedupRule).filter(DedupRule.rule_key == rule_key).first()
    if not rule:
        raise HTTPException(status_code=404, detail="判重规则不存在")
    
    all_rules = db.query(DedupRule).all()
    for r in all_rules:
        r.is_active = (r.rule_key == rule_key)
    
    db.commit()
    
    return ApiResponse(
        code=0,
        message="已激活指定规则",
        data={"active_rule_key": rule_key}
    )
