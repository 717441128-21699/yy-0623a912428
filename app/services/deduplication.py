import hashlib
import uuid
from datetime import datetime
from typing import Optional, Tuple, List, Dict
from sqlalchemy.orm import Session
from app.models import Lead, LeadDuplicate, Blacklist, Channel, Store, DedupRule, CustomerArchive
from app.config import settings
from app.schemas import LeadReceiveRequest


DEFAULT_RULES = {
    "phone_weight": 60.0,
    "wechat_weight": 50.0,
    "name_weight": 10.0,
    "city_weight": 5.0,
    "confirmed_threshold": 80.0,
    "suspected_threshold": 40.0,
}


class DeduplicationResult:
    def __init__(self):
        self.result_type = "new_customer"
        self.result_description = "新客"
        self.suggested_action = "分配给对应门店跟进"
        self.match_score = 0.0
        self.duplicate_reason_code = None
        self.duplicate_reason = None
        self.is_new_customer = True
        self.is_blacklist = False
        self.is_cross_store = False
        self.is_returning = False
        self.attribution_channel = None
        self.attribution_store = None
        self.attribution_type = "first_touch"
        self.original_lead_id = None
        self.original_channel = None
        self.original_store = None
        self.original_lead_time = None
        self.original_source_channel = None
        self.original_source_store = None
        self.last_visit_date = None
        self.customer_level = None
        self.followup_suggestion = None
        self.conflict_duplicate_id = None


def hash_phone(phone: str) -> str:
    if not phone:
        return ""
    salted = f"{settings.LEAD_PHONE_HASH_SALT}:{phone}"
    return hashlib.sha256(salted.encode('utf-8')).hexdigest()


def generate_lead_id() -> str:
    return f"LEAD{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:8].upper()}"


def generate_request_id() -> str:
    return f"REQ{datetime.now().strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:10].upper()}"


def get_active_rules(db: Session) -> dict:
    rule = db.query(DedupRule).filter(DedupRule.status == "published").first()
    if rule:
        return {
            "phone_weight": rule.phone_weight,
            "wechat_weight": rule.wechat_weight,
            "name_weight": rule.name_weight,
            "city_weight": rule.city_weight,
            "confirmed_threshold": rule.confirmed_threshold,
            "suspected_threshold": rule.suspected_threshold,
            "rule_key": rule.rule_key,
            "version": rule.version,
        }
    fallback = db.query(DedupRule).filter(DedupRule.is_active == True).first()
    if fallback:
        return {
            "phone_weight": fallback.phone_weight,
            "wechat_weight": fallback.wechat_weight,
            "name_weight": fallback.name_weight,
            "city_weight": fallback.city_weight,
            "confirmed_threshold": fallback.confirmed_threshold,
            "suspected_threshold": fallback.suspected_threshold,
            "rule_key": fallback.rule_key,
            "version": fallback.version,
        }
    return DEFAULT_RULES.copy()


def get_rules_by_key(db: Session, rule_key: str) -> Optional[dict]:
    rule = db.query(DedupRule).filter(
        DedupRule.rule_key == rule_key
    ).order_by(DedupRule.version.desc()).first()
    if rule:
        return {
            "phone_weight": rule.phone_weight,
            "wechat_weight": rule.wechat_weight,
            "name_weight": rule.name_weight,
            "city_weight": rule.city_weight,
            "confirmed_threshold": rule.confirmed_threshold,
            "suspected_threshold": rule.suspected_threshold,
            "rule_key": rule.rule_key,
            "version": rule.version,
        }
    return None


def find_customer_archive(db: Session, phone: Optional[str], wechat_encrypted: Optional[str]) -> Optional[CustomerArchive]:
    if phone:
        phone_hash = hash_phone(phone)
        archive = db.query(CustomerArchive).filter(
            CustomerArchive.phone_hash == phone_hash,
            CustomerArchive.is_active == True
        ).first()
        if archive:
            return archive
    if wechat_encrypted:
        archive = db.query(CustomerArchive).filter(
            CustomerArchive.wechat_encrypted == wechat_encrypted,
            CustomerArchive.is_active == True
        ).first()
        if archive:
            return archive
    return None


