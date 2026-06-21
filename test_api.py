import urllib.request
import urllib.error
import json
import time

BASE = "http://127.0.0.1:8000/api/v1"

passed = 0
failed = 0

def post(path, data):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=json.dumps(data).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return None, {"detail": str(e)}

def get(path):
    req = urllib.request.Request(f"{BASE}{path}")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return None, {"detail": str(e)}

def put(path, data=None):
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=(json.dumps(data).encode("utf-8") if data else None),
        headers={"Content-Type": "application/json"} if data else {},
        method="PUT"
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode("utf-8"))
    except Exception as e:
        return None, {"detail": str(e)}

def run(title, fn):
    global passed, failed
    print("\n" + "=" * 60)
    print(f"测试{title}")
    print("=" * 60)
    try:
        ok, msg = fn()
        if ok:
            print(f"  ✅ 通过")
            passed += 1
        else:
            print(f"  ❌ 失败: {msg}")
            failed += 1
    except Exception as e:
        print(f"  ❌ 异常: {e}")
        import traceback
        traceback.print_exc()
        failed += 1


def t1():
    """规则版本管理：新建V2草稿→修改→发布→新线索按V2生效"""
    # 1. 查看当前规则，确认standard V1为published
    s, r = get("/config/dedup-rules?status=published")
    if s != 200 or r["data"]["total"] != 1 or r["data"]["list"][0]["rule_key"] != "standard":
        return False, f"当前published规则非standard V1，total={r.get('data',{}).get('total')}"
    print(f"  当前published规则: {r['data']['list'][0]['rule_key']} V{r['data']['list'][0]['version']}")

    # 2. 新建 strict 的 V2 草稿（调高手机权重，降低阈值）
    s, r = post("/config/dedup-rules", {
        "rule_name": "严格判重规则 V2 - 调宽手机",
        "rule_key": "strict",
        "phone_weight": 90.0,
        "wechat_weight": 60.0,
        "name_weight": 5.0,
        "city_weight": 2.0,
        "confirmed_threshold": 85.0,
        "suspected_threshold": 45.0,
        "description": "strict V2 草稿"
    })
    if s != 200:
        return False, f"创建strict V2失败: {r}"
    ver = r["data"]["version"]
    print(f"  新建strict草稿: V{ver} status={r['data']['status']}")

    # 3. 修改strict V2，降低手机权重到80
    s, r = put("/config/dedup-rules/strict", {
        "phone_weight": 80.0,
        "confirmed_threshold": 82.0
    })
    if s != 200:
        return False, f"修改strict V2失败: {r}"
    print(f"  修改strict V2完成")

    # 4. 发布strict V2
    s, r = put(f"/config/dedup-rules/strict/publish?version={ver}&published_by=tester")
    if s != 200:
        return False, f"发布strict V2失败: {r}"
    print(f"  已发布 strict V{ver}")

    # 5. 确认 published 规则已切换
    s, r = get("/config/dedup-rules?status=published")
    if s != 200 or r["data"]["list"][0]["rule_key"] != "strict":
        return False, f"发布后published规则不是strict: {r}"
    print(f"  当前published规则: {r['data']['list'][0]['rule_key']} V{r['data']['list'][0]['version']}")

    # 6. 新线索判重：手机权重80，纯手机匹配应该超过确认阈值82 → 应是 confirmed_duplicate
    # 先插入第一个
    s, r = post("/leads/receive", {
        "phone": "13999999991",
        "name": "测试V2",
        "channel_code": "BAIDU_SEM",
        "store_code": "BJ_CHAOYANG"
    })
    if s != 200 or r["data"]["result_type"] != "new_customer":
        return False, f"第1条应该是new_customer，实际: {r['data'].get('result_type')}"

    s, r = post("/leads/receive", {
        "phone": "13999999991",
        "name": "测试V2不同名字",
        "channel_code": "DOUYIN_AD",
        "store_code": "BJ_CHAOYANG"
    })
    res_type = r["data"].get("result_type")
    score = r["data"].get("match_score")
    print(f"  V2发布后结果: {res_type} score={score}")
    # 手机80权重，姓名不匹配 → 80 < 82 确认阈值 → 疑似
    if res_type != "suspected_duplicate" or score != 80.0:
        return False, f"V2下纯手机80分应<确认82阈值，期望suspected_duplicate，实际{res_type} score={score}"

    # 7. 切回 standard V1，让后面测试用默认规则
    s, r = put("/config/dedup-rules/standard/publish?published_by=tester")
    if s != 200:
        return False, f"切回standard失败: {r}"
    print(f"  已切回 standard published")

    return True, ""


