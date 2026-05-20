"""
SweetLoaf 烘焙管理系统 - API 端点测试用例

测试覆盖以下核心API:
  1. GET /api/stores          - 门店列表
  2. GET /api/products        - 产品列表（支持按分类筛选）
  3. POST /api/products       - 新增产品
  4. GET /api/inventory       - 库存看板
  5. POST /api/inventory/transaction - 库存变动
  6. GET /api/inventory/alerts - 库存预警
  7. POST /api/production     - 生产记录
  8. POST /api/waste          - 报废记录
  9. GET/POST /api/orders     - 订单列表/创建订单
  10. GET /api/orders/calendar - 订单日历
  11. GET/POST /api/employees  - 员工列表/新增员工
  12. GET /api/schedules       - 排班表
  13. POST /api/leave-requests - 请假/调班申请
  14. GET/POST /api/members    - 会员列表/注册会员
  15. GET /api/dashboard       - 经营数据仪表盘
"""
import json
import pytest


# ============================================================
# 1. 门店管理
# ============================================================
class TestStores:
    """门店管理 API 测试"""

    def test_list_stores(self, client):
        """测试获取门店列表 - 应返回3家门店"""
        resp = client.get('/api/stores')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        assert len(data['data']) == 3
        # 验证门店名称
        store_names = [s['name'] for s in data['data']]
        assert '总店（东区）' in store_names
        assert '中西区分店' in store_names
        assert '南区分店' in store_names

    def test_list_stores_structure(self, client):
        """测试门店数据字段完整性"""
        resp = client.get('/api/stores')
        data = resp.get_json()
        store = data['data'][0]
        assert 'id' in store
        assert 'name' in store
        assert 'address' in store
        assert 'phone' in store
        assert 'is_active' in store