def check_blacklist(db: Session, phone: Optional[str], wechat_encrypted: Optional[str]) -> Tuple[bool, Optional[str]]:
    if phone:
        phone_hash = hash_phone(phone)
        black = db.query(Blacklist).filter(
            Blacklist.black_type == "phone",
            Blacklist.black_value == phone_hash,
            Blacklist.is_active == True
        ).first()
        if black:
            return True, black.reason or "手机号在黑名单中"
    
    if wechat_encrypted:
        black = db.query(Blacklist).filter(
            Blacklist.black_type == "wechat",
            Blacklist.black_value == wechat_encrypted,
            Blacklist.is_active == True
        ).first()
        if black:
            return True, black.reason or "微信在黑名单中"
    
    return False, None


def find_matching_leads(db: Session, phone: Optional[str], wechat_encrypted: Optional[str]) -> List[Lead]:
    matches = []
    seen_ids = set()
    
    if phone:
        phone_hash = hash_phone(phone)
        phone_matches = db.query(Lead).filter(
            Lead.phone_hash == phone_hash
        ).all()
        for m in phone_matches:
            if m.lead_id not in seen_ids:
                matches.append(m)
                seen_ids.add(m.lead_id)
    
    if wechat_encrypted:
        wechat_matches = db.query(Lead).filter(
            Lead.wechat_encrypted == wechat_encrypted
        ).all()
        for m in wechat_matches:
            if m.lead_id not in seen_ids:
                matches.append(m)
                seen_ids.add(m.lead_id)
    
    return matches


def calculate_match_score(lead: Lead, request: LeadReceiveRequest, rules: dict) -> float:
    score = 0.0
    
    if request.phone and lead.phone_hash == hash_phone(request.phone):
        score += rules.get("phone_weight", 60.0)
    
    if request.wechat_encrypted and lead.wechat_encrypted == request.wechat_encrypted:
        score += rules.get("wechat_weight", 50.0)
    
    if request.name and lead.name and request.name == lead.name:
        score += rules.get("name_weight", 10.0)
    
    if request.city and lead.city and request.city == lead.city:
        score += rules.get("city_weight", 5.0)
    
    return min(score, 100.0)


def get_channel_priority(db: Session, channel_code: str) -> int:
    channel = db.query(Channel).filter(Channel.channel_code == channel_code).first()
    if channel:
        return channel.priority
    return settings.DEFAULT_CHANNEL_PRIORITY


def determine_attribution(db: Session, original_lead: Lead, new_channel: str, new_store: Optional[str]) -> Tuple[str, str, Optional[str], str]:
    first_channel = original_lead.first_channel_code or original_lead.channel_code
    first_store = original_lead.first_store_code or original_lead.store_code
    
    last_channel = original_lead.last_channel_code or original_lead.channel_code
    last_store = original_lead.last_store_code or original_lead.store_code
    
    first_priority = get_channel_priority(db, first_channel)
    new_priority = get_channel_priority(db, new_channel)
    
    attribution_type = "first_touch"
    attribution_channel = first_channel
    attribution_store = first_store
    
    if new_priority > first_priority:
        attribution_type = "priority_channel"
        attribution_channel = new_channel
        attribution_store = new_store
    elif original_lead.attribution_type == "last_touch":
        attribution_type = "last_touch"
        attribution_channel = last_channel
        attribution_store = last_store
    
    return attribution_type, attribution_channel, attribution_store, first_channel


def check_cross_store(original_store: Optional[str], new_store: Optional[str]) -> bool:
    if not original_store or not new_store:
        return False
    return original_store != new_store


