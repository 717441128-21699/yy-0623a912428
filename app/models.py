from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Float, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class Channel(Base):
    __tablename__ = "channels"

    id = Column(Integer, primary_key=True, index=True)
    channel_code = Column(String(50), unique=True, index=True, nullable=False)
    channel_name = Column(String(100), nullable=False)
    channel_type = Column(String(50))
    priority = Column(Integer, default=100)
    is_active = Column(Boolean, default=True)
    description = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    leads = relationship("Lead", back_populates="channel_rel")


class Store(Base):
    __tablename__ = "stores"

    id = Column(Integer, primary_key=True, index=True)
    store_code = Column(String(50), unique=True, index=True, nullable=False)
    store_name = Column(String(100), nullable=False)
    city = Column(String(50))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    leads = relationship("Lead", back_populates="store_rel")


class Blacklist(Base):
    __tablename__ = "blacklist"

    id = Column(Integer, primary_key=True, index=True)
    black_type = Column(String(20), nullable=False)
    black_value = Column(String(255), nullable=False)
    phone_plain = Column(String(20))
    reason = Column(String(255))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_blacklist_type_value', 'black_type', 'black_value', unique=True),
    )


class DedupRule(Base):
    __tablename__ = "dedup_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_name = Column(String(100), unique=True, index=True, nullable=False)
    rule_key = Column(String(50), unique=True, index=True, nullable=False)

    phone_weight = Column(Float, default=60.0)
    wechat_weight = Column(Float, default=50.0)
    name_weight = Column(Float, default=10.0)
    city_weight = Column(Float, default=5.0)

    confirmed_threshold = Column(Float, default=80.0)
    suspected_threshold = Column(Float, default=40.0)

    is_active = Column(Boolean, default=True)
    description = Column(String(255))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Lead(Base):
    __tablename__ = "leads"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(String(64), unique=True, index=True, nullable=False)
    
    phone = Column(String(64), index=True)
    phone_hash = Column(String(64), index=True)
    wechat_encrypted = Column(String(255), index=True)
    name = Column(String(100))
    
    city = Column(String(50))
    intended_project = Column(String(200))
    ad_plan = Column(String(200))
    landing_page = Column(String(500))
    
    channel_code = Column(String(50), ForeignKey("channels.channel_code"))
    store_code = Column(String(50), ForeignKey("stores.store_code"))
    
    lead_status = Column(String(30), default="new")
    attribution_type = Column(String(20), default="first_touch")
    
    first_channel_code = Column(String(50))
    first_store_code = Column(String(50))
    first_lead_time = Column(DateTime(timezone=True))
    
    last_channel_code = Column(String(50))
    last_store_code = Column(String(50))
    last_lead_time = Column(DateTime(timezone=True))
    
    total_lead_count = Column(Integer, default=1)
    is_cross_store = Column(Boolean, default=False)
    is_returning = Column(Boolean, default=False)
    
    review_status = Column(String(20), default="pending")
    reviewed_by = Column(String(50))
    reviewed_at = Column(DateTime(timezone=True))
    
    remark = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    channel_rel = relationship("Channel", back_populates="leads")
    store_rel = relationship("Store", back_populates="leads")
    duplicates = relationship("LeadDuplicate", foreign_keys="LeadDuplicate.lead_id", back_populates="lead")


class LeadDuplicate(Base):
    __tablename__ = "lead_duplicates"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(String(64), ForeignKey("leads.lead_id"))
    duplicate_lead_id = Column(String(64), index=True)
    
    duplicate_type = Column(String(30))
    duplicate_reason = Column(String(255))
    duplicate_reason_code = Column(String(20))
    
    match_score = Column(Float, default=0.0)
    is_confirmed = Column(Boolean, default=False)
    confirmed_by = Column(String(50))
    confirmed_at = Column(DateTime(timezone=True))
    confirm_result = Column(String(20))
    confirm_remark = Column(Text)
    
    is_cross_store = Column(Boolean, default=False)
    original_store = Column(String(50))
    duplicate_store = Column(String(50))
    
    channel_conflict = Column(Boolean, default=False)
    original_channel = Column(String(50))
    duplicate_channel = Column(String(50))
    
    final_owner_channel = Column(String(50))
    final_owner_store = Column(String(50))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="duplicates", foreign_keys=[lead_id])


class LeadReview(Base):
    __tablename__ = "lead_reviews"

    id = Column(Integer, primary_key=True, index=True)
    duplicate_id = Column(Integer, index=True)
    lead_id = Column(String(64), index=True)
    
    reviewer = Column(String(50))
    review_result = Column(String(20))
    review_remark = Column(Text)
    
    final_owner_channel = Column(String(50))
    final_owner_store = Column(String(50))
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class ApiLog(Base):
    __tablename__ = "api_logs"

    id = Column(Integer, primary_key=True, index=True)
    request_id = Column(String(64), index=True)
    api_path = Column(String(255))
    method = Column(String(10))
    
    channel_code = Column(String(50), index=True)
    store_code = Column(String(50), index=True)
    
    request_summary = Column(String(500))
    request_params = Column(Text)
    response_data = Column(Text)
    
    status_code = Column(Integer)
    process_time_ms = Column(Integer)
    
    client_ip = Column(String(50))
    user_agent = Column(String(500))
    
    has_error = Column(Boolean, default=False)
    error_message = Column(Text)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_api_logs_created', 'created_at'),
    )


class DailyStats(Base):
    __tablename__ = "daily_stats"

    id = Column(Integer, primary_key=True, index=True)
    stat_date = Column(String(10), index=True)
    
    channel_code = Column(String(50), index=True)
    store_code = Column(String(50), index=True)
    
    total_leads = Column(Integer, default=0)
    new_leads = Column(Integer, default=0)
    duplicate_leads = Column(Integer, default=0)
    cross_store_leads = Column(Integer, default=0)
    blacklist_leads = Column(Integer, default=0)
    returning_leads = Column(Integer, default=0)
    valid_leads = Column(Integer, default=0)
    
    valid_rate = Column(Float, default=0.0)
    duplicate_rate = Column(Float, default=0.0)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_daily_stats_date_channel_store', 'stat_date', 'channel_code', 'store_code', unique=True),
    )
