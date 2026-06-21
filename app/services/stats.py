from datetime import datetime, date
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from app.models import DailyStats, Lead, LeadDuplicate, Channel, Store
from typing import List, Dict, Optional


def get_stat_date_str(dt: Optional[datetime] = None) -> str:
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y-%m-%d")


def update_daily_stats(db: Session, channel_code: str, store_code: Optional[str], 
                        is_new: bool, is_duplicate: bool, is_cross_store: bool, 
                        is_blacklist: bool, is_valid: bool, is_returning: bool = False):
    stat_date = get_stat_date_str()
    
    query = db.query(DailyStats).filter(
        DailyStats.stat_date == stat_date,
        DailyStats.channel_code == channel_code
    )
    
    if store_code is None:
        query = query.filter(DailyStats.store_code.is_(None))
    else:
        query = query.filter(DailyStats.store_code == store_code)
    
    stats = query.first()
    
    if not stats:
        stats = DailyStats(
            stat_date=stat_date,
            channel_code=channel_code,
            store_code=store_code,
            total_leads=0,
            new_leads=0,
            duplicate_leads=0,
            cross_store_leads=0,
            blacklist_leads=0,
            returning_leads=0,
            valid_leads=0,
            valid_rate=0.0,
            duplicate_rate=0.0
        )
        db.add(stats)
    
    stats.total_leads += 1
    if is_new:
        stats.new_leads += 1
    if is_duplicate:
        stats.duplicate_leads += 1
    if is_cross_store:
        stats.cross_store_leads += 1
    if is_blacklist:
        stats.blacklist_leads += 1
    if is_valid:
        stats.valid_leads += 1
    if is_returning:
        stats.returning_leads += 1
    
    if stats.total_leads > 0:
        stats.valid_rate = round(stats.valid_leads / stats.total_leads * 100, 2)
        stats.duplicate_rate = round(stats.duplicate_leads / stats.total_leads * 100, 2)
    
    db.flush()


def get_channel_stats(db: Session, start_date: Optional[str] = None, 
                       end_date: Optional[str] = None) -> List[Dict]:
    query = db.query(
        DailyStats.channel_code,
        func.sum(DailyStats.total_leads).label('total_leads'),
        func.sum(DailyStats.valid_leads).label('valid_leads'),
        func.sum(DailyStats.duplicate_leads).label('duplicate_leads'),
        func.sum(DailyStats.new_leads).label('new_leads'),
        func.sum(DailyStats.blacklist_leads).label('blacklist_leads'),
        func.sum(DailyStats.returning_leads).label('returning_leads'),
    )
    
    if start_date:
        query = query.filter(DailyStats.stat_date >= start_date)
    if end_date:
        query = query.filter(DailyStats.stat_date <= end_date)
    
    query = query.group_by(DailyStats.channel_code)
    results = query.all()
    
    channel_map = {c.channel_code: c.channel_name for c in db.query(Channel).all()}
    
    stats_list = []
    for row in results:
        total = row.total_leads or 0
        valid = row.valid_leads or 0
        dup = row.duplicate_leads or 0
        
        stats_list.append({
            "channel_code": row.channel_code,
            "channel_name": channel_map.get(row.channel_code, row.channel_code),
            "total_leads": total,
            "valid_leads": valid,
            "new_leads": row.new_leads or 0,
            "duplicate_leads": dup,
            "blacklist_leads": row.blacklist_leads or 0,
            "returning_leads": row.returning_leads or 0,
            "valid_rate": round(valid / total * 100, 2) if total > 0 else 0.0,
            "duplicate_rate": round(dup / total * 100, 2) if total > 0 else 0.0,
        })
    
    return sorted(stats_list, key=lambda x: x["total_leads"], reverse=True)