def deduplicate_lead(db: Session, request: LeadReceiveRequest, custom_rules: Optional[dict] = None) -> Tuple[DeduplicationResult, Optional[Lead]]:
    result = DeduplicationResult()
    rules = custom_rules if custom_rules else get_active_rules(db)
    
    is_black, black_reason = check_blacklist(db, request.phone, request.wechat_encrypted)
    if is_black:
        result.result_type = "blacklist"
        result.result_description = "黑名单线索"
        result.suggested_action = "直接拦截，不进入分配流程"
        result.is_blacklist = True
        result.is_new_customer = False
        result.duplicate_reason_code = "BLACKLIST"
        result.duplicate_reason = black_reason
        result.match_score = 100.0
        return result, None
    
    archive = find_customer_archive(db, request.phone, request.wechat_encrypted)
    
    matching_leads = find_matching_leads(db, request.phone, request.wechat_encrypted)
    
    if not matching_leads and not archive:
        result.attribution_channel = request.channel_code
        result.attribution_store = request.store_code
        result.attribution_type = "first_touch"
        return result, None
    
    best_match = None
    best_score = 0.0
    
    for lead in matching_leads:
        score = calculate_match_score(lead, request, rules)
        if score > best_score:
            best_score = score
            best_match = lead
    
    result.match_score = best_score
    result.is_new_customer = False
    
    if best_match:
        result.original_lead_id = best_match.lead_id
        result.original_channel = best_match.channel_code
        result.original_store = best_match.store_code
        result.original_lead_time = best_match.created_at
        
        attribution_type, attr_channel, attr_store, first_channel = determine_attribution(
            db, best_match, request.channel_code, request.store_code
        )
        result.attribution_type = attribution_type
        result.attribution_channel = attr_channel
        result.attribution_store = attr_store
        
        is_cross = check_cross_store(best_match.store_code, request.store_code)
        result.is_cross_store = is_cross
        
        is_returning_customer = (
            request.is_returning or
            best_match.is_returning or
            best_match.lead_status in ("allocated", "reviewed") or
            (best_match.review_status == "confirmed")
        )
        result.is_returning = is_returning_customer
    else:
        result.attribution_channel = request.channel_code
        result.attribution_store = request.store_code
        result.attribution_type = "first_touch"
        is_cross = False
    
    if archive:
        result.is_returning = True
        result.original_source_channel = archive.original_source_channel
        result.original_source_store = archive.original_source_store
        result.last_visit_date = archive.last_visit_date
        result.customer_level = archive.customer_level
        result.followup_suggestion = archive.suggested_followup
        
        if not best_match:
            result.original_channel = archive.original_source_channel
            result.original_store = archive.original_source_store
            result.original_lead_time = archive.last_visit_date
    
    confirmed_threshold = rules.get("confirmed_threshold", 80.0)
    suspected_threshold = rules.get("suspected_threshold", 40.0)
    
    if archive:
        result.result_type = "returning_customer"
        result.result_description = "老客复询"
        suggestion = archive.suggested_followup or "关联原有客户档案，由原跟进人继续跟进"
        extra_info = []
        if archive.customer_level:
            extra_info.append(f"客户等级[{archive.customer_level}]")
        if archive.last_visit_date:
            extra_info.append(f"最近到店[{archive.last_visit_date.strftime('%Y-%m-%d')}]")
        if extra_info:
            suggestion = "、".join(extra_info) + "，" + suggestion
        result.suggested_action = suggestion
        result.duplicate_reason_code = "RETURNING"
        result.duplicate_reason = "老客户再次咨询"
        result.match_score = max(result.match_score, rules.get("phone_weight", 60.0))
    elif best_match and best_match.lead_status == "allocated" and not is_cross:
        result.result_type = "allocated"
        result.result_description = "已分配线索"
        result.suggested_action = "已有跟进人，转交原跟进人或协同处理"
        result.duplicate_reason_code = "ALLOCATED"
        result.duplicate_reason = "该线索已分配给其他人员跟进"
    elif result.is_returning and best_match and best_score >= rules.get("phone_weight", 60.0):
        result.result_type = "returning_customer"
        result.result_description = "老客复询"
        result.suggested_action = "关联原有客户档案，由原跟进人继续跟进"
        result.duplicate_reason_code = "RETURNING"
        result.duplicate_reason = "老客户再次咨询"
    elif is_cross:
        result.result_type = "cross_store_conflict"
        result.result_description = "跨门店重复"
        result.suggested_action = "触发跨店冲突流程，由总部或区域协调归属"
        result.duplicate_reason_code = "CROSS_STORE"
        result.duplicate_reason = f"原归属门店[{best_match.store_code if best_match else '未知'}]与新门店[{request.store_code}]冲突"
    elif best_score >= confirmed_threshold:
        result.result_type = "confirmed_duplicate"
        result.result_description = "确认重复"
        result.suggested_action = "合并到原有线索，更新末触信息"
        result.duplicate_reason_code = "CONFIRMED_DUP"
        result.duplicate_reason = "手机号或微信高度匹配"
    elif best_score >= suspected_threshold:
        result.result_type = "suspected_duplicate"
        result.result_description = "疑似重复"
        result.suggested_action = "人工复核确认后再处理"
        result.duplicate_reason_code = "SUSPECTED_DUP"
        result.duplicate_reason = "部分信息匹配，需人工确认"
    elif result.is_returning:
        result.result_type = "returning_customer"
        result.result_description = "老客复询"
        result.suggested_action = "关联原有客户档案，继续跟进"
        result.duplicate_reason_code = "RETURNING"
        result.duplicate_reason = "老客户再次咨询"
    
    return result, best_match