def t2():
    """老客档案识别：预置VIP客户王美丽（13800009999）再咨询→带原来源+最近到店+建议跟进"""
    s, r = post("/leads/receive", {
        "phone": "13800009999",
        "name": "王美丽",
        "city": "北京",
        "intended_project": "祛斑",
        "channel_code": "XHS_AD",
        "store_code": "BJ_CHAOYANG"
    })
    if s != 200:
        return False, f"接口失败 {r}"
    d = r["data"]
    print(f"  结果类型: {d['result_type']}")
    print(f"  是否老客复询: {d['is_returning']}")
    print(f"  原客户来源渠道: {d['original_source_channel']}")
    print(f"  原客户来源门店: {d['original_source_store']}")
    print(f"  客户等级: {d['customer_level']}")
    print(f"  跟进建议: {d['followup_suggestion'][:30]}...")
    print(f"  建议动作(含最近到店): {d['suggested_action'][:50]}...")

    if d["result_type"] != "returning_customer":
        return False, f"期望returning_customer，实际{d['result_type']}"
    if d["original_source_channel"] != "OFFICIAL_WEBSITE":
        return False, f"原渠道应为OFFICIAL_WEBSITE"
    if d["original_source_store"] != "BJ_CHAOYANG":
        return False, f"原门店应为BJ_CHAOYANG"
    if d["customer_level"] != "VIP":
        return False, f"客户等级应为VIP"
    if not d["last_visit_date"]:
        return False, f"最近到店日期为空"
    if "最近到店" not in d["suggested_action"]:
        return False, f"建议动作中应包含最近到店信息"
    return True, ""


def t3():
    """批量导入CRM历史客户，再咨询同一手机返回老客复询"""
    # 导入3个客户，1个和预置王美丽重复
    custs = [
        {
            "phone": "13600001111",
            "name": "赵敏",
            "city": "广州",
            "original_source_channel": "MEITUAN",
            "original_source_store": "GZ_TIANHE",
            "customer_level": "金卡",
            "suggested_followup": "美团来源老客，推荐本月隆胸套餐",
            "total_visit_count": 3
        },
        {
            "phone": "13800009999",
            "name": "王美丽(更新)",
            "city": "北京",
            "customer_level": "钻石"
        },
        {
            "phone": "13600002222",
            "name": "周芷若",
            "original_source_channel": "MINI_PROGRAM",
            "original_source_store": "CD_JINJIANG",
            "suggested_followup": "小程序预约老客，本月生日优惠可触达"
        },
    ]
    s, r = post("/config/customer-archives/batch-import", {
        "customers": custs,
        "overwrite": False
    })
    if s != 200:
        return False, f"导入失败 {r}"
    d = r["data"]
    print(f"  导入结果: 成功{d['success_count']} 跳过{d['skip_count']} 失败{d['error_count']}")
    if d["success_count"] != 2 or d["skip_count"] != 1:
        return False, f"期望成功2跳过1，实际{d}"

    # 赵敏再次咨询
    s, r = post("/leads/receive", {
        "phone": "13600001111",
        "name": "赵敏",
        "channel_code": "BAIDU_SEM",
        "store_code": "GZ_TIANHE"
    })
    d = r["data"]
    print(f"  赵敏再咨询结果: {d['result_type']} 来源:{d['original_source_channel']} 等级:{d['customer_level']}")
    if d["result_type"] != "returning_customer":
        return False, f"赵敏应为returning_customer，实际{d['result_type']}"
    if d["original_source_channel"] != "MEITUAN":
        return False, f"赵敏原渠道应为MEITUAN"
    if "隆胸套餐" not in d["suggested_action"]:
        return False, f"建议动作应包含隆胸套餐提示"

    # overwrite模式更新王美丽
    s, r = post("/config/customer-archives/batch-import", {
        "customers": [custs[1]],
        "overwrite": True
    })
    if s != 200 or r["data"]["success_count"] != 1:
        return False, f"覆盖更新失败 {r}"
    print(f"  王美丽覆盖更新完成")
    return True, ""


