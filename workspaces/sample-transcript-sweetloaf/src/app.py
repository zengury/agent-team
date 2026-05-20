"""
SweetLoaf 面包店数字化管理系统 - Flask主入口
"""
import os
import sys
from datetime import datetime, date, timedelta
from flask import Flask, request, jsonify, render_template_string

# 确保能正确导入src包
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import config
from src.models import (
    db, User, Product, RawMaterial, Recipe, Stock, RawMaterialStock,
    Sale, SaleItem, InventoryTransaction, TransferOrder,
    Member, PointsLog, Coupon, MemberCoupon, ProductionSuggestion
)


def create_app(config_name=None):
    """应用工厂"""
    if config_name is None:
        config_name = os.environ.get('FLASK_CONFIG', 'default')

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    db.init_app(app)

    # 注册路由
    register_routes(app)

    return app


def register_routes(app):
    """注册所有路由"""

    # ============================================================
    # 首页 / 状态检查
    # ============================================================
    @app.route('/')
    def index():
        return jsonify({
            'app': 'SweetLoaf 面包店数字化管理系统',
            'version': '1.0.0',
            'status': 'running',
            'timestamp': datetime.utcnow().isoformat(),
        })

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok'})

    # ============================================================
    # 员工管理 API
    # ============================================================
    @app.route('/api/users', methods=['GET'])
    def list_users():
        users = User.query.all()
        return jsonify([u.to_dict() for u in users])

    @app.route('/api/users', methods=['POST'])
    def create_user():
        data = request.get_json()
        if not data or not data.get('username'):
            return jsonify({'error': '用户名不能为空'}), 400
        if User.query.filter_by(username=data['username']).first():
            return jsonify({'error': '用户名已存在'}), 400

        user = User(
            username=data['username'],
            display_name=data.get('display_name', data['username']),
            role=data.get('role', 'cashier'),
            store_code=data.get('store_code'),
            phone=data.get('phone'),
        )
        user.set_password(data.get('password', '123456'))
        db.session.add(user)
        db.session.commit()
        return jsonify(user.to_dict()), 201

    # ============================================================
    # 产品管理 API
    # ============================================================
    @app.route('/api/products', methods=['GET'])
    def list_products():
        products = Product.query.filter_by(is_active=True).all()
        return jsonify([p.to_dict() for p in products])

    @app.route('/api/products', methods=['POST'])
    def create_product():
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': '产品名称不能为空'}), 400

        product = Product(
            name=data['name'],
            category=data.get('category', '面包'),
            price=data.get('price', 0.0),
            cost=data.get('cost', 0.0),
            unit=data.get('unit', '个'),
        )
        db.session.add(product)
        db.session.commit()

        # 为所有门店初始化库存为0
        from src.config import Config
        for store_code in Config.STORES:
            stock = Stock(product_id=product.id, store_code=store_code, quantity=0)
            db.session.add(stock)
        db.session.commit()

        return jsonify(product.to_dict()), 201

    # ============================================================
    # 原材料管理 API
    # ============================================================
    @app.route('/api/materials', methods=['GET'])
    def list_materials():
        materials = RawMaterial.query.filter_by(is_active=True).all()
        return jsonify([m.to_dict() for m in materials])

    @app.route('/api/materials', methods=['POST'])
    def create_material():
        data = request.get_json()
        if not data or not data.get('name'):
            return jsonify({'error': '原材料名称不能为空'}), 400

        material = RawMaterial(
            name=data['name'],
            unit=data.get('unit', '公斤'),
            min_stock=data.get('min_stock', 0.0),
        )
        db.session.add(material)
        db.session.commit()

        # 为所有门店初始化库存为0
        from src.config import Config
        for store_code in Config.STORES:
            stock = RawMaterialStock(material_id=material.id, store_code=store_code, quantity=0)
            db.session.add(stock)
        db.session.commit()

        return jsonify(material.to_dict()), 201

    # ============================================================
    # 配方管理 API
    # ============================================================
    @app.route('/api/recipes', methods=['GET'])
    def list_recipes():
        product_id = request.args.get('product_id', type=int)
        query = Recipe.query
        if product_id:
            query = query.filter_by(product_id=product_id)
        recipes = query.all()
        return jsonify([r.to_dict() for r in recipes])

    @app.route('/api/recipes', methods=['POST'])
    def create_recipe():
        data = request.get_json()
        if not data:
            return jsonify({'error': '数据不能为空'}), 400

        recipe = Recipe(
            product_id=data['product_id'],
            material_id=data['material_id'],
            quantity=data.get('quantity', 0.0),
        )
        db.session.add(recipe)
        db.session.commit()
        return jsonify(recipe.to_dict()), 201

    # ============================================================
    # 库存管理 API
    # ============================================================
    @app.route('/api/stocks', methods=['GET'])
    def list_stocks():
        store_code = request.args.get('store_code')
        product_id = request.args.get('product_id', type=int)
        query = Stock.query
        if store_code:
            query = query.filter_by(store_code=store_code)
        if product_id:
            query = query.filter_by(product_id=product_id)
        stocks = query.all()
        result = []
        for s in stocks:
            d = s.to_dict()
            # 检查是否需要预警
            from src.config import Config
            if s.quantity < Config.STOCK_ALERT_THRESHOLD:
                d['alert'] = True
            else:
                d['alert'] = False
            result.append(d)
        return jsonify(result)

    @app.route('/api/materials/stocks', methods=['GET'])
    def list_material_stocks():
        store_code = request.args.get('store_code')
        query = RawMaterialStock.query
        if store_code:
            query = query.filter_by(store_code=store_code)
        stocks = query.all()
        return jsonify([s.to_dict() for s in stocks])

    # ============================================================
    # 原材料入库 API
    # ============================================================
    @app.route('/api/inventory/purchase', methods=['POST'])
    def purchase_material():
        """原材料采购入库"""
        data = request.get_json()
        if not data:
            return jsonify({'error': '数据不能为空'}), 400

        material_id = data['material_id']
        store_code = data.get('store_code', 'main')
        quantity = data['quantity']
        unit_price = data.get('unit_price')

        material = RawMaterial.query.get(material_id)
        if not material:
            return jsonify({'error': '原材料不存在'}), 404

        # 更新库存
        stock = RawMaterialStock.query.filter_by(
            material_id=material_id, store_code=store_code
        ).first()
        if not stock:
            stock = RawMaterialStock(material_id=material_id, store_code=store_code, quantity=0)
            db.session.add(stock)
        stock.quantity += quantity

        # 记录交易
        transaction = InventoryTransaction(
            transaction_type='purchase',
            item_type='material',
            item_id=material_id,
            store_code=store_code,
            quantity=quantity,
            unit_price=unit_price,
            note=data.get('note', '采购入库'),
        )
        db.session.add(transaction)
        db.session.commit()

        return jsonify({
            'message': '入库成功',
            'stock': stock.to_dict(),
            'transaction': transaction.to_dict(),
        }), 201

    # ============================================================
    # 生产管理 API
    # ============================================================
    @app.route('/api/production', methods=['POST'])
    def produce_product():
        """生产产品：消耗原材料，增加成品库存"""
        data = request.get_json()
        if not data:
            return jsonify({'error': '数据不能为空'}), 400

        product_id = data['product_id']
        quantity = data['quantity']
        store_code = data.get('store_code', 'main')

        product = Product.query.get(product_id)
        if not product:
            return jsonify({'error': '产品不存在'}), 404

        # 获取配方
        recipes = Recipe.query.filter_by(product_id=product_id).all()
        if not recipes:
            return jsonify({'error': '该产品没有配方，无法生产'}), 400

        # 检查原材料是否充足并扣减
        for recipe in recipes:
            material_stock = RawMaterialStock.query.filter_by(
                material_id=recipe.material_id, store_code=store_code
            ).first()
            if not material_stock or material_stock.quantity < recipe.quantity * quantity:
                material = RawMaterial.query.get(recipe.material_id)
                return jsonify({
                    'error': f'原材料 {material.name if material else "未知"} 库存不足'
                }), 400

        # 扣减原材料
        for recipe in recipes:
            material_stock = RawMaterialStock.query.filter_by(
                material_id=recipe.material_id, store_code=store_code
            ).first()
            consume_qty = recipe.quantity * quantity
            material_stock.quantity -= consume_qty

            # 记录原材料消耗
            transaction = InventoryTransaction(
                transaction_type='production_consume',
                item_type='material',
                item_id=recipe.material_id,
                store_code=store_code,
                quantity=-consume_qty,
                note=f'生产 {product.name} x{quantity}',
            )
            db.session.add(transaction)

        # 增加成品库存
        stock = Stock.query.filter_by(product_id=product_id, store_code=store_code).first()
        if not stock:
            stock = Stock(product_id=product_id, store_code=store_code, quantity=0)
            db.session.add(stock)
        stock.quantity += quantity

        # 记录成品入库
        transaction = InventoryTransaction(
            transaction_type='production_in',
            item_type='product',
            item_id=product_id,
            store_code=store_code,
            quantity=quantity,
            note=f'生产入库 {product.name} x{quantity}',
        )
        db.session.add(transaction)
        db.session.commit()

        return jsonify({
            'message': f'成功生产 {product.name} x{quantity}',
            'product_stock': stock.to_dict(),
        }), 201

    # ============================================================
    # 销售 API
    # ============================================================
    @app.route('/api/sales', methods=['POST'])
    def create_sale():
        """创建销售记录"""
        data = request.get_json()
        if not data:
            return jsonify({'error': '数据不能为空'}), 400

        store_code = data.get('store_code', 'main')
        items_data = data.get('items', [])
        if not items_data:
            return jsonify({'error': '销售明细不能为空'}), 400

        member_id = data.get('member_id')
        cashier_id = data.get('cashier_id')
        payment_method = data.get('payment_method', '现金')
        coupon_id = data.get('coupon_id')

        total_amount = 0.0
        sale_items = []

        # 检查库存并计算总价
        for item_data in items_data:
            product_id = item_data['product_id']
            quantity = item_data['quantity']

            product = Product.query.get(product_id)
            if not product:
                return jsonify({'error': f'产品ID {product_id} 不存在'}), 404

            # 检查库存
            stock = Stock.query.filter_by(product_id=product_id, store_code=store_code).first()
            if not stock or stock.quantity < quantity:
                return jsonify({'error': f'{product.name} 库存不足'}), 400

            unit_price = item_data.get('unit_price', product.price)
            subtotal = unit_price * quantity
            total_amount += subtotal

            sale_items.append({
                'product_id': product_id,
                'quantity': quantity,
                'unit_price': unit_price,
                'subtotal': subtotal,
                'product': product,
            })

        # 计算折扣
        discount_amount = 0.0
        if coupon_id and member_id:
            member_coupon = MemberCoupon.query.filter_by(
                member_id=member_id, coupon_id=coupon_id, is_used=False
            ).first()
            if member_coupon:
                coupon = Coupon.query.get(coupon_id)
                if coupon and coupon.is_active:
                    if coupon.coupon_type == 'cash' and total_amount >= (coupon.condition_amount or 0):
                        discount_amount = coupon.value
                    elif coupon.coupon_type == 'discount':
                        discount_amount = total_amount * (1 - coupon.value)

        # 会员折扣
        member_discount = 0.0
        if member_id:
            member = Member.query.get(member_id)
            if member:
                from src.config import Config
                level_info = Config.MEMBER_LEVELS.get(member.level, {})
                discount_rate = level_info.get('discount', 1.0)
                if discount_rate < 1.0:
                    member_discount = total_amount * (1 - discount_rate)

        final_discount = max(discount_amount, member_discount)
        final_amount = total_amount - final_discount

        # 创建销售单
        sale = Sale(
            store_code=store_code,
            total_amount=total_amount,
            discount_amount=final_discount,
            final_amount=final_amount,
            payment_method=payment_method,
            member_id=member_id,
            cashier_id=cashier_id,
        )
        db.session.add(sale)
        db.session.flush()  # 获取sale.id

        # 创建销售明细并扣减库存
        for item_data in sale_items:
            sale_item = SaleItem(
                sale_id=sale.id,
                product_id=item_data['product_id'],
                quantity=item_data['quantity'],
                unit_price=item_data['unit_price'],
                subtotal=item_data['subtotal'],
            )
            db.session.add(sale_item)

            # 扣减库存
            stock = Stock.query.filter_by(
                product_id=item_data['product_id'], store_code=store_code
            ).first()
            if stock:
                stock.quantity -= item_data['quantity']

            # 记录库存变动
            transaction = InventoryTransaction(
                transaction_type='sale',
                item_type='product',
                item_id=item_data['product_id'],
                store_code=store_code,
                quantity=-item_data['quantity'],
                reference_id=sale.id,
                note=f'销售出库',
            )
            db.session.add(transaction)

        # 处理会员积分
        if member_id:
            member = Member.query.get(member_id)
            if member:
                from src.config import Config
                points_earned = int(final_amount / Config.POINTS_RATIO)
                member.points += points_earned
                member.total_spent += final_amount
                member.last_visit_at = datetime.utcnow()
                member.calculate_level()

                points_log = PointsLog(
                    member_id=member_id,
                    points_change=points_earned,
                    reason='purchase',
                    reference_id=sale.id,
                )
                db.session.add(points_log)

        # 标记优惠券已使用
        if coupon_id and member_id:
            member_coupon = MemberCoupon.query.filter_by(
                member_id=member_id, coupon_id=coupon_id, is_used=False
            ).first()
            if member_coupon:
                member_coupon.is_used = True
                member_coupon.used_at = datetime.utcnow()
                member_coupon.sale_id = sale.id

        db.session.commit()

        return jsonify(sale.to_dict()), 201

    @app.route('/api/sales', methods=['GET'])
    def list_sales():
        """查询销售记录"""
        store_code = request.args.get('store_code')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        member_id = request.args.get('member_id', type=int)

        query = Sale.query
        if store_code:
            query = query.filter_by(store_code=store_code)
        if member_id:
            query = query.filter_by(member_id=member_id)
        if start_date:
            query = query.filter(Sale.created_at >= datetime.fromisoformat(start_date))
        if end_date:
            query = query.filter(Sale.created_at <= datetime.fromisoformat(end_date))

        sales = query.order_by(Sale.created_at.desc()).all()
        return jsonify([s.to_dict() for s in sales])

    # ============================================================
    # 销售数据看板 API
    # ============================================================
    @app.route('/api/dashboard/summary', methods=['GET'])
    def dashboard_summary():
        """销售数据看板汇总"""
        period = request.args.get('period', 'today')
        store_code = request.args.get('store_code')

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if period == 'today':
            start_date = today_start
        elif period == 'week':
            start_date = today_start - timedelta(days=now.weekday())
        elif period == 'month':
            start_date = today_start.replace(day=1)
        else:
            start_date = today_start

        query = Sale.query.filter(Sale.created_at >= start_date)
        if store_code:
            query = query.filter_by(store_code=store_code)

        sales = query.all()
        total_revenue = sum(s.final_amount for s in sales)
        total_orders = len(sales)
        avg_order_value = total_revenue / total_orders if total_orders > 0 else 0

        # 按门店统计
        from src.config import Config
        store_revenue = {}
        for code, info in Config.STORES.items():
            store_sales = [s for s in sales if s.store_code == code]
            store_revenue[code] = {
                'name': info['name'],
                'revenue': sum(s.final_amount for s in store_sales),
                'orders': len(store_sales),
            }

        return jsonify({
            'period': period,
            'total_revenue': round(total_revenue, 2),
            'total_orders': total_orders,
            'avg_order_value': round(avg_order_value, 2),
            'store_revenue': store_revenue,
        })

    @app.route('/api/dashboard/top-products', methods=['GET'])
    def top_products():
        """热销/滞销产品排行榜"""
        period = request.args.get('period', 'today')
        store_code = request.args.get('store_code')
        limit = request.args.get('limit', 10, type=int)

        now = datetime.utcnow()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        if period == 'today':
            start_date = today_start
        elif period == 'week':
            start_date = today_start - timedelta(days=now.weekday())
        elif period == 'month':
            start_date = today_start.replace(day=1)
        else:
            start_date = today_start

        query = SaleItem.query.join(Sale).filter(Sale.created_at >= start_date)
        if store_code:
            query = query.filter(Sale.store_code == store_code)

        items = query.all()

        # 汇总产品销量
        product_sales = {}
        for item in items:
            pid = item.product_id
            if pid not in product_sales:
                product_sales[pid] = {
                    'product_id': pid,
                    'product_name': item.product.name if item.product else '未知',
                    'total_quantity': 0,
                    'total_revenue': 0,
                }
            product_sales[pid]['total_quantity'] += item.quantity
            product_sales[pid]['total_revenue'] += item.subtotal

        sorted_products = sorted(product_sales.values(), key=lambda x: x['total_quantity'], reverse=True)

        top = sorted_products[:limit]
        bottom = sorted_products[-limit:] if len(sorted_products) > limit else []

        return jsonify({
            'top': top,
            'bottom': list(reversed(bottom)),
        })

    # ============================================================
    # 调拨管理 API
    # ============================================================
    @app.route('/api/transfers', methods=['POST'])
    def create_transfer():
        """创建调拨申请"""
        data = request.get_json()
        if not data:
            return jsonify({'error': '数据不能为空'}), 400

        product_id = data['product_id']
        quantity = data['quantity']
        from_store = data['from_store']
        to_store = data['to_store']
        requester_id = data.get('requester_id')

        # 检查库存
        stock = Stock.query.filter_by(product_id=product_id, store_code=from_store).first()
        if not stock or stock.quantity < quantity:
            return jsonify({'error': '调出门店库存不足'}), 400

        transfer = TransferOrder(
            product_id=product_id,
            quantity=quantity,
            from_store=from_store,
            to_store=to_store,
            status='pending',
            requester_id=requester_id,
            note=data.get('note'),
        )
        db.session.add(transfer)
        db.session.commit()

        return jsonify(transfer.to_dict()), 201

    @app.route('/api/transfers', methods=['GET'])
    def list_transfers():
        """查询调拨单"""
        status = request.args.get('status')
        query = TransferOrder.query
        if status:
            query = query.filter_by(status=status)
        transfers = query.order_by(TransferOrder.created_at.desc()).all()
        return jsonify([t.to_dict() for t in transfers])

    @app.route('/api/transfers/<int:transfer_id>/approve', methods=['POST'])
    def approve_transfer(transfer_id):
        """审批调拨单"""
        transfer = TransferOrder.query.get_or_404(transfer_id)
        data = request.get_json() or {}

        if transfer.status != 'pending':
            return jsonify({'error': '调拨单状态不正确'}), 400

        transfer.status = 'approved'
        transfer.approver_id = data.get('approver_id')
        db.session.commit()

        return jsonify(transfer.to_dict())

    @app.route('/api/transfers/<int:transfer_id>/deliver', methods=['POST'])
    def deliver_transfer(transfer_id):
        """执行调拨（扣减调出方库存，增加调入方库存）"""
        transfer = TransferOrder.query.get_or_404(transfer_id)
        data = request.get_json() or {}

        if transfer.status != 'approved':
            return jsonify({'error': '调拨单未审批或已完成'}), 400

        # 扣减调出方库存
        from_stock = Stock.query.filter_by(
            product_id=transfer.product_id, store_code=transfer.from_store
        ).first()
        if not from_stock or from_stock.quantity < transfer.quantity:
            return jsonify({'error': '调出方库存不足'}), 400
        from_stock.quantity -= transfer.quantity

        # 增加调入方库存
        to_stock = Stock.query.filter_by(
            product_id=transfer.product_id, store_code=transfer.to_store
        ).first()
        if not to_stock:
            to_stock = Stock(product_id=transfer.product_id, store_code=transfer.to_store, quantity=0)
            db.session.add(to_stock)
        to_stock.quantity += transfer.quantity

        # 记录交易
        out_transaction = InventoryTransaction(
            transaction_type='transfer_out',
            item_type='product',
            item_id=transfer.product_id,
            store_code=transfer.from_store,
            quantity=-transfer.quantity,
            reference_id=transfer.id,
            note=f'调拨至{transfer.to_store}',
        )
        db.session.add(out_transaction)

        in_transaction = InventoryTransaction(
            transaction_type='transfer_in',
            item_type='product',
            item_id=transfer.product_id,
            store_code=transfer.to_store,
            quantity=transfer.quantity,
            reference_id=transfer.id,
            note=f'从{transfer.from_store}调拨',
        )
        db.session.add(in_transaction)

        transfer.status = 'delivered'
        transfer.driver_id = data.get('driver_id')
        db.session.commit()

        return jsonify(transfer.to_dict())

    # ============================================================
    # 会员管理 API
    # ============================================================
    @app.route('/api/members', methods=['GET'])
    def list_members():
        members = Member.query.all()
        return jsonify([m.to_dict() for m in members])

    @app.route('/api/members', methods=['POST'])
    def create_member():
        """注册会员"""
        data = request.get_json()
        if not data or not data.get('phone'):
            return jsonify({'error': '手机号不能为空'}), 400

        existing = Member.query.filter_by(phone=data['phone']).first()
        if existing:
            return jsonify(existing.to_dict())

        member = Member(
            phone=data['phone'],
            name=data.get('name'),
            birthday=datetime.strptime(data['birthday'], '%Y-%m-%d').date() if data.get('birthday') else None,
        )
        db.session.add(member)
        db.session.commit()

        return jsonify(member.to_dict()), 201

    @app.route('/api/members/<int:member_id>', methods=['GET'])
    def get_member(member_id):
        member = Member.query.get_or_404(member_id)
        return jsonify(member.to_dict())

    @app.route('/api/members/phone/<phone>', methods=['GET'])
    def get_member_by_phone(phone):
        member = Member.query.filter_by(phone=phone).first()
        if not member:
            return jsonify({'error': '会员不存在'}), 404
        return jsonify(member.to_dict())

    @app.route('/api/members/<int:member_id>/points', methods=['GET'])
    def get_member_points_log(member_id):
        logs = PointsLog.query.filter_by(member_id=member_id).order_by(
            PointsLog.created_at.desc()
        ).all()
        return jsonify([l.to_dict() for l in logs])

    @app.route('/api/members/<int:member_id>/exchange', methods=['POST'])
    def exchange_points(member_id):
        """积分兑换"""
        member = Member.query.get_or_404(member_id)
        data = request.get_json()
        if not data or not data.get('points'):
            return jsonify({'error': '积分数量不能为空'}), 400

        points_to_exchange = data['points']
        if member.points < points_to_exchange:
            return jsonify({'error': '积分不足'}), 400

        from src.config import Config
        exchange_amount = points_to_exchange / Config.POINTS_EXCHANGE_RATE

        member.points -= points_to_exchange

        log = PointsLog(
            member_id=member_id,
            points_change=-points_to_exchange,
            reason='exchange',
            note=f'兑换{exchange_amount}元',
        )
        db.session.add(log)
        db.session.commit()

        return jsonify({
            'message': f'成功兑换{exchange_amount}元',
            'member': member.to_dict(),
        })

    # ============================================================
    # 优惠券管理 API
    # ============================================================
    @app.route('/api/coupons', methods=['GET'])
    def list_coupons():
        coupons = Coupon.query.all()
        return jsonify([c.to_dict() for c in coupons])

    @app.route('/api/coupons', methods=['POST'])
    def create_coupon():
        data = request.get_json()
        if not data:
            return jsonify({'error': '数据不能为空'}), 400

        coupon = Coupon(
            name=data['name'],
            coupon_type=data['coupon_type'],
            condition_amount=data.get('condition_amount'),
            value=data['value'],
            start_date=datetime.fromisoformat(data['start_date']) if data.get('start_date') else None,
            end_date=datetime.fromisoformat(data['end_date']) if data.get('end_date') else None,
        )
        db.session.add(coupon)
        db.session.commit()
        return jsonify(coupon.to_dict()), 201

    @app.route('/api/coupons/<int:coupon_id>/send', methods=['POST'])
    def send_coupon_to_members(coupon_id):
        """向会员发送优惠券"""
        coupon = Coupon.query.get_or_404(coupon_id)
        data = request.get_json() or {}
        member_ids = data.get('member_ids', [])

        if not member_ids:
            # 如果没有指定会员，发送给所有活跃会员
            members = Member.query.filter_by(is_active=True).all()
            member_ids = [m.id for m in members]

        sent_count = 0
        for mid in member_ids:
            existing = MemberCoupon.query.filter_by(member_id=mid, coupon_id=coupon_id, is_used=False).first()
            if not existing:
                mc = MemberCoupon(member_id=mid, coupon_id=coupon_id)
                db.session.add(mc)
                sent_count += 1

        db.session.commit()
        return jsonify({'message': f'成功向{sent_count}位会员发送优惠券'})

    @app.route('/api/members/<int:member_id>/coupons', methods=['GET'])
    def get_member_coupons(member_id):
        coupons = MemberCoupon.query.filter_by(member_id=member_id).all()
        return jsonify([c.to_dict() for c in coupons])

    # ============================================================
    # 生产建议 API
    # ============================================================
    @app.route('/api/production-suggestions', methods=['GET'])
    def get_production_suggestions():
        """获取生产建议"""
        target_date_str = request.args.get('date')
        if target_date_str:
            target_date = datetime.strptime(target_date_str, '%Y-%m-%d').date()
        else:
            target_date = date.today() + timedelta(days=1)

        suggestions = ProductionSuggestion.query.filter_by(
            suggested_date=target_date
        ).all()

        if not suggestions:
            # 自动生成建议
            suggestions = generate_suggestions(target_date)

        return jsonify([s.to_dict() for s in suggestions])

    def generate_suggestions(target_date):
        """基于历史数据生成生产建议"""
        from src.config import Config
        days = Config.PRODUCTION_FORECAST_DAYS
        start_date = datetime.combine(target_date - timedelta(days=days), datetime.min.time())

        products = Product.query.filter_by(is_active=True).all()
        suggestions = []

        for product in products:
            # 查询过去N天的销量
            sales_data = db.session.query(
                db.func.sum(SaleItem.quantity)
            ).join(Sale).filter(
                SaleItem.product_id == product.id,
                Sale.created_at >= start_date,
            ).scalar() or 0

            avg_daily = sales_data / days if days > 0 else 0
            suggested_qty = max(1, int(avg_daily * 1.15))  # 建议量 = 平均销量 * 1.15

            suggestion = ProductionSuggestion(
                product_id=product.id,
                suggested_date=target_date,
                suggested_quantity=suggested_qty,
                reason=f'基于过去{days}天平均销量{avg_daily:.1f}，上浮15%',
            )
            db.session.add(suggestion)
            suggestions.append(suggestion)

        db.session.commit()
        return suggestions

    @app.route('/api/production-suggestions/<int:suggestion_id>/adjust', methods=['POST'])
    def adjust_suggestion(suggestion_id):
        """师傅调整生产建议"""
        suggestion = ProductionSuggestion.query.get_or_404(suggestion_id)
        data = request.get_json()
        if not data or 'actual_quantity' not in data:
            return jsonify({'error': '请提供调整后的数量'}), 400

        suggestion.actual_quantity = data['actual_quantity']
        suggestion.is_adjusted = True
        db.session.commit()

        return jsonify(suggestion.to_dict())

    # ============================================================
    # 库存交易记录 API
    # ============================================================
    @app.route('/api/inventory-transactions', methods=['GET'])
    def list_inventory_transactions():
        store_code = request.args.get('store_code')
        transaction_type = request.args.get('transaction_type')
        limit = request.args.get('limit', 50, type=int)

        query = InventoryTransaction.query
        if store_code:
            query = query.filter_by(store_code=store_code)
        if transaction_type:
            query = query.filter_by(transaction_type=transaction_type)

        transactions = query.order_by(
            InventoryTransaction.created_at.desc()
        ).limit(limit).all()

        return jsonify([t.to_dict() for t in transactions])

    # ============================================================
    # 库存预警 API
    # ============================================================
    @app.route('/api/alerts', methods=['GET'])
    def get_alerts():
        """获取所有库存预警"""
        from src.config import Config
        threshold = Config.STOCK_ALERT_THRESHOLD
        alerts = []

        # 成品库存预警
        low_stocks = Stock.query.filter(Stock.quantity < threshold).all()
        for s in low_stocks:
            alerts.append({
                'type': 'product',
                'product_id': s.product_id,
                'product_name': s.product.name if s.product else '',
                'store_code': s.store_code,
                'current_quantity': s.quantity,
                'threshold': threshold,
                'message': f'【库存预警】{s.store_code}店 {s.product.name if s.product else ""} 库存仅剩 {s.quantity} 个',
            })

        # 原材料库存预警
        low_materials = RawMaterialStock.query.join(RawMaterial).filter(
            RawMaterialStock.quantity < RawMaterial.min_stock
        ).all()
        for s in low_materials:
            alerts.append({
                'type': 'material',
                'material_id': s.material_id,
                'material_name': s.material.name if s.material else '',
                'store_code': s.store_code,
                'current_quantity': s.quantity,
                'min_stock': s.material.min_stock if s.material else 0,
                'message': f'【原材料预警】{s.store_code}店 {s.material.name if s.material else ""} 库存 {s.quantity}，低于最低库存 {s.material.min_stock if s.material else 0}',
            })

        return jsonify(alerts)

    # ============================================================
    # 生日会员查询 API（营销用）
    # ============================================================
    @app.route('/api/members/birthday-today', methods=['GET'])
    def birthday_members_today():
        """查询今天生日的会员"""
        today = date.today()
        members = Member.query.filter(
            db.extract('month', Member.birthday) == today.month,
            db.extract('day', Member.birthday) == today.day,
            Member.is_active == True,
        ).all()
        return jsonify([m.to_dict() for m in members])