def create_lead_record(db: Session, request: LeadReceiveRequest, result: DeduplicationResult) -> Lead:
    lead_id = generate_lead_id()
    phone_hash = hash_phone(request.phone) if request.phone else None
    
    now = datetime.now()
    
    lead = Lead(
        lead_id=lead_id,
        phone=request.phone,
        phone_hash=phone_hash,
        wechat_encrypted=request.wechat_encrypted,
        name=request.name,
        city=request.city,
        intended_project=request.intended_project,
        ad_plan=request.ad_plan,
        landing_page=request.landing_page,
        channel_code=request.channel_code,
        store_code=request.store_code,
        lead_status="new" if result.is_new_customer else "duplicate",
        attribution_type=result.attribution_type,
        first_channel_code=result.attribution_channel or request.channel_code,
        first_store_code=result.attribution_store or request.store_code,
        first_lead_time=now,
        last_channel_code=request.channel_code,
        last_store_code=request.store_code,
        last_lead_time=now,
        total_lead_count=1,
        is_cross_store=result.is_cross_store,
        is_returning=request.is_returning or result.is_returning,
        remark=request.remark
    )
    
    db.add(lead)
    db.flush()
    return lead


def update_existing_lead(db: Session, existing_lead: Lead, request: LeadReceiveRequest, result: DeduplicationResult) -> Lead:
    existing_lead.total_lead_count += 1
    existing_lead.last_channel_code = request.channel_code
    existing_lead.last_store_code = request.store_code
    existing_lead.last_lead_time = datetime.now()
    
    if result.is_cross_store:
        existing_lead.is_cross_store = True
    
    if result.is_returning:
        existing_lead.is_returning = True
    
    if request.intended_project and not existing_lead.intended_project:
        existing_lead.intended_project = request.intended_project
    
    if request.city and not existing_lead.city:
        existing_lead.city = request.city
    
    if request.name and not existing_lead.name:
        existing_lead.name = request.name
    
    db.flush()
    return existing_lead


def create_duplicate_record(db: Session, original_lead: Lead, new_lead_id: str, 
                             result: DeduplicationResult, request: LeadReceiveRequest) -> LeadDuplicate:
    dup = LeadDuplicate(
        lead_id=original_lead.lead_id,
        duplicate_lead_id=new_lead_id,
        duplicate_type=result.result_type,
        duplicate_reason=result.duplicate_reason,
        duplicate_reason_code=result.duplicate_reason_code,
        match_score=result.match_score,
        is_confirmed=False,
        is_cross_store=result.is_cross_store,
        original_store=original_lead.store_code,
        duplicate_store=request.store_code,
        channel_conflict=(original_lead.channel_code != request.channel_code),
        original_channel=original_lead.channel_code,
        duplicate_channel=request.channel_code
    )
    
    db.add(dup)
    db.flush()
    
    result.conflict_duplicate_id = dup.id
    return dup
