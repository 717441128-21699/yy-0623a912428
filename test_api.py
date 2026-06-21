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
    print("=" * 50)
    print("测试1: 新客线索接收")
    print("=" * 50)
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
    print(f"结果类型: {d['result_type']}")
    print(f"结果描述: {d['result_description']}")
    print(f"是否新客: {d['is_new_customer']}")
    print(f"建议动作: {d['suggested_action']}")
    print(f"线索ID: {d['lead_id']}")
    print(f"归属渠道: {d['attribution_channel']}")
    print()
    return d['lead_id']


def test_duplicate():
    print("=" * 50)
    print("测试2: 重复线索（同手机号，不同渠道）")
    print("=" * 50)
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
    print(f"结果类型: {d['result_type']}")
    print(f"结果描述: {d['result_description']}")
    print(f"是否新客: {d['is_new_customer']}")
    print(f"匹配分数: {d['match_score']}")
    print(f"归属渠道: {d['attribution_channel']}")
    print(f"归因类型: {d['attribution_type']}")
    print(f"原始线索ID: {d['original_lead_id']}")
    print(f"建议动作: {d['suggested_action']}")
    print()


def test_cross_store():
    print("=" * 50)
    print("测试3: 跨门店重复")
    print("=" * 50)
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
    print(f"结果类型: {d['result_type']}")
    print(f"结果描述: {d['result_description']}")
    print(f"是否跨店: {d['is_cross_store']}")
    print(f"原门店: {d['original_store']}")
    print(f"新门店: SH_PUDONG")
    print(f"冲突记录ID: {d['conflict_duplicate_id']}")
    print(f"建议动作: {d['suggested_action']}")
    print()
    return d['conflict_duplicate_id']


def test_blacklist():
    print("=" * 50)
    print("测试4: 黑名单拦截")
    print("=" * 50)
    data = {
        'phone': '13800000001',
        'name': '测试黑名单',
        'channel_code': 'BAIDU_SEM',
        'store_code': 'BJ_CHAOYANG'
    }
    result = post('/leads/receive', data)
    d = result['data']
    print(f"结果类型: {d['result_type']}")
    print(f"结果描述: {d['result_description']}")
    print(f"是否黑名单: {d['is_blacklist']}")
    print(f"建议动作: {d['suggested_action']}")
    print()


def test_stats():
    print("=" * 50)
    print("测试5: 统计查询 - 渠道维度")
    print("=" * 50)
    result = get('/stats/channels')
    print(f"渠道数量: {result['data']['total_count']}")
    for item in result['data']['items'][:3]:
        print(f"  {item['channel_name']}: 总线索{item['total_leads']}, 有效率{item['valid_rate']}%, 重复率{item['duplicate_rate']}%")
    print()

    print("=" * 50)
    print("测试6: 统计查询 - 门店维度")
    print("=" * 50)
    result = get('/stats/stores')
    print(f"门店数量: {result['data']['total_count']}")
    for item in result['data']['items'][:3]:
        print(f"  {item['store_name']}: 总线索{item['total_leads']}, 重复率{item['duplicate_rate']}%")
    print()

    print("=" * 50)
    print("测试7: 统计总览")
    print("=" * 50)
    result = get('/stats/overview')
    d = result['data']
    print(f"总线索数: {d['total_leads']}")
    print(f"有效线索: {d['valid_leads']}")
    print(f"新客数: {d['new_leads']}")
    print(f"重复线索: {d['duplicate_leads']}")
    print(f"黑名单: {d['blacklist_leads']}")
    print(f"有效率: {d['valid_rate']}%")
    print(f"新客率: {d['new_customer_rate']}%")
    print()


def test_duplicate_list():
    print("=" * 50)
    print("测试8: 重复冲突列表")
    print("=" * 50)
    result = get('/leads/duplicates/list')
    d = result['data']
    print(f"总记录数: {d['total']}")
    for item in d['list'][:3]:
        print(f"  ID:{item['id']} 类型:{item['duplicate_type']} 跨店:{item['is_cross_store']}")
    print()


def test_channel_config():
    print("=" * 50)
    print("测试9: 渠道配置列表")
    print("=" * 50)
    result = get('/config/channels')
    d = result['data']
    print(f"渠道总数: {d['total']}")
    for item in d['list'][:5]:
        print(f"  {item['channel_code']}: {item['channel_name']} (优先级:{item['priority']})")
    print()


def test_lead_list():
    print("=" * 50)
    print("测试10: 线索列表")
    print("=" * 50)
    result = get('/leads/list?page=1&page_size=5')
    d = result['data']
    print(f"总线索数: {d['total']}")
    for item in d['list']:
        print(f"  {item['lead_id']}: {item['lead_status']} - {item['channel_code']}")
    print()


if __name__ == "__main__":
    try:
        test_new_customer()
        test_duplicate()
        conflict_id = test_cross_store()
        test_blacklist()
        test_stats()
        test_duplicate_list()
        test_channel_config()
        test_lead_list()
        
        print("=" * 50)
        print("所有测试完成！")
        print("=" * 50)
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()