# ============================================================
# 2. 产品管理
# ============================================================
class TestProducts:
    """产品管理 API 测试"""

    def test_list_products(self, client):
        """测试获取产品列表"""
        resp = client.get('/api/products')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        assert len(data['data']) > 0

    def test_list_products_by_category(self, client):
        """测试按分类筛选产品"""
        resp = client.get('/api/products?category=finished')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        for p in data['data']:
            assert p['category'] == 'finished'

    def test_list_products_raw_material(self, client):
        """测试筛选原料类产品"""
        resp = client.get('/api/products?category=raw_material')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        for p in data['data']:
            assert p['category'] == 'raw_material'

    def test_create_product(self, client):
        """测试新增产品"""
        new_product = {
            'name': '测试面包',
            'category': 'finished',
            'unit': '个',
            'price': 25.0,
            'cost': 10.0
        }
        resp = client.post(
            '/api/products',
            data=json.dumps(new_product),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        assert data['data']['name'] == '测试面包'
        assert data['data']['price'] == 25.0

    def test_create_product_missing_name(self, client):
        """测试新增产品缺少名称应返回错误"""
        resp = client.post(
            '/api/products',
            data=json.dumps({'category': 'finished'}),
            content_type='application/json'
        )
        assert resp.status_code == 400 or resp.status_code == 200
        data = resp.get_json()
        # 期望返回错误码
        if resp.status_code == 200:
            assert data['code'] != 0


# ============================================================
# 3. 库存管理
# ============================================================
class TestInventory:
    """库存管理 API 测试"""

    def test_get_inventory(self, client):
        """测试获取库存看板"""
        resp = client.get('/api/inventory?store_id=1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        assert 'data' in data

    def test_get_inventory_all_stores(self, client):
        """测试不传store_id获取所有门店库存"""
        resp = client.get('/api/inventory')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0

    def test_inventory_transaction_in(self, client):
        """测试入库操作"""
        # 先获取一个产品ID
        resp = client.get('/api/products?category=raw_material')
        products = resp.get_json()['data']
        if not products:
            pytest.skip("没有原料产品可测试")
        product_id = products[0]['id']

        transaction = {
            'store_id': 1,
            'product_id': product_id,
            'type': 'in',
            'quantity': 50,
            'remark': '测试入库'
        }
        resp = client.post(
            '/api/inventory/transaction',
            data=json.dumps(transaction),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0

    def test_inventory_transaction_out(self, client):
        """测试出库操作"""
        resp = client.get('/api/products?category=raw_material')
        products = resp.get_json()['data']
        if not products:
            pytest.skip("没有原料产品可测试")
        product_id = products[0]['id']

        # 先入库
        client.post(
            '/api/inventory/transaction',
            data=json.dumps({
                'store_id': 1,
                'product_id': product_id,
                'type': 'in',
                'quantity': 100
            }),
            content_type='application/json'
        )

        # 再出库
        transaction = {
            'store_id': 1,
            'product_id': product_id,
            'type': 'out',
            'quantity': 30,
            'remark': '测试出库'
        }
        resp = client.post(
            '/api/inventory/transaction',
            data=json.dumps(transaction),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0

    def test_inventory_alerts(self, client):
        """测试库存预警"""
        resp = client.get('/api/inventory/alerts')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        assert 'data' in data


# ============================================================
# 4. 生产与报废
# ============================================================
class TestProductionAndWaste:
    """生产与报废管理 API 测试"""

    def test_create_production_record(self, client):
        """测试创建生产记录"""
        resp = client.get('/api/products?category=finished')
        products = resp.get_json()['data']
        if not products:
            pytest.skip("没有成品可测试")
        product_id = products[0]['id']

        record = {
            'store_id': 1,
            'product_id': product_id,
            'quantity': 50,
            'produced_date': '2026-05-15'
        }
        resp = client.post(
            '/api/production',
            data=json.dumps(record),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0

    def test_create_waste_record(self, client):
        """测试创建报废记录"""
        resp = client.get('/api/products?category=finished')
        products = resp.get_json()['data']
        if not products:
            pytest.skip("没有成品可测试")
        product_id = products[0]['id']

        record = {
            'store_id': 1,
            'product_id': product_id,
            'quantity': 5,
            'reason': '未售出',
            'waste_date': '2026-05-15'
        }
        resp = client.post(
            '/api/waste',
            data=json.dumps(record),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0


# ============================================================
# 5. 订单管理
# ============================================================
class TestOrders:
    """订单管理 API 测试"""

    def test_list_orders(self, client):
        """测试获取订单列表"""
        resp = client.get('/api/orders')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0

    def test_create_order(self, client):
        """测试创建订单"""
        resp = client.get('/api/products?category=finished')
        products = resp.get_json()['data']
        if not products:
            pytest.skip("没有成品可测试")
        product_id = products[0]['id']

        order = {
            'store_id': 1,
            'customer_name': '测试客户',
            'customer_phone': '0912345678',
            'order_type': '预订',
            'pickup_date': '2026-05-20',
            'items': [
                {'product_id': product_id, 'quantity': 2}
            ]
        }
        resp = client.post(
            '/api/orders',
            data=json.dumps(order),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0

    def test_order_calendar(self, client):
        """测试订单日历"""
        resp = client.get('/api/orders/calendar?year=2026&month=5')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0


# ============================================================
# 6. 员工与排班
# ============================================================
class TestEmployees:
    """员工管理 API 测试"""

    def test_list_employees(self, client):
        """测试获取员工列表"""
        resp = client.get('/api/employees')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        assert len(data['data']) > 0

    def test_create_employee(self, client):
        """测试新增员工"""
        employee = {
            'name': '测试员工',
            'store_id': 1,
            'position': '店员',
            'phone': '0999999999'
        }
        resp = client.post(
            '/api/employees',
            data=json.dumps(employee),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        assert data['data']['name'] == '测试员工'

    def test_get_schedules(self, client):
        """测试获取排班表"""
        resp = client.get('/api/schedules?store_id=1&date=2026-05-15')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0

    def test_create_leave_request(self, client):
        """测试提交请假申请"""
        leave = {
            'employee_id': 1,
            'leave_date': '2026-05-20',
            'leave_type': '请假',
            'reason': '身体不适'
        }
        resp = client.post(
            '/api/leave-requests',
            data=json.dumps(leave),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0


# ============================================================
# 7. 会员管理
# ============================================================
class TestMembers:
    """会员管理 API 测试"""

    def test_list_members(self, client):
        """测试获取会员列表"""
        resp = client.get('/api/members')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0

    def test_register_member(self, client):
        """测试注册新会员"""
        member = {
            'name': '张三',
            'phone': '0911111111',
            'birthday': '1990-01-01'
        }
        resp = client.post(
            '/api/members',
            data=json.dumps(member),
            content_type='application/json'
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        assert data['data']['name'] == '张三'


# ============================================================
# 8. 数据仪表盘
# ============================================================
class TestDashboard:
    """经营数据仪表盘 API 测试"""

    def test_dashboard(self, client):
        """测试获取经营数据仪表盘"""
        resp = client.get('/api/dashboard?store_id=1')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0
        assert 'data' in data

    def test_dashboard_all_stores(self, client):
        """测试获取所有门店仪表盘"""
        resp = client.get('/api/dashboard')
        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 0


# ============================================================
# 9. 首页与健康检查
# ============================================================
class TestHealth:
    """基础健康检查"""

    def test_index_page(self, client):
        """测试首页可访问"""
        resp = client.get('/')
        assert resp.status_code == 200
        assert b'SweetLoaf' in resp.data

    def test_api_json_response_format(self, client):
        """测试API响应格式统一"""
        resp = client.get('/api/stores')
        data = resp.get_json()
        assert 'code' in data
        assert 'data' in data
