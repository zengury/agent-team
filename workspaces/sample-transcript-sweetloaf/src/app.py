"""
SweetLoaf 烘焙坊运营管理平台 - Flask主入口

基于PRD需求，提供以下API路由：
1. 门店管理 API
2. 员工管理 API
3. 产品管理 API
4. 原料管理 API
5. 库存管理 API
6. 订单管理 API
7. 排班管理 API
8. 会员管理 API
9. 数据看板 API
"""
import os
import sys
from datetime import datetime, date, timedelta
from functools import wraps

from flask import Flask, request, jsonify, render_template_string

# 确保能找到src包
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import config
from models import db, Store, Employee, Product, Ingredient, Inventory
from models import InventoryTransaction, Order, OrderItem, Schedule
from models import ShiftRequest, Member, SaleRecord, ProductionRecord


def create_app(config_name=None):
    """应用工厂"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__)
    app.config.from_object(config.get(config_name, config['default']))

    db.init_app(app)

    # 注册路由
    register_routes(app)

    # 创建数据库表
    with app.app_context():
        db.create_all()
        # 初始化种子数据
        _init_seed_data()


    # ── Dashboard UI ──
    @app.route("/dashboard")
    def dashboard():
        from flask import send_from_directory
        import os
        return send_from_directory(os.path.join(app.root_path, ".."), "dashboard.html")

    return app


def register_routes(app):
    """注册所有路由"""

    # ============================================================
    # 首页 - API文档
    # ============================================================
    @app.route('/')
    def index():
        return jsonify({
            'name': 'SweetLoaf 烘焙坊运营管理平台',
            'version': '1.0.0',
            'status': 'running',
            'endpoints': {
                'stores': '/api/stores',
                'employees': '/api/employees',
                'products': '/api/products',
                'ingredients': '/api/ingredients',
                'inventory': '/api/inventory',
                'orders': '/api/orders',
                'schedules': '/api/schedules',
                'members': '/api/members',
                'dashboard': '/api/dashboard'
            }
        })

    # ============================================================
    # 门店管理 API
    # ============================================================
    @app.route('/api/stores', methods=['GET'])
    def get_stores():
        """获取所有门店"""
        stores = Store.query.all()
        return jsonify({'code': 0, 'data': [s.to_dict() for s in stores]})

    @app.route('/api/stores', methods=['POST'])
    def create_store():
        """创建门店"""
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'code': 1, 'message': '门店名称不能为空'}), 400
        store = Store(
            name=data['name'],
            location=data.get('location', ''),
            phone=data.get('phone', '')
        )
        db.session.add(store)
        db.session.commit()
        return jsonify({'code': 0, 'data': store.to_dict(), 'message': '创建成功'}), 201

    @app.route('/api/stores/<int:store_id>', methods=['GET'])
    def get_store(store_id):
        """获取单个门店"""
        store = Store.query.get_or_404(store_id)
        return jsonify({'code': 0, 'data': store.to_dict()})

    # ============================================================
    # 员工管理 API
    # ============================================================
    @app.route('/api/employees', methods=['GET'])
    def get_employees():
        """获取所有员工"""
        store_id = request.args.get('store_id', type=int)
        query = Employee.query
        if store_id:
            query = query.filter_by(store_id=store_id)
        employees = query.all()
        return jsonify({'code': 0, 'data': [e.to_dict() for e in employees]})

    @app.route('/api/employees', methods=['POST'])
    def create_employee():
        """创建员工"""
        data = request.get_json()
        required = ['name', 'role', 'store_id']
        if not data or not all(k in data for k in required):
            return jsonify({'code': 1, 'message': '缺少必填字段'}), 400
        employee = Employee(
            name=data['name'],
            phone=data.get('phone', ''),
            role=data['role'],
            store_id=data['store_id']
        )
        db.session.add(employee)
        db.session.commit()
        return jsonify({'code': 0, 'data': employee.to_dict(), 'message': '创建成功'}), 201

    # ============================================================
    # 产品管理 API
    # ============================================================
    @app.route('/api/products', methods=['GET'])
    def get_products():
        """获取所有产品"""
        category = request.args.get('category')
        query = Product.query
        if category:
            query = query.filter_by(category=category)
        products = query.all()
        return jsonify({'code': 0, 'data': [p.to_dict() for p in products]})

    @app.route('/api/products', methods=['POST'])
    def create_product():
        """创建产品"""
        data = request.get_json()
        required = ['name', 'category', 'price']
        if not data or not all(k in data for k in required):
            return jsonify({'code': 1, 'message': '缺少必填字段'}), 400
        product = Product(
            name=data['name'],
            category=data['category'],
            price=data['price'],
            cost=data.get('cost', 0.0),
            is_signature=data.get('is_signature', False),
            is_limited=data.get('is_limited', False),
            description=data.get('description', '')
        )
        db.session.add(product)
        db.session.commit()
        return jsonify({'code': 0, 'data': product.to_dict(), 'message': '创建成功'}), 201

    # ============================================================
    # 原料管理 API
    # ============================================================
    @app.route('/api/ingredients', methods=['GET'])
    def get_ingredients():
        """获取所有原料"""
        ingredients = Ingredient.query.all()
        return jsonify({'code': 0, 'data': [i.to_dict() for i in ingredients]})

    @app.route('/api/ingredients', methods=['POST'])
    def create_ingredient():
        """创建原料"""
        data = request.get_json()
        required = ['name', 'unit']
        if not data or not all(k in data for k in required):
            return jsonify({'code': 1, 'message': '缺少必填字段'}), 400
        ingredient = Ingredient(
            name=data['name'],
            unit=data['unit'],
            unit_price=data.get('unit_price', 0.0),
            safety_stock=data.get('safety_stock', 0.0),
            supplier=data.get('supplier', '')
        )
        db.session.add(ingredient)
        db.session.commit()
        return jsonify({'code': 0, 'data': ingredient.to_dict(), 'message': '创建成功'}), 201

    # ============================================================
    # 库存管理 API
    # ============================================================
    @app.route('/api/inventory', methods=['GET'])
    def get_inventory():
        """获取库存看板 - 支持按门店筛选"""
        store_id = request.args.get('store_id', type=int)
        item_type = request.args.get('type')  # product 或 ingredient

        query = Inventory.query
        if store_id:
            query = query.filter_by(store_id=store_id)
        inventories = query.all()

        # 按类型筛选
        if item_type == 'product':
            inventories = [i for i in inventories if i.product_id is not None]
        elif item_type == 'ingredient':
            inventories = [i for i in inventories if i.ingredient_id is not None]

        return jsonify({'code': 0, 'data': [i.to_dict() for i in inventories]})

    @app.route('/api/inventory/transactions', methods=['GET'])
    def get_inventory_transactions():
        """获取库存变动记录"""
        store_id = request.args.get('store_id', type=int)
        query = InventoryTransaction.query
        if store_id:
            query = query.filter_by(store_id=store_id)
        transactions = query.order_by(InventoryTransaction.created_at.desc()).limit(100).all()
        return jsonify({'code': 0, 'data': [t.to_dict() for t in transactions]})

    @app.route('/api/inventory/transactions', methods=['POST'])
    def create_inventory_transaction():
        """创建库存变动记录（入库/出库/报废）"""
        data = request.get_json()
        required = ['store_id', 'transaction_type', 'quantity']
        if not data or not all(k in data for k in required):
            return jsonify({'code': 1, 'message': '缺少必填字段'}), 400

        transaction = InventoryTransaction(
            store_id=data['store_id'],
            product_id=data.get('product_id'),
            ingredient_id=data.get('ingredient_id'),
            transaction_type=data['transaction_type'],
            quantity=data['quantity'],
            reason=data.get('reason', ''),
            operator=data.get('operator', '')
        )

        # 更新库存
        store_id = data['store_id']
        qty = data['quantity']
        product_id = data.get('product_id')
        ingredient_id = data.get('ingredient_id')

        if product_id:
            inv = Inventory.query.filter_by(
                store_id=store_id, product_id=product_id
            ).first()
            if not inv:
                inv = Inventory(store_id=store_id, product_id=product_id, quantity=0)
                db.session.add(inv)
            if data['transaction_type'] == 'in':
                inv.quantity += qty
            elif data['transaction_type'] in ('out', 'waste'):
                inv.quantity -= qty

        if ingredient_id:
            inv = Inventory.query.filter_by(
                store_id=store_id, ingredient_id=ingredient_id
            ).first()
            if not inv:
                inv = Inventory(store_id=store_id, ingredient_id=ingredient_id, quantity=0)
                db.session.add(inv)
            if data['transaction_type'] == 'in':
                inv.quantity += qty
            elif data['transaction_type'] in ('out', 'waste'):
                inv.quantity -= qty

        db.session.add(transaction)
        db.session.commit()
        return jsonify({'code': 0, 'data': transaction.to_dict(), 'message': '操作成功'}), 201

    @app.route('/api/inventory/alerts', methods=['GET'])
    def get_inventory_alerts():
        """获取库存预警 - 低于安全库存的原料"""
        store_id = request.args.get('store_id', type=int)
        alerts = []

        query = Inventory.query
        if store_id:
            query = query.filter_by(store_id=store_id)

        for inv in query.all():
            if inv.ingredient_id:
                ingredient = Ingredient.query.get(inv.ingredient_id)
                if ingredient and inv.quantity < ingredient.safety_stock:
                    alerts.append({
                        'store_id': inv.store_id,
                        'store_name': inv.store.name if inv.store else None,
                        'ingredient_id': ingredient.id,
                        'ingredient_name': ingredient.name,
                        'current_quantity': inv.quantity,
                        'safety_stock': ingredient.safety_stock,
                        'suggested_order': max(
                            ingredient.safety_stock * 2 - inv.quantity,
                            0
                        )
                    })

        return jsonify({'code': 0, 'data': alerts})

    # ============================================================
    # 订单管理 API
    # ============================================================
    @app.route('/api/orders', methods=['GET'])
    def get_orders():
        """获取订单列表"""
        store_id = request.args.get('store_id', type=int)
        status = request.args.get('status')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        query = Order.query
        if store_id:
            query = query.filter_by(store_id=store_id)
        if status:
            query = query.filter_by(status=status)
        if date_from:
            query = query.filter(Order.pickup_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        if date_to:
            query = query.filter(Order.pickup_date <= datetime.strptime(date_to, '%Y-%m-%d').date())

        orders = query.order_by(Order.pickup_date.desc()).all()
        return jsonify({'code': 0, 'data': [o.to_dict() for o in orders]})

    @app.route('/api/orders', methods=['POST'])
    def create_order():
        """创建订单"""
        data = request.get_json()
        required = ['store_id', 'customer_name', 'pickup_date']
        if not data or not all(k in data for k in required):
            return jsonify({'code': 1, 'message': '缺少必填字段'}), 400

        # 生成订单编号
        order_no = f"SL{datetime.now().strftime('%Y%m%d%H%M%S')}{data['store_id']}"

        order = Order(
            order_no=order_no,
            store_id=data['store_id'],
            customer_name=data['customer_name'],
            customer_phone=data.get('customer_phone', ''),
            channel=data.get('channel', 'phone'),
            status='pending',
            pickup_date=datetime.strptime(data['pickup_date'], '%Y-%m-%d').date(),
            pickup_time=data.get('pickup_time', ''),
            notes=data.get('notes', '')
        )

        # 处理订单项
        total = 0.0
        if data.get('items'):
            for item_data in data['items']:
                product = Product.query.get(item_data['product_id'])
                if product:
                    subtotal = product.price * item_data['quantity']
                    total += subtotal
                    order_item = OrderItem(
                        product_id=product.id,
                        quantity=item_data['quantity'],
                        unit_price=product.price,
                        subtotal=subtotal
                    )
                    order.items.append(order_item)

        order.total_amount = total
        db.session.add(order)
        db.session.commit()
        return jsonify({'code': 0, 'data': order.to_dict(), 'message': '订单创建成功'}), 201

    @app.route('/api/orders/<int:order_id>', methods=['GET'])
    def get_order(order_id):
        """获取订单详情"""
        order = Order.query.get_or_404(order_id)
        return jsonify({'code': 0, 'data': order.to_dict()})

    @app.route('/api/orders/<int:order_id>', methods=['PUT'])
    def update_order(order_id):
        """更新订单状态"""
        order = Order.query.get_or_404(order_id)
        data = request.get_json()
        if data.get('status'):
            order.status = data['status']
        if data.get('notes'):
            order.notes = data['notes']
        db.session.commit()
        return jsonify({'code': 0, 'data': order.to_dict(), 'message': '更新成功'})

    @app.route('/api/orders/calendar', methods=['GET'])
    def get_order_calendar():
        """获取订单日历视图"""
        year = request.args.get('year', type=int, default=datetime.now().year)
        month = request.args.get('month', type=int, default=datetime.now().month)

        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1)
        else:
            end_date = date(year, month + 1, 1)

        orders = Order.query.filter(
            Order.pickup_date >= start_date,
            Order.pickup_date < end_date
        ).all()

        # 按日期分组
        calendar = {}
        for order in orders:
            day = order.pickup_date.day
            if day not in calendar:
                calendar[day] = {
                    'date': order.pickup_date.isoformat(),
                    'total_orders': 0,
                    'orders': []
                }
            calendar[day]['total_orders'] += 1
            calendar[day]['orders'].append({
                'id': order.id,
                'order_no': order.order_no,
                'customer_name': order.customer_name,
                'total_amount': order.total_amount,
                'pickup_time': order.pickup_time,
                'status': order.status
            })

        return jsonify({
            'code': 0,
            'data': {
                'year': year,
                'month': month,
                'calendar': calendar
            }
        })

    # ============================================================
    # 排班管理 API
    # ============================================================
    @app.route('/api/schedules', methods=['GET'])
    def get_schedules():
        """获取排班表"""
        store_id = request.args.get('store_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        query = Schedule.query
        if store_id:
            query = query.filter_by(store_id=store_id)
        if date_from:
            query = query.filter(Schedule.work_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        if date_to:
            query = query.filter(Schedule.work_date <= datetime.strptime(date_to, '%Y-%m-%d').date())

        schedules = query.order_by(Schedule.work_date).all()
        return jsonify({'code': 0, 'data': [s.to_dict() for s in schedules]})

    @app.route('/api/schedules', methods=['POST'])
    def create_schedule():
        """创建排班记录"""
        data = request.get_json()
        required = ['employee_id', 'store_id', 'work_date', 'start_time', 'end_time']
        if not data or not all(k in data for k in required):
            return jsonify({'code': 1, 'message': '缺少必填字段'}), 400

        schedule = Schedule(
            employee_id=data['employee_id'],
            store_id=data['store_id'],
            work_date=datetime.strptime(data['work_date'], '%Y-%m-%d').date(),
            start_time=data['start_time'],
            end_time=data['end_time'],
            notes=data.get('notes', '')
        )
        db.session.add(schedule)
        db.session.commit()
        return jsonify({'code': 0, 'data': schedule.to_dict(), 'message': '排班创建成功'}), 201

    @app.route('/api/shift-requests', methods=['GET'])
    def get_shift_requests():
        """获取调班/请假申请"""
        employee_id = request.args.get('employee_id', type=int)
        status = request.args.get('status')

        query = ShiftRequest.query
        if employee_id:
            query = query.filter_by(employee_id=employee_id)
        if status:
            query = query.filter_by(status=status)

        requests = query.order_by(ShiftRequest.created_at.desc()).all()
        return jsonify({'code': 0, 'data': [r.to_dict() for r in requests]})

    @app.route('/api/shift-requests', methods=['POST'])
    def create_shift_request():
        """创建调班/请假申请"""
        data = request.get_json()
        required = ['employee_id', 'request_type', 'target_date']
        if not data or not all(k in data for k in required):
            return jsonify({'code': 1, 'message': '缺少必填字段'}), 400

        request_obj = ShiftRequest(
            employee_id=data['employee_id'],
            request_type=data['request_type'],
            target_date=datetime.strptime(data['target_date'], '%Y-%m-%d').date(),
            reason=data.get('reason', ''),
            swap_with_employee_id=data.get('swap_with_employee_id')
        )
        db.session.add(request_obj)
        db.session.commit()
        return jsonify({'code': 0, 'data': request_obj.to_dict(), 'message': '申请已提交'}), 201

    @app.route('/api/shift-requests/<int:request_id>/approve', methods=['PUT'])
    def approve_shift_request(request_id):
        """审批调班/请假申请"""
        request_obj = ShiftRequest.query.get_or_404(request_id)
        data = request.get_json()
        status = data.get('status', 'approved')
        request_obj.status = status
        request_obj.approved_by = data.get('approved_by')
        db.session.commit()
        return jsonify({'code': 0, 'data': request_obj.to_dict(), 'message': f'已{status}'})

    # ============================================================
    # 会员管理 API
    # ============================================================
    @app.route('/api/members', methods=['GET'])
    def get_members():
        """获取会员列表"""
        phone = request.args.get('phone')
        query = Member.query
        if phone:
            query = query.filter_by(phone=phone)
        members = query.order_by(Member.total_spent.desc()).all()
        return jsonify({'code': 0, 'data': [m.to_dict() for m in members]})

    @app.route('/api/members', methods=['POST'])
    def create_member():
        """创建会员"""
        data = request.get_json()
        if not data or not data.get('phone'):
            return jsonify({'code': 1, 'message': '手机号不能为空'}), 400

        # 检查是否已存在
        existing = Member.query.filter_by(phone=data['phone']).first()
        if existing:
            return jsonify({'code': 1, 'message': '该手机号已注册'}), 400

        member = Member(
            phone=data['phone'],
            name=data.get('name', ''),
            gender=data.get('gender'),
            birthday=datetime.strptime(data['birthday'], '%Y-%m-%d').date() if data.get('birthday') else None,
            tags=','.join(data.get('tags', [])) if data.get('tags') else ''
        )
        db.session.add(member)
        db.session.commit()
        return jsonify({'code': 0, 'data': member.to_dict(), 'message': '注册成功'}), 201

    # ============================================================
    # 销售记录 API
    # ============================================================
    @app.route('/api/sales', methods=['GET'])
    def get_sales():
        """获取销售记录"""
        store_id = request.args.get('store_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        query = SaleRecord.query
        if store_id:
            query = query.filter_by(store_id=store_id)
        if date_from:
            query = query.filter(SaleRecord.sale_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        if date_to:
            query = query.filter(SaleRecord.sale_date <= datetime.strptime(date_to, '%Y-%m-%d').date())

        records = query.order_by(SaleRecord.sale_date.desc()).limit(200).all()
        return jsonify({'code': 0, 'data': [r.to_dict() for r in records]})

    @app.route('/api/sales', methods=['POST'])
    def create_sale():
        """创建销售记录"""
        data = request.get_json()
        required = ['store_id', 'product_id', 'quantity', 'unit_price']
        if not data or not all(k in data for k in required):
            return jsonify({'code': 1, 'message': '缺少必填字段'}), 400

        total = data['quantity'] * data['unit_price']
        sale = SaleRecord(
            store_id=data['store_id'],
            product_id=data['product_id'],
            member_id=data.get('member_id'),
            quantity=data['quantity'],
            unit_price=data['unit_price'],
            total_amount=total,
            sale_date=datetime.strptime(data.get('sale_date', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date(),
            sale_time=data.get('sale_time', datetime.now().strftime('%H:%M'))
        )

        # 更新会员累计消费
        if data.get('member_id'):
            member = Member.query.get(data['member_id'])
            if member:
                member.total_spent += total
                member.points += int(total)  # 1元=1积分

        # 更新成品库存
        inv = Inventory.query.filter_by(
            store_id=data['store_id'],
            product_id=data['product_id']
        ).first()
        if inv:
            inv.quantity -= data['quantity']

        db.session.add(sale)
        db.session.commit()
        return jsonify({'code': 0, 'data': sale.to_dict(), 'message': '销售记录已创建'}), 201

    # ============================================================
    # 生产记录 API
    # ============================================================
    @app.route('/api/production', methods=['GET'])
    def get_production():
        """获取生产记录"""
        store_id = request.args.get('store_id', type=int)
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')

        query = ProductionRecord.query
        if store_id:
            query = query.filter_by(store_id=store_id)
        if date_from:
            query = query.filter(ProductionRecord.production_date >= datetime.strptime(date_from, '%Y-%m-%d').date())
        if date_to:
            query = query.filter(ProductionRecord.production_date <= datetime.strptime(date_to, '%Y-%m-%d').date())

        records = query.order_by(ProductionRecord.production_date.desc()).all()
        return jsonify({'code': 0, 'data': [r.to_dict() for r in records]})

    @app.route('/api/production', methods=['POST'])
    def create_production():
        """创建生产记录"""
        data = request.get_json()
        required = ['store_id', 'product_id', 'actual_quantity']
        if not data or not all(k in data for k in required):
            return jsonify({'code': 1, 'message': '缺少必填字段'}), 400

        record = ProductionRecord(
            store_id=data['store_id'],
            product_id=data['product_id'],
            planned_quantity=data.get('planned_quantity', 0),
            actual_quantity=data['actual_quantity'],
            waste_quantity=data.get('waste_quantity', 0),
            waste_reason=data.get('waste_reason', ''),
            production_date=datetime.strptime(data.get('production_date', datetime.now().strftime('%Y-%m-%d')), '%Y-%m-%d').date(),
            operator=data.get('operator', '')
        )

        # 更新成品库存（生产入库）
        inv = Inventory.query.filter_by(
            store_id=data['store_id'],
            product_id=data['product_id']
        ).first()
        if not inv:
            inv = Inventory(
                store_id=data['store_id'],
                product_id=data['product_id'],
                quantity=0
            )
            db.session.add(inv)
        inv.quantity += data['actual_quantity'] - data.get('waste_quantity', 0)

        db.session.add(record)
        db.session.commit()
        return jsonify({'code': 0, 'data': record.to_dict(), 'message': '生产记录已创建'}), 201

    # ============================================================
    # 数据看板 API
    # ============================================================
    @app.route('/api/dashboard', methods=['GET'])
    def get_dashboard():
        """获取核心经营数据仪表盘"""
        today = date.today()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)

        # 今日销售额
        today_sales = db.session.query(db.func.sum(SaleRecord.total_amount)).filter(
            SaleRecord.sale_date == today
        ).scalar() or 0.0

        # 本周销售额
        week_sales = db.session.query(db.func.sum(SaleRecord.total_amount)).filter(
            SaleRecord.sale_date >= week_ago
        ).scalar() or 0.0

        # 本月销售额
        month_sales = db.session.query(db.func.sum(SaleRecord.total_amount)).filter(
            SaleRecord.sale_date >= month_ago
        ).scalar() or 0.0

        # 各店销售额
        stores = Store.query.all()
        store_sales = []
        for store in stores:
            store_today = db.session.query(db.func.sum(SaleRecord.total_amount)).filter(
                SaleRecord.store_id == store.id,
                SaleRecord.sale_date == today
            ).scalar() or 0.0
            store_sales.append({
                'store_id': store.id,
                'store_name': store.name,
                'today_sales': store_today
            })

        # 销量Top10产品
        top_products = db.session.query(
            Product.name,
            db.func.sum(SaleRecord.quantity).label('total_qty'),
            db.func.sum(SaleRecord.total_amount).label('total_amount')
        ).join(SaleRecord, Product.id == SaleRecord.product_id).filter(
            SaleRecord.sale_date >= month_ago
        ).group_by(Product.id).order_by(db.desc('total_qty')).limit(10).all()

        # 综合损耗率
        total_production = db.session.query(db.func.sum(ProductionRecord.actual_quantity)).filter(
            ProductionRecord.production_date >= month_ago
        ).scalar() or 0
        total_waste = db.session.query(db.func.sum(ProductionRecord.waste_quantity)).filter(
            ProductionRecord.production_date >= month_ago
        ).scalar() or 0
        waste_rate = round((total_waste / total_production * 100), 2) if total_production > 0 else 0

        # 待处理订单
        pending_orders = Order.query.filter(
            Order.status.in_(['pending', 'confirmed'])
        ).count()

        # 库存预警数量
        alert_count = 0
        for inv in Inventory.query.all():
            if inv.ingredient_id:
                ingredient = Ingredient.query.get(inv.ingredient_id)
                if ingredient and inv.quantity < ingredient.safety_stock:
                    alert_count += 1

        return jsonify({
            'code': 0,
            'data': {
                'today_sales': today_sales,
                'week_sales': week_sales,
                'month_sales': month_sales,
                'store_sales': store_sales,
                'top_products': [
                    {
                        'name': p.name,
                        'total_quantity': int(p.total_qty),
                        'total_amount': float(p.total_amount)
                    }
                    for p in top_products
                ],
                'waste_rate': waste_rate,
                'pending_orders': pending_orders,
                'inventory_alerts': alert_count
            }
        })


def _init_seed_data():
    from datetime import date; today = date.today()
    """初始化种子数据"""
    # 如果已有数据则跳过
    if Store.query.first():
        return

    # 创建门店
    store1 = Store(name='SweetLoaf 总店', location='台南东区', phone='06-1234567')
    store2 = Store(name='SweetLoaf 中西店', location='台南中西区（商圈）', phone='06-2345678')
    store3 = Store(name='SweetLoaf 南区分店', location='台南南区（学区）', phone='06-3456789')
    db.session.add_all([store1, store2, store3])
    db.session.flush()

    # 创建员工
    employees = [
        Employee(name='陈老板', role='店长', store_id=store1.id),
        Employee(name='王师傅', role='烘焙师', store_id=store1.id),
        Employee(name='林师傅', role='烘焙师', store_id=store1.id),
        Employee(name='小李', role='店员', store_id=store1.id),
        Employee(name='小张', role='店员', store_id=store2.id),
        Employee(name='小陈', role='店员', store_id=store2.id),
        Employee(name='阿华', role='烘焙师', store_id=store2.id),
        Employee(name='小美', role='店员', store_id=store3.id),
        Employee(name='阿强', role='烘焙师', store_id=store3.id),
        Employee(name='小婷', role='店员', store_id=store3.id),
        Employee(name='大伟', role='店员', store_id=store1.id),
        Employee(name='雅文', role='店员', store_id=store2.id),
    ]
    db.session.add_all(employees)
    db.session.flush()

    # 创建产品
    products = [
        Product(name='台南桂圆核桃面包', category='面包', price=65, cost=25,
                is_signature=True, is_limited=True,
                description='招牌产品，每日限量供应'),
        Product(name='芒果乳酪蛋糕', category='蛋糕', price=180, cost=70,
                is_signature=True, is_limited=True,
                description='夏季限定，使用新鲜芒果'),
        Product(name='经典可颂', category='面包', price=45, cost=15),
        Product(name='北海道牛奶吐司', category='面包', price=80, cost=30),
        Product(name='巧克力布朗尼', category='蛋糕', price=55, cost=20),
        Product(name='手工蔓越莓饼干', category='饼干', price=35, cost=12),
        Product(name='抹茶红豆面包', category='面包', price=50, cost=18),
        Product(name='奶油泡芙', category='蛋糕', price=40, cost=15),
        Product(name='核桃燕麦饼干', category='饼干', price=38, cost=14),
        Product(name='法式长棍面包', category='面包', price=55, cost=20),
    ]
    db.session.add_all(products)
    db.session.flush()

    # 创建原料
    ingredients = [
        Ingredient(name='高筋面粉', unit='kg', unit_price=25, safety_stock=50, supplier='台南面粉行'),
        Ingredient(name='低筋面粉', unit='kg', unit_price=28, safety_stock=30, supplier='台南面粉行'),
        Ingredient(name='无盐黄油', unit='kg', unit_price=120, safety_stock=20, supplier='进口食材商'),
        Ingredient(name='奶油芝士', unit='kg', unit_price=180, safety_stock=10, supplier='进口食材商'),
        Ingredient(name='细砂糖', unit='kg', unit_price=15, safety_stock=40, supplier='台南糖业'),
        Ingredient(name='鸡蛋', unit='个', unit_price=8, safety_stock=200, supplier='本地农场'),
        Ingredient(name='鲜牛奶', unit='L', unit_price=45, safety_stock=30, supplier='本地牧场'),
        Ingredient(name='桂圆干', unit='kg', unit_price=200, safety_stock=5, supplier='东山农产'),
        Ingredient(name='核桃仁', unit='kg', unit_price=160, safety_stock=8, supplier='坚果批发商'),
        Ingredient(name='芒果果泥', unit='kg', unit_price=90, safety_stock=10, supplier='水果加工厂'),
    ]
    db.session.add_all(ingredients)
    db.session.flush()

    # 创建初始库存
    for store in [store1, store2, store3]:
        for product in products:
            inv = Inventory(
                store_id=store.id,
                product_id=product.id,
                quantity=10  # 每种产品初始10个
            )
            db.session.add(inv)
        for ingredient in ingredients:
            inv = Inventory(
                store_id=store.id,
                ingredient_id=ingredient.id,
                quantity=ingredient.safety_stock * 2  # 初始为安全库存的2倍
            )
            db.session.add(inv)

    # 创建示例订单
    sample_order = Order(
        order_no=f"SL{datetime.now().strftime('%Y%m%d%H%M%S')}01",
        store_id=store1.id,
        customer_name='张小姐',
        customer_phone='0912-345678',
        channel='phone',
        status='confirmed',
        total_amount=360,
        pickup_date=today + timedelta(days=1),
        pickup_time='14:00-15:00',
        notes='生日蛋糕，请写"生日快乐"'
    )
    db.session.add(sample_order)
    db.session.flush()

    # 订单项
    order_item = OrderItem(
        order_id=sample_order.id,
        product_id=products[1].id,  # 芒果乳酪蛋糕
        quantity=2,
        unit_price=180,
        subtotal=360
    )
    db.session.add(order_item)

    # 创建示例会员
    member = Member(
        phone='0912-345678',
        name='张小姐',
        gender='女',
        birthday=date(1995, 5, 20),
        total_spent=3600,
        points=3600,
        level='silver',
        tags='蛋糕控,高客单价'
    )
    db.session.add(member)

    # 创建今日排班
    for emp in employees:
        schedule = Schedule(
            employee_id=emp.id,
            store_id=emp.store_id,
            work_date=today,
            start_time='08:00',
            end_time='17:00',
            status='confirmed'
        )
        db.session.add(schedule)

    db.session.commit()
    print('✅ 种子数据初始化完成')




# ── 仪表盘 UI ──

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, host='0.0.0.0', port=5099)