def t4():
    """复核待办：待办统计+待办列表按条件筛选"""
    # 先造N条待办
    phones = [f"137111100{i:02d}" for i in range(6)]
    for ph in phones[:3]:
        # 同一手机号两次进不同渠道/门店 → 产生冲突
        post("/leads/receive", {
            "phone": ph, "name": "张重复", "channel_code": "BAIDU_SEM", "store_code": "BJ_CHAOYANG"
        })
        post("/leads/receive", {
            "phone": ph, "name": "张重复", "channel_code": "DOUYIN_AD", "store_code": "SH_PUDONG"
        })

    # 查待办统计
    s, r = get("/leads/duplicates/todo-summary")
    if s != 200:
        return False, f"待办统计失败 {r}"
    d = r["data"]
    print(f"  待办总数: {d['total_pending']}")
    print(f"  按类型: {d['by_duplicate_type']}")
    print(f"  按渠道数: {len(d['by_channel'])}")
    if d["total_pending"] < 3:
        return False, f"待办数太少，至少3条，实际{d['total_pending']}"

    # 待办列表按 cross_store 筛选
    s, r = get("/leads/duplicates/todo?is_cross_store=true&page_size=20")
    if s != 200:
        return False, f"待办列表失败 {r}"
    cross_count = r["data"]["total"]
    print(f"  跨店冲突待办数: {cross_count}")
    if cross_count < 3:
        return False, f"跨店冲突至少3条"

    # 待办列表按 duplicate_type=suspected_duplicate 筛选
    s, r = get("/leads/duplicates/todo?duplicate_type=suspected_duplicate&page_size=20")
    sus_count = r["data"]["total"]
    print(f"  疑似重复待办数: {sus_count}")
    return True, ""


def t5():
    """批量复核：多选几条→批量改归属→所有记录同步最终归属一致"""
    # 先拿几条待办ID（跨店冲突，因为standard规则下同名同手机跨店优先）
    s, r = get("/leads/duplicates/todo?is_cross_store=true&page_size=10")
    todos = r["data"]["list"]
    if len(todos) < 2:
        return False, f"待办太少，至少2条才能测批量，实际{len(todos)}"
    ids = [t["id"] for t in todos[:2]]
    print(f"  待处理ID: {ids} (duplicate_type={todos[0]['duplicate_type']})")

    # 批量改归属到 DOUYIN_AD / SZ_NANSHAN
    s, r = post("/leads/duplicates/batch-review", {
        "duplicate_ids": ids,
        "review_result": "reassigned",
        "reviewer": "批量处理主管",
        "final_owner_channel": "DOUYIN_AD",
        "final_owner_store": "SZ_NANSHAN",
        "review_remark": "统一归属抖音广告深圳店"
    })
    if s != 200:
        return False, f"批量复核失败 {r}"
    d = r["data"]
    print(f"  批量复核结果: 成功{d['success_count']} 跳过{d['skipped_count']}")
    if d["success_count"] != 2:
        return False, f"期望成功2条，实际{d['success_count']}"

    # 查看重复冲突列表，确认这些 ID 的 confirm_result 和 final_owner 一致
    s, r = get("/leads/duplicates/list?confirm_result=reassigned&page_size=10")
    results = r["data"]["list"]
    for item in results:
        if item["id"] in ids:
            print(f"  ID{item['id']}: 结果={item['confirm_result']} 最终渠道={item['final_owner_channel']} 最终门店={item['final_owner_store']}")
            if item["final_owner_channel"] != "DOUYIN_AD" or item["final_owner_store"] != "SZ_NANSHAN":
                return False, f"ID{item['id']}最终归属不一致"
            if item["confirm_result"] != "reassigned":
                return False, f"ID{item['id']}复核结果不是reassigned"

    # 查看某条线索详情，确认 review_status=reassigned 且 final_owner 一致
    sample_lead_id = results[0]["lead_id"]
    s, r = get(f"/leads/{sample_lead_id}")
    ld = r["data"]
    print(f"  线索详情 {sample_lead_id}: review_status={ld['review_status']} final_ch={ld['final_owner_channel']} final_st={ld['final_owner_store']}")
    if ld["review_status"] != "reassigned":
        return False, f"线索review_status应为reassigned"
    if ld["final_owner_channel"] != "DOUYIN_AD" or ld["final_owner_store"] != "SZ_NANSHAN":
        return False, f"线索final_owner和批量复核结果不一致"
    return True, ""


