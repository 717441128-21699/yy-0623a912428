import urllib.request
import json
import urllib.error

BASE_URL = "http://127.0.0.1:8000/api/v1"


def post(path, data):
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=json.dumps(data).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode('utf-8'))


def get(path):
    req = urllib.request.Request(f"{BASE_URL}{path}")
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read().decode('utf-8'))


def test_new_customer():
    print("=" * 60)
    print("测试1: 新客线索接收")
    print("=" * 60)
    data = {
        'phone': '13912345678',
        'name': '张三',
        'city': '北京',
        'intended_project': '双眼皮',
        'ad_plan': '暑期促销活动',
        'landing_page': '/promotion/summer',
        'channel_code': 'BAIDU_SEM',
        'store_code': 'BJ_CHAOYANG'
    }
    result = post('/leads/receive', data)
    d = result['data']
    print(f"  结果类型: {d['result_type']}")
    print(f"  结果描述: {d['result_description']}")
    print(f"  是否新客: {d['is_new_customer']}")
    print(f"  建议动作: {d['suggested_action']}")
    print(f"  线索ID: {d['lead_id']}")
    assert d['result_type'] == 'new_customer'
    print("  ✅ 通过\n")
    return d['lead_id']


def test_duplicate_same_phone():
    print("=" * 60)
    print("测试2: 同手机号重复线索")
    print("=" * 60)
    data = {
        'phone': '13912345678',
        'name': '张小三',
        'city': '北京',
        'intended_project': '隆鼻',
        'channel_code': 'DOUYIN_AD',
        'store_code': 'BJ_CHAOYANG'
    }
    result = post('/leads/receive', data)
    d = result['data']
    print(f"  结果类型: {d['result_type']}")
    print(f"  结果描述: {d['result_description']}")
    print(f"  匹配分数: {d['match_score']}")
    print(f"  归属渠道: {d['attribution_channel']}")
    print(f"  归因类型: {d['attribution_type']}")
    assert d['result_type'] in ('confirmed_duplicate', 'suspected_duplicate')
    print("  ✅ 通过\n")
    return d['conflict_duplicate_id']


def test_cross_store():
    print("=" * 60)
    print("测试3: 跨门店重复")
    print("=" * 60)
    data = {
        'phone': '13912345678',
        'name': '张三',
        'city': '上海',
        'intended_project': '双眼皮',
        'channel_code': 'OFFICIAL_WEBSITE',
        'store_code': 'SH_PUDONG'
    }
    result = post('/leads/receive', data)
    d = result['data']
    print(f"  结果类型: {d['result_type']}")
    print(f"  是否跨店: {d['is_cross_store']}")
    print(f"  原门店: {d['original_store']}")
    assert d['is_cross_store'] == True
    print("  ✅ 通过\n")
    return d['conflict_duplicate_id']


def test_returning_customer_via_crm():
    print("=" * 60)
    print("测试4: CRM导入标记老客 → 老客复询")
    print("=" * 60)
    data = {
        'phone': '13987654321',
        'name': '李四',
        'city': '广州',
        'intended_project': '玻尿酸',
        'channel_code': 'CRM_IMPORT',
        'store_code': 'GZ_TIANHE',
        'is_returning': True
    }
    result = post('/leads/receive', data)
    d = result['data']
    print(f"  结果类型: {d['result_type']}")
    print(f"  是否老客: {d.get('is_returning', False)}")
    assert d['is_new_customer'] == True
    lead_id = d['lead_id']
    
    data2 = {
        'phone': '13987654321',
        'name': '李四',
        'city': '广州',
        'intended_project': '热玛吉',
        'channel_code': 'MINI_PROGRAM',
        'store_code': 'GZ_TIANHE'
    }
    result2 = post('/leads/receive', data2)
    d2 = result2['data']
    print(f"  再次咨询结果: {d2['result_type']}")
    print(f"  再次咨询描述: {d2['result_description']}")
    print(f"  是否老客复询: {d2.get('is_returning', False)}")
    assert d2['result_type'] == 'returning_customer'
    print("  ✅ 通过\n")
    return lead_id


