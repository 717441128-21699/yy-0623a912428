import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from app.database import SessionLocal, engine, Base
from app.models import Channel, Store, Blacklist, DedupRule, CustomerArchive
from app.services.deduplication import hash_phone


def init_seed_data():
    print("创建数据库表...")
    Base.metadata.create_all(bind=engine)
    print("数据库表创建完成！")
    
    db = SessionLocal()
    
    try:
        print("\n开始初始化种子数据...")
        
        channels = [
            {"channel_code": "OFFICIAL_WEBSITE", "channel_name": "官网表单", "channel_type": "organic", "priority": 80, "description": "官方网站在线咨询表单"},
            {"channel_code": "BAIDU_SEM", "channel_name": "百度SEM", "channel_type": "paid", "priority": 120, "description": "百度搜索引擎付费推广"},
            {"channel_code": "DOUYIN_AD", "channel_name": "抖音广告", "channel_type": "paid", "priority": 130, "description": "抖音信息流广告投放"},
            {"channel_code": "WECHAT_WORK", "channel_name": "企微客服", "channel_type": "social", "priority": 90, "description": "企业微信客服接待"},
            {"channel_code": "CRM_IMPORT", "channel_name": "CRM导入", "channel_type": "offline", "priority": 70, "description": "线下活动/老客导入"},
            {"channel_code": "MINI_PROGRAM", "channel_name": "小程序预约", "channel_type": "mini_program", "priority": 85, "description": "微信小程序预约咨询"},
            {"channel_code": "XHS_AD", "channel_name": "小红书广告", "channel_type": "paid", "priority": 115, "description": "小红书信息流广告"},
            {"channel_code": "MEITUAN", "channel_name": "美团", "channel_type": "platform", "priority": 95, "description": "美团平台到店咨询"},
        ]
        
        for ch_data in channels:
            existing = db.query(Channel).filter(Channel.channel_code == ch_data["channel_code"]).first()
            if not existing:
                channel = Channel(**ch_data)
                db.add(channel)
                print(f"  新增渠道: {ch_data['channel_code']} - {ch_data['channel_name']}")
            else:
                print(f"  渠道已存在: {ch_data['channel_code']}")
        
        stores = [
            {"store_code": "BJ_CHAOYANG", "store_name": "北京朝阳旗舰店", "city": "北京"},
            {"store_code": "BJ_HAIDIAN", "store_name": "北京海淀分院", "city": "北京"},
            {"store_code": "SH_PUDONG", "store_name": "上海浦东旗舰店", "city": "上海"},
            {"store_code": "SH_XUHUI", "store_name": "上海徐汇分院", "city": "上海"},
            {"store_code": "GZ_TIANHE", "store_name": "广州天河旗舰店", "city": "广州"},
            {"store_code": "SZ_NANSHAN", "store_name": "深圳南山旗舰店", "city": "深圳"},
            {"store_code": "CD_JINJIANG", "store_name": "成都锦江分院", "city": "成都"},
            {"store_code": "HZ_XIHU", "store_name": "杭州西湖分院", "city": "杭州"},
        ]
        
        for st_data in stores:
            existing = db.query(Store).filter(Store.store_code == st_data["store_code"]).first()
            if not existing:
                store = Store(**st_data)
                db.add(store)
                print(f"  新增门店: {st_data['store_code']} - {st_data['store_name']}")
            else:
                print(f"  门店已存在: {st_data['store_code']}")
        
        blacklist_phones = ["13800000001", "13800000002"]
        for phone in blacklist_phones:
            phone_hash = hash_phone(phone)
            existing = db.query(Blacklist).filter(
                Blacklist.black_type == "phone",
                Blacklist.black_value == phone_hash
            ).first()
            if not existing:
                black = Blacklist(
                    black_type="phone",
                    black_value=phone_hash,
                    phone_plain=phone,
                    reason="骚扰电话/恶意投诉用户"
                )
                db.add(black)
                print(f"  新增黑名单手机号: {phone}")
            else:
                print(f"  黑名单手机号已存在: {phone}")
        
        dedup_rules = [
            {
                "rule_name": "标准判重规则 V1",
                "rule_key": "standard",
                "version": 1,
                "phone_weight": 60.0,
                "wechat_weight": 50.0,
                "name_weight": 10.0,
                "city_weight": 5.0,
                "confirmed_threshold": 80.0,
                "suspected_threshold": 40.0,
                "description": "默认标准判重策略，手机号权重最高",
                "status": "published",
                "is_active": True,
                "published_by": "init",
                "published_at": datetime.now()
            },
            {
                "rule_name": "宽松判重规则 V1",
                "rule_key": "loose",
                "version": 1,
                "phone_weight": 40.0,
                "wechat_weight": 30.0,
                "name_weight": 15.0,
                "city_weight": 10.0,
                "confirmed_threshold": 70.0,
                "suspected_threshold": 30.0,
                "description": "宽松策略，更容易触发疑似重复，适合试运营期",
                "status": "draft",
                "is_active": False
            },
            {
                "rule_name": "严格判重规则 V1",
                "rule_key": "strict",
                "version": 1,
                "phone_weight": 70.0,
                "wechat_weight": 60.0,
                "name_weight": 5.0,
                "city_weight": 3.0,
                "confirmed_threshold": 90.0,
                "suspected_threshold": 50.0,
                "description": "严格策略，只拦截高置信度重复，减少误判",
                "status": "draft",
                "is_active": False
            },
        ]
        
        for rule_data in dedup_rules:
            existing = db.query(DedupRule).filter(
                DedupRule.rule_key == rule_data["rule_key"],
                DedupRule.version == rule_data["version"]
            ).first()
            if not existing:
                rule = DedupRule(**rule_data)
                db.add(rule)
                print(f"  新增判重规则: {rule_data['rule_key']} V{rule_data['version']} - {rule_data['rule_name']} [{rule_data['status']}]")
            else:
                print(f"  判重规则已存在: {rule_data['rule_key']} V{rule_data['version']}")
        
        sample_customers = [
            {
                "phone": "13800009999",
                "name": "王美丽",
                "city": "北京",
                "original_source_channel": "OFFICIAL_WEBSITE",
                "original_source_store": "BJ_CHAOYANG",
                "first_visit_date": datetime.now() - timedelta(days=365),
                "last_visit_date": datetime.now() - timedelta(days=30),
                "total_visit_count": 5,
                "customer_level": "VIP",
                "suggested_followup": "高意向VIP客户，由原跟进人李医生继续回访，本月有复购双眼皮活动可推荐",
                "remark": "2024年埋线双眼皮，反馈良好，咨询过祛斑项目"
            },
            {
                "phone": "13800008888",
                "name": "李芳芳",
                "city": "上海",
                "original_source_channel": "CRM_IMPORT",
                "original_source_store": "SH_PUDONG",
                "first_visit_date": datetime.now() - timedelta(days=540),
                "last_visit_date": datetime.now() - timedelta(days=90),
                "total_visit_count": 2,
                "customer_level": "普通",
                "suggested_followup": "老客唤醒，上次做了水光针，可推季度保养套餐",
                "remark": "2023年水光针2次"
            },
        ]
        
        for cust in sample_customers:
            ph = cust.pop("phone")
            phone_hash = hash_phone(ph)
            existing = db.query(CustomerArchive).filter(CustomerArchive.phone_hash == phone_hash).first()
            if not existing:
                archive = CustomerArchive(
                    phone=ph,
                    phone_hash=phone_hash,
                    **cust
                )
                db.add(archive)
                print(f"  预置客户档案: {ph} - {cust.get('name')} [{cust.get('customer_level')}]")
            else:
                print(f"  客户档案已存在: {ph}")
        
        db.commit()
        print("\n种子数据初始化完成！")
        
    except Exception as e:
        db.rollback()
        print(f"初始化失败: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    init_seed_data()
