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
    is_returning: bool = False

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
    is_returning: bool = False
    
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
    black_type: str = "phone"
    phone: Optional[str] = None
    wechat_encrypted: Optional[str] = None
    reason: Optional[str] = None

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


class DedupRuleCreate(BaseModel):
    rule_name: str
    rule_key: str
    phone_weight: float = 60.0
    wechat_weight: float = 50.0
    name_weight: float = 10.0
    city_weight: float = 5.0
    confirmed_threshold: float = 80.0
    suspected_threshold: float = 40.0
    description: Optional[str] = None


class DedupRuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    phone_weight: Optional[float] = None
    wechat_weight: Optional[float] = None
    name_weight: Optional[float] = None
    city_weight: Optional[float] = None
    confirmed_threshold: Optional[float] = None
    suspected_threshold: Optional[float] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class ReviewConfirmRequest(BaseModel):
    duplicate_id: int
    review_result: str = Field(..., description="confirmed/rejected/reassigned")
    review_remark: Optional[str] = None
    reviewer: Optional[str] = None
    final_owner_channel: Optional[str] = None
    final_owner_store: Optional[str] = None

    @field_validator('review_result')
    @classmethod
    def validate_review_result(cls, v):
        allowed = {"confirmed", "rejected", "reassigned"}
        if v not in allowed:
            raise ValueError(f'review_result 必须是 {allowed} 之一')
        return v