def t6():
    """给已有线索打老客标签→同手机号后续进来识别为老客复询"""
    # 新线索
    s, r = post("/leads/receive", {
        "phone": "13500006666",
        "name": "陈测试",
        "city": "杭州",
        "channel_code": "MEITUAN",
        "store_code": "HZ_XIHU"
    })
    lead_id = r["data"]["lead_id"]
    print(f"  新建线索ID: {lead_id}")

    # 同号再进一次，产生重复，但此时还不是老客
    s, r = post("/leads/receive", {
        "phone": "13500006666",
        "name": "陈测试",
        "channel_code": "DOUYIN_AD",
        "store_code": "HZ_XIHU"
    })
    rt1 = r["data"]["result_type"]
    print(f"  未打标签前重复结果: {rt1}")

    # 给第一条线索打老客标签，同时指定原来源和建议
    s, r = post(f"/leads/{lead_id}/mark-returning", {
        "is_returning": True,
        "operator": "运营A",
        "original_source_channel": "MEITUAN",
        "original_source_store": "HZ_XIHU",
        "suggested_followup": "美团到店老客，3个月前做了热玛吉，推荐热玛吉年度保养",
        "remark": "后台批量打标"
    })
    if s != 200 or r["data"]["is_returning"] != True:
        return False, f"打老客标签失败 {r}"
    print(f"  已打老客标签")

    # 同号第三次进来，应返回老客复询
    s, r = post("/leads/receive", {
        "phone": "13500006666",
        "name": "陈测试",
        "channel_code": "XHS_AD",
        "store_code": "HZ_XIHU"
    })
    d = r["data"]
    print(f"  打标签后再咨询: {d['result_type']} is_returning={d['is_returning']}")
    if d["result_type"] not in ("returning_customer", "allocated"):
        return False, f"打标后期望老客/已分配，实际{d['result_type']}"
    return True, ""


def t7():
    """规则试算：自定义规则、指定已保存规则、默认published规则三种模式对比"""
    samples = [
        {"phone": "13922223331", "name": "试算A", "channel_code": "BAIDU_SEM", "store_code": "BJ_CHAOYANG"},
        {"phone": "13922223332", "name": "试算B", "channel_code": "MEITUAN", "store_code": "SH_PUDONG"},
        {"phone": "13800008888", "name": "李芳芳", "channel_code": "XHS_AD", "store_code": "SH_PUDONG"},
    ]
    # 先让 samples[0] 进库，这样 samples[0] 作为重复线索
    post("/leads/receive", samples[0])

    # 1. 默认published（standard V1）试算
    s, r = post("/config/dedup-rules/tryout", {
        "sample_leads": samples
    })
    if s != 200:
        return False, f"试算失败 {r}"
    d = r["data"]
    print(f"  默认published试算来源: {d['rule_info']['source']}")
    print(f"  结果分布: {d['result_summary']}")
    if d["rule_info"]["source"] != "published_default" or d["rule_info"]["rule_key"] != "standard":
        return False, f"默认试算应为 published standard"

    # 2. 指定 strict 规则试算（strict当前是published切换过的，应该有2个版本，取最高的）
    s, r = post("/config/dedup-rules/tryout", {
        "rule_key": "strict",
        "sample_leads": samples
    })
    if s != 200:
        return False, f"指定strict试算失败 {r}"
    print(f"  指定strict试算来源: {r['data']['rule_info']['source']} rule_key={r['data']['rule_info']['rule_key']}")
    if r["data"]["rule_info"]["source"] != "saved_rule" or r["data"]["rule_info"]["rule_key"] != "strict":
        return False, f"指定strict应为 saved_rule"

    # 3. 自定义规则（手机权重100，确认阈值99），纯手机匹配=100分>99→confirmed_duplicate
    s, r = post("/config/dedup-rules/tryout", {
        "custom_rules": {
            "rule_name": "手机唯一规则",
            "rule_key": "phone_only_try",
            "phone_weight": 100.0,
            "wechat_weight": 80.0,
            "name_weight": 0.0,
            "city_weight": 0.0,
            "confirmed_threshold": 99.0,
            "suspected_threshold": 50.0,
        },
        "sample_leads": samples
    })
    if s != 200:
        return False, f"自定义规则试算失败 {r}"
    results = r["data"]["results"]
    phone_only_summary = r["data"]["result_summary"]
    print(f"  自定义手机100权重结果分布: {phone_only_summary}")
    # sample[0] 已存在，手机权重100 → confirmed_duplicate
    s0_result = [x for x in results if x["sample_phone"] == "13922223331"][0]
    if s0_result["result_type"] != "confirmed_duplicate" or s0_result["match_score"] != 100.0:
        return False, f"自定义100权重手机匹配应confirmed_duplicate，实际{s0_result['result_type']} score={s0_result['match_score']}"

    # 4. 样例中李芳芳是预置老客 → returning_customer
    lifangfang = [x for x in results if x["sample_phone"] == "13800008888"][0]
    print(f"  李芳芳试算结果: {lifangfang['result_type']} 原来源={lifangfang['original_source_channel']} 等级={lifangfang['customer_level']}")
    if lifangfang["result_type"] != "returning_customer" or lifangfang["original_source_channel"] != "CRM_IMPORT":
        return False, f"李芳芳试算应为returning_customer+CRM_IMPORT来源"
    return True, ""