# ============================================================
# 初始化数据库
# ============================================================
def init_db(app):
    """初始化数据库并插入示例数据"""
    with app.app_context():
        db.create_all()

        # 检查是否已有数据
        if User.query.first():
            return

        # 创建管理员用户
        admin = User(
            username='admin',
            display_name='陈老板',
            role='admin',
            store_code='main',
            phone='0912345678',
        )
        admin.set_password('admin123')
        db.session.add(admin)

        # 创建门店员工
        users_data = [
            ('manager_east', '东区店长', 'manager', 'east', '0911111111'),
            ('manager_central', '中西区店长', 'manager', 'central', '0922222222'),
            ('manager_north', '北区店长', 'manager', 'north', '0933333333'),
            ('baker1', '阿旺师傅', 'baker', 'main', '0944444444'),
            ('cashier1', '小美', 'cashier', 'east', '0955555555'),
            ('cashier2', '阿花', 'cashier', 'central', '0966666666'),
            ('driver1', '阿强', 'driver', 'main', '0977777777'),
        ]
        for username, display_name, role, store_code, phone in users_data:
            user = User(
                username=username,
                display_name=display_name,
                role=role,
                store_code=store_code,
                phone=phone,
            )
            user.set_password('123456')
            db.session.add(user)

        # 创建产品
        products_data = [
            ('台南红豆包', '面包', 45, 18),
            ('奶油吐司', '面包', 60, 25),
            ('法式长棍', '面包', 80, 30),
            ('巧克力蛋糕', '蛋糕', 120, 50),
            ('蛋挞', '蛋糕', 35, 15),
            ('鲜奶泡芙', '蛋糕', 50, 22),
            ('美式咖啡', '饮品', 40, 10),
            ('鲜奶茶', '饮品', 55, 15),
        ]
        products = []
        for name, category, price, cost in products_data:
            product = Product(name=name, category=category, price=price, cost=cost)
            db.session.add(product)
            db.session.flush()
            products.append(product)

            # 初始化各门店库存
            from src.config import Config
            for store_code in Config.STORES:
                stock = Stock(product_id=product.id, store_code=store_code, quantity=0)
                db.session.add(stock)

        # 创建原材料
        materials_data = [
            ('高筋面粉', '公斤', 50),
            ('低筋面粉', '公斤', 30),
            ('黄油', '公斤', 20),
            ('糖', '公斤', 40),
            ('鸡蛋', '个', 200),
            ('牛奶', '升', 30),
            ('酵母', '包', 10),
            ('红豆馅', '公斤', 15),
        ]
        materials = []
        for name, unit, min_stock in materials_data:
            material = RawMaterial(name=name, unit=unit, min_stock=min_stock)
            db.session.add(material)
            db.session.flush()
            materials.append(material)

            # 初始化各门店原材料库存
            from src.config import Config
            for store_code in Config.STORES:
                stock = RawMaterialStock(material_id=material.id, store_code=store_code, quantity=0)
                db.session.add(stock)

        # 创建配方（红豆包）
        recipe_data = [
            (products[0].id, materials[0].id, 0.2),  # 红豆包 -> 高筋面粉 0.2公斤
            (products[0].id, materials[3].id, 0.05),  # 红豆包 -> 糖 0.05公斤
            (products[0].id, materials[6].id, 0.01),  # 红豆包 -> 酵母 0.01包
            (products[0].id, materials[7].id, 0.1),   # 红豆包 -> 红豆馅 0.1公斤
            (products[1].id, materials[0].id, 0.3),   # 奶油吐司 -> 高筋面粉
            (products[1].id, materials[2].id, 0.05),  # 奶油吐司 -> 黄油
            (products[1].id, materials[4].id, 1),     # 奶油吐司 -> 鸡蛋 1个
            (products[2].id, materials[0].id, 0.25),  # 法式长棍 -> 高筋面粉
            (products[2].id, materials[6].id, 0.01),  # 法式长棍 -> 酵母
        ]
        for product_id, material_id, qty in recipe_data:
            recipe = Recipe(product_id=product_id, material_id=material_id, quantity=qty)
            db.session.add(recipe)

        # 创建示例会员
        members_data = [
            ('0911111111', '王小明', '2026-05-15'),
            ('0922222222', '林美丽', '2026-05-16'),
            ('0933333333', '张大明', '2026-05-10'),
        ]
        for phone, name, birthday_str in members_data:
            member = Member(
                phone=phone,
                name=name,
                points=100,
                total_spent=1000,
                birthday=datetime.strptime(birthday_str, '%Y-%m-%d').date(),
            )
            db.session.add(member)

        # 创建示例优惠券
        coupon = Coupon(
            name='满100减15',
            coupon_type='cash',
            condition_amount=100,
            value=15,
            is_active=True,
        )
        db.session.add(coupon)

        db.session.commit()
        print('数据库初始化完成！')


# ============================================================
# 主入口
# ============================================================
app = create_app(os.environ.get('FLASK_CONFIG', 'default'))


if __name__ == '__main__':
    init_db(app)
    app.run(host='0.0.0.0', port=5000, debug=True)
