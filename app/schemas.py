from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
import re


class LeadReceiveRequest(BaseModel):
    phone: Optional[str] = None
    wechat_encrypted: Optional[str] = None
    name: Optional[str] = None
    city: Optional[str] = None
    intended_project: Optional[str] = None
    ad_plan: Optional[str] = None
    landing_page: Optional[str] = None
    channel_code: str = Field(..., description="渠道编码")
    store_code: Optional[str] = None
    remark: Optional[str] = None
    external_lead_id: Optional[str] = None

    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        if not re.match(r'^1[3-9]\d{9}$', v):
            raise ValueError('手机号格式不正确')
        return v

    @field_validator('channel_code')
    @classmethod
    def validate_channel(cls, v):
        if not v or not v.strip():
            raise ValueError('渠道编码不能为空')
        return v.strip()


class LeadDeduplicateResponse(BaseModel):
    request_id: str
    lead_id: str
    result_type: str
    result_description: str
    suggested_action: str
    match_score: float = 0.0
    duplicate_reason_code: Optional[str] = None
    duplicate_reason: Optional[str] = None
    
    is_new_customer: bool = True
    is_blacklist: bool = False
    is_cross_store: bool = False
    
    attribution_channel: Optional[str] = None
    attribution_store: Optional[str] = None
    attribution_type: Optional[str] = None
    
    original_lead_id: Optional[str] = None
    original_channel: Optional[str] = None
    original_store: Optional[str] = None
    original_lead_time: Optional[datetime] = None
    
    conflict_duplicate_id: Optional[int] = None


class ApiResponse(BaseModel):
    code: int = 0
    message: str = "success"
    data: Optional[dict] = None
    request_id: Optional[str] = None


class ChannelCreate(BaseModel):
    channel_code: str
    channel_name: str
    channel_type: Optional[str] = None
    priority: int = 100
    description: Optional[str] = None


class StoreCreate(BaseModel):
    store_code: str
    store_name: str
    city: Optional[str] = None


class BlacklistCreate(BaseModel):
    black_type: str
    black_value: str
    reason: Optional[str] = None


class LeadQueryParams(BaseModel):
    channel_code: Optional[str] = None
    store_code: Optional[str] = None
    city: Optional[str] = None
    lead_status: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    page: int = 1
    page_size: int = 20


class DuplicateQueryParams(BaseModel):
    channel_code: Optional[str] = None
    store_code: Optional[str] = None
    is_confirmed: Optional[bool] = None
    is_cross_store: Optional[bool] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    page: int = 1
    page_size: int = 20


class ReviewConfirmRequest(BaseModel):
    duplicate_id: int
    review_result: str
    review_remark: Optional[str] = None
    reviewer: Optional[str] = None
    final_owner_channel: Optional[str] = None
    final_owner_store: Optional[str] = None


class StatsQueryParams(BaseModel):
    channel_code: Optional[str] = None
    store_code: Optional[str] = None
    stat_type: str = "daily"
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class StatsItem(BaseModel):
    stat_date: Optional[str] = None
    channel_code: Optional[str] = None
    store_code: Optional[str] = None
    total_leads: int = 0
    new_leads: int = 0
    duplicate_leads: int = 0
    cross_store_leads: int = 0
    blacklist_leads: int = 0
    valid_leads: int = 0
    valid_rate: float = 0.0
    duplicate_rate: float = 0.0


class ChannelStatsItem(BaseModel):
    channel_code: str
    channel_name: str
    total_leads: int = 0
    valid_leads: int = 0
    valid_rate: float = 0.0
    duplicate_rate: float = 0.0


class StoreStatsItem(BaseModel):
    store_code: str
    store_name: str
    city: Optional[str] = None
    total_leads: int = 0
    duplicate_leads: int = 0
    cross_store_leads: int = 0
    duplicate_rate: float = 0.0
    duplicate_source_channels: List[dict] = []