def test_blacklist_with_phone():
    print("=" * 60)
    print("测试5: 黑名单 - 提交明文手机号后立即拦截")
    print("=" * 60)
    bl_result = post('/config/blacklist', {
        'black_type': 'phone',
        'phone': '13900001111',
        'reason': '恶意骚扰'
    })
    print(f"  添加黑名单: {bl_result['message']}")
    print(f"  返回ID: {bl_result['data']['id']}")
    
    data = {
        'phone': '13900001111',
        'name': '测试黑名单',
        'channel_code': 'BAIDU_SEM',
        'store_code': 'BJ_CHAOYANG'
    }
    result = post('/leads/receive', data)
    d = result['data']
    print(f"  判重结果: {d['result_type']}")
    print(f"  是否黑名单: {d['is_blacklist']}")
    assert d['result_type'] == 'blacklist'
    assert d['is_blacklist'] == True
    print("  ✅ 通过\n")


def test_dedup_rules():
    print("=" * 60)
    print("测试6: 判重规则配置 - 查看/修改/切换")
    print("=" * 60)
    rules_result = get('/config/dedup-rules')
    rules = rules_result['data']['list']
    print(f"  规则总数: {len(rules)}")
    for r in rules:
        active = "【活跃】" if r['is_active'] else ""
        print(f"    {r['rule_key']}: {r['rule_name']} {active}")
        print(f"      手机权重:{r['phone_weight']} 微信权重:{r['wechat_weight']} 确认阈值:{r['confirmed_threshold']} 疑似阈值:{r['suspected_threshold']}")
    
    active_rule = [r for r in rules if r['is_active']][0]
    print(f"\n  当前活跃规则: {active_rule['rule_key']}")
    
    import urllib.request as ur
    req = ur.Request(
        f"{BASE_URL}/config/dedup-rules/loose/activate",
        data=b'',
        headers={'Content-Type': 'application/json'},
        method='PUT'
    )
    resp = ur.urlopen(req)
    activate_result = json.loads(resp.read().decode('utf-8'))
    print(f"  切换到宽松规则: {activate_result['data']['active_rule_key']}")
    
    rules_after = get('/config/dedup-rules')
    for r in rules_after['data']['list']:
        if r['is_active']:
            print(f"  切换后活跃规则: {r['rule_key']}")
            assert r['rule_key'] == 'loose'
    
    import urllib.request as ur2
    req2 = ur2.Request(
        f"{BASE_URL}/config/dedup-rules/standard/activate",
        data=b'',
        headers={'Content-Type': 'application/json'},
        method='PUT'
    )
    resp2 = ur2.urlopen(req2)
    json.loads(resp2.read().decode('utf-8'))
    print("  已切回标准规则")
    
    print("  ✅ 通过\n")