def t8():
    """新进重复线索也能看到final_owner + 复核后的线索所有详情一致"""
    # 造1条新的重复冲突
    ph = "13455556666"
    post("/leads/receive", {"phone": ph, "name": "FinalOwner", "channel_code": "BAIDU_SEM", "store_code": "BJ_CHAOYANG"})
    s, r = post("/leads/receive", {"phone": ph, "name": "FinalOwner", "channel_code": "WECHAT_WORK", "store_code": "BJ_HAIDIAN"})
    dup_id = r["data"]["conflict_duplicate_id"]
    orig_lead_id = r["data"]["original_lead_id"]
    new_lead_id = r["data"]["lead_id"]
    print(f"  产生冲突: dup_id={dup_id} orig={orig_lead_id} new={new_lead_id}")

    # 复核改归属到 企微客服 / BJ_HAIDIAN
    s, r = post("/leads/duplicates/review", {
        "duplicate_id": dup_id,
        "review_result": "reassigned",
        "reviewer": "李四",
        "final_owner_channel": "WECHAT_WORK",
        "final_owner_store": "BJ_HAIDIAN"
    })
    print(f"  复核完成: {r['data']['review_result']}")

    # 查原线索详情
    s, orig = get(f"/leads/{orig_lead_id}")
    print(f"  原线索详情: review={orig['data']['review_status']} final_ch={orig['data']['final_owner_channel']} final_st={orig['data']['final_owner_store']}")

    # 同号第三次进入 → 应是 allocated/returning_customer
    s, r = post("/leads/receive", {"phone": ph, "name": "FinalOwner3", "channel_code": "DOUYIN_AD", "store_code": "SZ_NANSHAN"})
    rt3 = r["data"]["result_type"]
    attr_ch = r["data"]["attribution_channel"]
    attr_st = r["data"]["attribution_store"]
    print(f"  复核后第三次进入: {rt3} 归属渠道={attr_ch} 归属门店={attr_st}")
    # 应继承复核后的归属，因为原线索已经被分配，所以会有优先级归因等

    if orig["data"]["review_status"] != "reassigned":
        return False, f"原线索review_status不是reassigned"
    if orig["data"]["final_owner_channel"] != "WECHAT_WORK" or orig["data"]["final_owner_store"] != "BJ_HAIDIAN":
        return False, f"原线索final_owner和复核结果不一致"

    # 查新线索(第二条，即 duplicate_lead_id 对应那个)是否可以看到最终归属信息
    s, dup_list_resp = get("/leads/duplicates/list?is_confirmed=true&page_size=5")
    for item in dup_list_resp["data"]["list"]:
        if item["id"] == dup_id:
            print(f"  冲突记录: orig_ch={item['original_channel']} dup_ch={item['duplicate_channel']} final_ch={item['final_owner_channel']} final_st={item['final_owner_store']}")
            if item["final_owner_channel"] != "WECHAT_WORK":
                return False, f"冲突记录final_owner_channel不是WECHAT_WORK"
            break
    return True, ""