def get_store_stats(db: Session, start_date: Optional[str] = None, 
                     end_date: Optional[str] = None) -> List[Dict]:
    query = db.query(
        DailyStats.store_code,
        func.sum(DailyStats.total_leads).label('total_leads'),
        func.sum(DailyStats.duplicate_leads).label('duplicate_leads'),
        func.sum(DailyStats.cross_store_leads).label('cross_store_leads'),
    )
    
    if start_date:
        query = query.filter(DailyStats.stat_date >= start_date)
    if end_date:
        query = query.filter(DailyStats.stat_date <= end_date)
    
    query = query.filter(DailyStats.store_code.isnot(None))
    query = query.group_by(DailyStats.store_code)
    results = query.all()
    
    store_map = {s.store_code: {"name": s.store_name, "city": s.city} for s in db.query(Store).all()}
    
    stats_list = []
    for row in results:
        total = row.total_leads or 0
        dup = row.duplicate_leads or 0
        cross = row.cross_store_leads or 0
        
        store_info = store_map.get(row.store_code, {"name": row.store_code, "city": None})
        
        dup_sources = get_store_duplicate_sources(db, row.store_code, start_date, end_date)
        
        stats_list.append({
            "store_code": row.store_code,
            "store_name": store_info["name"],
            "city": store_info["city"],
            "total_leads": total,
            "duplicate_leads": dup,
            "cross_store_leads": cross,
            "duplicate_rate": round(dup / total * 100, 2) if total > 0 else 0.0,
            "duplicate_source_channels": dup_sources,
        })
    
    return sorted(stats_list, key=lambda x: x["total_leads"], reverse=True)


def get_store_duplicate_sources(db: Session, store_code: str, 
                                 start_date: Optional[str] = None,
                                 end_date: Optional[str] = None) -> List[Dict]:
    query = db.query(
        LeadDuplicate.original_channel,
        func.count(LeadDuplicate.id).label('count')
    ).filter(
        LeadDuplicate.duplicate_store == store_code
    )
    
    if start_date:
        query = query.filter(func.date(LeadDuplicate.created_at) >= start_date)
    if end_date:
        query = query.filter(func.date(LeadDuplicate.created_at) <= end_date)
    
    query = query.group_by(LeadDuplicate.original_channel)
    query = query.order_by(func.count(LeadDuplicate.id).desc())
    query = query.limit(5)
    
    results = query.all()
    
    channel_map = {c.channel_code: c.channel_name for c in db.query(Channel).all()}
    
    return [
        {
            "channel_code": row.original_channel,
            "channel_name": channel_map.get(row.original_channel, row.original_channel),
            "duplicate_count": row.count
        }
        for row in results
    ]


def get_daily_trend(db: Session, channel_code: Optional[str] = None,
                     store_code: Optional[str] = None,
                     start_date: Optional[str] = None,
                     end_date: Optional[str] = None) -> List[Dict]:
    query = db.query(
        DailyStats.stat_date,
        func.sum(DailyStats.total_leads).label('total_leads'),
        func.sum(DailyStats.new_leads).label('new_leads'),
        func.sum(DailyStats.duplicate_leads).label('duplicate_leads'),
        func.sum(DailyStats.valid_leads).label('valid_leads'),
        func.sum(DailyStats.cross_store_leads).label('cross_store_leads'),
        func.sum(DailyStats.returning_leads).label('returning_leads'),
    )
    
    if channel_code:
        query = query.filter(DailyStats.channel_code == channel_code)
    if store_code:
        query = query.filter(DailyStats.store_code == store_code)
    if start_date:
        query = query.filter(DailyStats.stat_date >= start_date)
    if end_date:
        query = query.filter(DailyStats.stat_date <= end_date)
    
    query = query.group_by(DailyStats.stat_date)
    query = query.order_by(DailyStats.stat_date)
    
    results = query.all()
    
    return [
        {
            "stat_date": row.stat_date,
            "total_leads": row.total_leads or 0,
            "new_leads": row.new_leads or 0,
            "duplicate_leads": row.duplicate_leads or 0,
            "valid_leads": row.valid_leads or 0,
            "cross_store_leads": row.cross_store_leads or 0,
            "returning_leads": row.returning_leads or 0,
            "valid_rate": round((row.valid_leads or 0) / (row.total_leads or 1) * 100, 2),
            "duplicate_rate": round((row.duplicate_leads or 0) / (row.total_leads or 1) * 100, 2),
        }
        for row in results
    ]
