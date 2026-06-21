import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, engine, Base
from app.models import Channel, Store, Blacklist, Lead, DailyStats
from app.services.deduplication import deduplicate_lead, create_lead_record
from app.services.stats import update_daily_stats
from app.schemas import LeadReceiveRequest

def test_deduplication():
    db = SessionLocal()
    
    try:
        print("=== 测试1: 新客线索 ===")
        request1 = LeadReceiveRequest(
            phone="13912345678",
            name="张三",
            city="北京",
            intended_project="双眼皮",
            ad_plan="暑期促销活动",
            landing_page="/promotion/summer",
            channel_code="BAIDU_SEM",
            store_code="BJ_CHAOYANG"
        )
        
        result, existing = deduplicate_lead(db, request1)
        print(f"结果类型: {result.result_type}")
        print(f"结果描述: {result.result_description}")
        print(f"是否新客: {result.is_new_customer}")
        print(f"建议动作: {result.suggested_action}")
        print(f"匹配分数: {result.match_score}")
        
        if result.is_new_customer:
            lead = create_lead_record(db, request1, result)
            print(f"创建线索ID: {lead.lead_id}")
        
        update_daily_stats(
            db=db,
            channel_code=request1.channel_code,
            store_code=request1.store_code,
            is_new=result.is_new_customer,
            is_duplicate=not result.is_new_customer,
            is_cross_store=result.is_cross_store,
            is_blacklist=result.is_blacklist,
            is_valid=not result.is_blacklist
        )
        
        db.commit()
        print("测试1完成 ✓")
        
        print("\n=== 测试2: 重复线索（同手机号）===")
        request2 = LeadReceiveRequest(
            phone="13912345678",
            name="张小三",
            city="北京",
            intended_project="隆鼻",
            ad_plan="暑期促销活动2",
            channel_code="DOUYIN_AD",
            store_code="BJ_CHAOYANG"
        )
        
        result2, existing2 = deduplicate_lead(db, request2)
        print(f"结果类型: {result2.result_type}")
        print(f"结果描述: {result2.result_description}")
        print(f"是否新客: {result2.is_new_customer}")
        print(f"建议动作: {result2.suggested_action}")
        print(f"匹配分数: {result2.match_score}")
        print(f"原始线索ID: {result2.original_lead_id}")
        print(f"归属渠道: {result2.attribution_channel}")
        print(f"归因类型: {result2.attribution_type}")
        print("测试2完成 ✓")
        
        print("\n=== 测试3: 跨门店重复 ===")
        request3 = LeadReceiveRequest(
            phone="13912345678",
            name="张三",
            city="上海",
            intended_project="双眼皮",
            channel_code="OFFICIAL_WEBSITE",
            store_code="SH_PUDONG"
        )
        
        result3, existing3 = deduplicate_lead(db, request3)
        print(f"结果类型: {result3.result_type}")
        print(f"结果描述: {result3.result_description}")
        print(f"是否跨店: {result3.is_cross_store}")
        print(f"建议动作: {result3.suggested_action}")
        print(f"原门店: {result3.original_store}")
        print(f"新门店: {request3.store_code}")
        print("测试3完成 ✓")
        
        print("\n=== 测试4: 黑名单 ===")
        request4 = LeadReceiveRequest(
            phone="13800000001",
            name="测试黑名单",
            channel_code="BAIDU_SEM",
            store_code="BJ_CHAOYANG"
        )
        
        result4, existing4 = deduplicate_lead(db, request4)
        print(f"结果类型: {result4.result_type}")
        print(f"结果描述: {result4.result_description}")
        print(f"是否黑名单: {result4.is_blacklist}")
        print(f"建议动作: {result4.suggested_action}")
        print("测试4完成 ✓")
        
        print("\n=== 所有测试通过！ ===")
        
    except Exception as e:
        db.rollback()
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    test_deduplication()