def t9():
    """复核统计：按结果/最终归属渠道/最终归属门店分组"""
    s, r = get("/stats/reviews")
    if s != 200:
        return False, f"复核统计失败 {r}"
    d = r["data"]
    print(f"  总待办: {d['total_pending']}")
    print(f"  已复核: {d['total_reviewed']}  复核率: {d['review_rate']}%")
    print(f"  按结果: {d['by_confirm_result']}")
    print(f"  按归属渠道数: {len(d['by_final_owner_channel'])}")
    print(f"  按归属门店数: {len(d['by_final_owner_store'])}")
    print(f"  按线索review状态: {d['by_lead_review_status']}")

    if d["total_reviewed"] < 3:
        return False, f"已复核数应>=3（批量2+单次1）"
    if "reassigned" not in d["by_confirm_result"]:
        return False, f"by_confirm_result应含reassigned"

    # 总览里review_summary是否有
    s, r = get("/stats/overview")
    rv = r["data"].get("review_summary", {})
    print(f"  总览review_summary: pending={rv.get('total_pending')} reviewed={rv.get('total_reviewed')}")
    if "review_summary" not in r["data"]:
        return False, f"overview缺少review_summary字段"
    return True, ""


def t10():
    """综合回归：新客/重复/跨店/黑名单/老客 全链路走一遍"""
    cases = [
        # (数据, 期望类型集合, 描述)
        ({"phone": "13100001111", "name": "赵新客", "channel_code": "XHS_AD", "store_code": "SH_XUHUI"},
         {"new_customer"}, "全新客"),
        # 黑名单
        ({"phone": "13800000001", "name": "黑名单用户", "channel_code": "BAIDU_SEM", "store_code": "BJ_CHAOYANG"},
         {"blacklist"}, "黑名单"),
        # 李芳芳是老客
        ({"phone": "13800008888", "name": "李芳芳", "channel_code": "XHS_AD", "store_code": "SH_PUDONG"},
         {"returning_customer"}, "老客复询"),
    ]
    for data, expect, desc in cases:
        s, r = post("/leads/receive", data)
        rt = r["data"]["result_type"]
        print(f"  [{desc}] 实际={rt} 期望∈{expect}")
        if rt not in expect:
            return False, f"[{desc}] 期望{expect}，实际{rt}"

    # 跨店重复
    ph = "13200003333"
    post("/leads/receive", {"phone": ph, "name": "跨店", "channel_code": "BAIDU_SEM", "store_code": "BJ_CHAOYANG"})
    s, r = post("/leads/receive", {"phone": ph, "name": "跨店", "channel_code": "DOUYIN_AD", "store_code": "GZ_TIANHE"})
    print(f"  [跨店] 实际={r['data']['result_type']} is_cross={r['data']['is_cross_store']} orig_store={r['data']['original_store']}")
    if r["data"]["result_type"] != "cross_store_conflict":
        return False, f"跨店冲突应cross_store_conflict，实际{r['data']['result_type']}"

    # 总览统计
    s, r = get("/stats/overview")
    d = r["data"]
    print(f"\n  总览: 总{d['total_leads']} 新客{d['new_leads']} 重复{d['duplicate_leads']} 黑名单{d['blacklist_leads']} 老客复询{d['returning_leads']}")
    if d["returning_leads"] < 2:
        return False, f"老客复询至少2条"
    return True, ""


if __name__ == "__main__":
    run("1:规则版本-新建草稿/修改/发布/切回/新线索按发布版生效", t1)
    run("2:老客档案识别-预置VIP客户再咨询带出原来源/最近到店/建议跟进", t2)
    run("3:批量导入CRM客户-覆盖更新-新咨询优先返回老客复询", t3)
    run("4:复核待办-待办统计+按条件筛选", t4)
    run("5:批量复核-批量改归属后所有记录/线索详情一致", t5)
    run("6:给线索打老客标签-后续同号咨询识别为老客复询", t6)
    run("7:规则试算-默认published/指定保存/自定义权重三种模式", t7)
    run("8:复核后新进重复线索final_owner与复核结果一致", t8)
    run("9:复核统计-按结果/归属渠道/归属门店分组+总览review_summary", t9)
    run("10:综合回归-新客/重复/跨店/黑名单/老客+总览", t10)

    print("\n" + "=" * 60)
    print(f"🎉 完成：通过 {passed}，失败 {failed}，共 {passed + failed}")
    print("=" * 60)
    exit(0 if failed == 0 else 1)