def test_review_closed_loop():
    print("=" * 60)
    print("测试7: 复核闭环 - 确认/驳回/改归属")
    print("=" * 60)
    data = {
        'phone': '13911112222',
        'name': '王五',
        'city': '深圳',
        'intended_project': '吸脂',
        'channel_code': 'DOUYIN_AD',
        'store_code': 'SZ_NANSHAN'
    }
    result1 = post('/leads/receive', data)
    lead_id = result1['data']['lead_id']
    print(f"  新建线索: {lead_id}")
    
    data2 = {
        'phone': '13911112222',
        'name': '王五',
        'city': '深圳',
        'intended_project': '吸脂',
        'channel_code': 'XHS_AD',
        'store_code': 'SZ_NANSHAN'
    }
    result2 = post('/leads/receive', data2)
    dup_id = result2['data']['conflict_duplicate_id']
    print(f"  产生冲突记录: {dup_id}")
    
    review_result = post('/leads/duplicates/review', {
        'duplicate_id': dup_id,
        'review_result': 'reassigned',
        'reviewer': '张主管',
        'review_remark': '小红书渠道归因给抖音',
        'final_owner_channel': 'DOUYIN_AD',
        'final_owner_store': 'SZ_NANSHAN'
    })
    print(f"  复核结果: {review_result['data']['review_result']}")
    print(f"  最终归属渠道: {review_result['data']['final_owner_channel']}")
    print(f"  最终归属门店: {review_result['data']['final_owner_store']}")
    assert review_result['data']['review_result'] == 'reassigned'
    
    detail = get(f'/leads/{lead_id}')
    d = detail['data']
    print(f"  线索详情 - review_status: {d['review_status']}")
    print(f"  线索详情 - lead_status: {d['lead_status']}")
    print(f"  线索详情 - reviewed_by: {d['reviewed_by']}")
    assert d['review_status'] == 'reassigned'
    assert d['lead_status'] == 'allocated'
    
    data3 = {
        'phone': '13911112222',
        'name': '王五',
        'city': '深圳',
        'intended_project': '吸脂',
        'channel_code': 'MINI_PROGRAM',
        'store_code': 'SZ_NANSHAN'
    }
    result3 = post('/leads/receive', data3)
    d3 = result3['data']
    print(f"  复核后再进线索结果: {d3['result_type']}")
    print(f"  是否老客复询: {d3.get('is_returning', False)}")
    assert d3['result_type'] in ('returning_customer', 'allocated')
    print("  ✅ 通过\n")


def test_api_logs():
    print("=" * 60)
    print("测试8: 接口调用日志 - 按渠道/门店筛选")
    print("=" * 60)
    logs = get('/stats/api-logs?channel_code=BAIDU_SEM&page_size=5')
    d = logs['data']
    print(f"  按渠道筛选日志总数: {d['total']}")
    for item in d['list'][:3]:
        print(f"    {item['api_path']} [{item['method']}] status={item['status_code']} err={item['has_error']}")
        if item.get('request_summary'):
            print(f"      摘要: {item['request_summary']}")
    
    logs2 = get('/stats/api-logs?store_code=BJ_CHAOYANG&page_size=3')
    d2 = logs2['data']
    print(f"  按门店筛选日志总数: {d2['total']}")
    
    print("  ✅ 通过\n")


def test_duplicate_list_with_review():
    print("=" * 60)
    print("测试9: 重复冲突列表 - 含复核状态和最终归属")
    print("=" * 60)
    result = get('/leads/duplicates/list?is_confirmed=true&page_size=5')
    d = result['data']
    print(f"  已复核记录数: {d['total']}")
    for item in d['list'][:3]:
        print(f"    ID:{item['id']} 类型:{item['duplicate_type']} 复核结果:{item['confirm_result']} 最终渠道:{item.get('final_owner_channel')} 最终门店:{item.get('final_owner_store')}")
    print("  ✅ 通过\n")


def test_stats_with_returning():
    print("=" * 60)
    print("测试10: 统计 - 含老客复询维度")
    print("=" * 60)
    overview = get('/stats/overview')
    d = overview['data']
    print(f"  总线索: {d['total_leads']}")
    print(f"  新客数: {d['new_leads']}")
    print(f"  重复数: {d['duplicate_leads']}")
    print(f"  黑名单: {d['blacklist_leads']}")
    print(f"  老客复询: {d.get('returning_leads', 0)}")
    print(f"  老客复询率: {d.get('returning_rate', 0)}%")
    
    channels = get('/stats/channels')
    for item in channels['data']['items'][:3]:
        print(f"  {item['channel_name']}: 总{item['total_leads']} 有效率{item['valid_rate']}% 老客{item.get('returning_leads', 0)}")
    print("  ✅ 通过\n")


if __name__ == "__main__":
    try:
        test_new_customer()
        test_duplicate_same_phone()
        test_cross_store()
        test_returning_customer_via_crm()
        test_blacklist_with_phone()
        test_dedup_rules()
        test_review_closed_loop()
        test_api_logs()
        test_duplicate_list_with_review()
        test_stats_with_returning()
        
        print("=" * 60)
        print("🎉 所有10个测试全部通过！")
        print("=" * 60)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
