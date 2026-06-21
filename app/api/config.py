from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List

from app.database import get_db
from app.schemas import ApiResponse, ChannelCreate, StoreCreate, BlacklistCreate
from app.models import Channel, Store, Blacklist

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
    existing = db.query(Blacklist).filter(
        Blacklist.black_type == blacklist_data.black_type,
        Blacklist.black_value == blacklist_data.black_value
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该黑名单已存在")
    
    black = Blacklist(
        black_type=blacklist_data.black_type,
        black_value=blacklist_data.black_value,
        reason=blacklist_data.reason,
        is_active=True
    )
    
    db.add(black)
    db.commit()
    db.refresh(black)
    
    return ApiResponse(
        code=0,
        message="添加成功",
        data={"id": black.id}
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
