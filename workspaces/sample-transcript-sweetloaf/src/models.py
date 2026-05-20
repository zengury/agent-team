"""
SweetLoaf 面包店数字化管理系统 - 数据库模型
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, timedelta
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()


# ============================================================
# 员工与用户模型
# ============================================================

class User(db.Model):
    """系统用户（员工）"""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    display_name = db.Column(db.String(64), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='cashier')
    # role: 'admin' (老板), 'manager' (店长), 'cashier' (收银员), 'baker' (师傅), 'driver' (司机)
    store_code = db.Column(db.String(20), nullable=True)  # 所属门店
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'display_name': self.display_name,
            'role': self.role,
            'store_code': self.store_code,
            'phone': self.phone,
            'is_active': self.is_active,
        }


# ============================================================
# 产品与库存模型
# ============================================================

class Product(db.Model):
    """产品（面包/糕点/饮品）"""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False, default='面包')
    # category: '面包', '蛋糕', '饮品', '其他'
    price = db.Column(db.Float, nullable=False, default=0.0)
    cost = db.Column(db.Float, nullable=True, default=0.0)  # 成本
    unit = db.Column(db.String(20), default='个')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 库存关系
    stocks = db.relationship('Stock', backref='product', lazy='dynamic')
    # 配方关系
    recipes = db.relationship('Recipe', backref='product', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'price': self.price,
            'cost': self.cost,
            'unit': self.unit,
            'is_active': self.is_active,
        }


class RawMaterial(db.Model):
    """原材料"""
    __tablename__ = 'raw_materials'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    unit = db.Column(db.String(20), default='公斤')
    min_stock = db.Column(db.Float, default=0.0)  # 最低库存预警
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    stocks = db.relationship('RawMaterialStock', backref='material', lazy='dynamic')
    recipes = db.relationship('Recipe', backref='material', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'unit': self.unit,
            'min_stock': self.min_stock,
            'is_active': self.is_active,
        }


class Recipe(db.Model):
    """产品配方（生产一个产品需要消耗的原材料）"""
    __tablename__ = 'recipes'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=0.0)  # 消耗量

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'material_id': self.material_id,
            'material_name': self.material.name if self.material else '',
            'quantity': self.quantity,
        }


class Stock(db.Model):
    """成品库存（按门店）"""
    __tablename__ = 'stocks'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    store_code = db.Column(db.String(20), nullable=False, default='main')
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'store_code': self.store_code,
            'quantity': self.quantity,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class RawMaterialStock(db.Model):
    """原材料库存（按门店）"""
    __tablename__ = 'raw_material_stocks'

    id = db.Column(db.Integer, primary_key=True)
    material_id = db.Column(db.Integer, db.ForeignKey('raw_materials.id'), nullable=False)
    store_code = db.Column(db.String(20), nullable=False, default='main')
    quantity = db.Column(db.Float, nullable=False, default=0.0)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'material_id': self.material_id,
            'material_name': self.material.name if self.material else '',
            'store_code': self.store_code,
            'quantity': self.quantity,
        }


# ============================================================
# 交易与流水模型
# ============================================================

class Sale(db.Model):
    """销售记录"""
    __tablename__ = 'sales'

    id = db.Column(db.Integer, primary_key=True)
    store_code = db.Column(db.String(20), nullable=False)
    total_amount = db.Column(db.Float, nullable=False, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    final_amount = db.Column(db.Float, nullable=False, default=0.0)
    payment_method = db.Column(db.String(20), default='现金')
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    cashier_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship('SaleItem', backref='sale', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'store_code': self.store_code,
            'total_amount': self.total_amount,
            'discount_amount': self.discount_amount,
            'final_amount': self.final_amount,
            'payment_method': self.payment_method,
            'member_id': self.member_id,
            'cashier_id': self.cashier_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'items': [item.to_dict() for item in self.items.all()],
        }


class SaleItem(db.Model):
    """销售明细"""
    __tablename__ = 'sale_items'

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    product = db.relationship('Product')

    def to_dict(self):
        return {
            'id': self.id,
            'sale_id': self.sale_id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'subtotal': self.subtotal,
        }


class InventoryTransaction(db.Model):
    """库存变动记录（入库、出库、调拨、生产消耗）"""
    __tablename__ = 'inventory_transactions'

    id = db.Column(db.Integer, primary_key=True)
    transaction_type = db.Column(db.String(20), nullable=False)
    # 'purchase' 采购入库, 'production_in' 生产入库, 'production_consume' 生产消耗
    # 'transfer_out' 调拨出库, 'transfer_in' 调拨入库, 'sale' 销售出库, 'waste' 报损
    item_type = db.Column(db.String(20), nullable=False)  # 'product' 或 'material'
    item_id = db.Column(db.Integer, nullable=False)
    store_code = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    unit_price = db.Column(db.Float, nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)  # 关联单据ID
    note = db.Column(db.String(200), nullable=True)
    operator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'transaction_type': self.transaction_type,
            'item_type': self.item_type,
            'item_id': self.item_id,
            'store_code': self.store_code,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'reference_id': self.reference_id,
            'note': self.note,
            'operator_id': self.operator_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class TransferOrder(db.Model):
    """调拨单"""
    __tablename__ = 'transfer_orders'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    from_store = db.Column(db.String(20), nullable=False)
    to_store = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    # 'pending' 待审批, 'approved' 已审批, 'picked' 已取货, 'delivered' 已送达, 'cancelled' 已取消
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    driver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    note = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    product = db.relationship('Product')

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'quantity': self.quantity,
            'from_store': self.from_store,
            'to_store': self.to_store,
            'status': self.status,
            'requester_id': self.requester_id,
            'approver_id': self.approver_id,
            'driver_id': self.driver_id,
            'note': self.note,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


# ============================================================
# 会员模型
# ============================================================

class Member(db.Model):
    """会员"""
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(64), nullable=True)
    level = db.Column(db.String(20), default='普通')
    points = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Float, default=0.0)
    birthday = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_visit_at = db.Column(db.DateTime, nullable=True)

    sales = db.relationship('Sale', backref='member', lazy='dynamic')
    points_logs = db.relationship('PointsLog', backref='member', lazy='dynamic')

    def calculate_level(self):
        """根据积分重新计算会员等级"""
        from src.config import Config
        levels = Config.MEMBER_LEVELS
        current_level = '普通'
        for level_name, level_info in sorted(levels.items(),
                                              key=lambda x: x[1]['min_points'],
                                              reverse=True):
            if self.points >= level_info['min_points']:
                current_level = level_name
                break
        self.level = current_level
        return current_level

    def to_dict(self):
        return {
            'id': self.id,
            'phone': self.phone,
            'name': self.name,
            'level': self.level,
            'points': self.points,
            'total_spent': self.total_spent,
            'birthday': self.birthday.isoformat() if self.birthday else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_visit_at': self.last_visit_at.isoformat() if self.last_visit_at else None,
        }


class PointsLog(db.Model):
    """积分变动记录"""
    __tablename__ = 'points_logs'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    points_change = db.Column(db.Integer, nullable=False)  # 正数为增加，负数为消耗
    reason = db.Column(db.String(100), nullable=False)  # 'purchase', 'exchange', 'adjust'
    reference_id = db.Column(db.Integer, nullable=True)  # 关联销售单ID
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'points_change': self.points_change,
            'reason': self.reason,
            'reference_id': self.reference_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ============================================================
# 营销工具模型
# ============================================================

class Coupon(db.Model):
    """优惠券"""
    __tablename__ = 'coupons'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    coupon_type = db.Column(db.String(20), nullable=False)
    # 'discount' 折扣券, 'cash' 满减券
    condition_amount = db.Column(db.Float, nullable=True)  # 满多少元可用
    value = db.Column(db.Float, nullable=False)  # 折扣率(0.9)或减免金额(15)
    is_active = db.Column(db.Boolean, default=True)
    start_date = db.Column(db.DateTime, nullable=True)
    end_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'coupon_type': self.coupon_type,
            'condition_amount': self.condition_amount,
            'value': self.value,
            'is_active': self.is_active,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
        }


class MemberCoupon(db.Model):
    """会员领取的优惠券"""
    __tablename__ = 'member_coupons'

    id = db.Column(db.Integer, primary_key=True)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=False)
    coupon_id = db.Column(db.Integer, db.ForeignKey('coupons.id'), nullable=False)
    is_used = db.Column(db.Boolean, default=False)
    used_at = db.Column(db.DateTime, nullable=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sales.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    coupon = db.relationship('Coupon')

    def to_dict(self):
        return {
            'id': self.id,
            'member_id': self.member_id,
            'coupon_id': self.coupon_id,
            'coupon_name': self.coupon.name if self.coupon else '',
            'is_used': self.is_used,
            'used_at': self.used_at.isoformat() if self.used_at else None,
            'sale_id': self.sale_id,
        }


# ============================================================
# 生产建议模型
# ============================================================

class ProductionSuggestion(db.Model):
    """生产建议"""
    __tablename__ = 'production_suggestions'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    suggested_date = db.Column(db.Date, nullable=False)
    suggested_quantity = db.Column(db.Float, nullable=False)
    actual_quantity = db.Column(db.Float, nullable=True)  # 师傅实际调整后的数量
    reason = db.Column(db.String(200), nullable=True)  # 建议依据
    is_adjusted = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    product = db.relationship('Product')

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else '',
            'suggested_date': self.suggested_date.isoformat() if self.suggested_date else None,
            'suggested_quantity': self.suggested_quantity,
            'actual_quantity': self.actual_quantity,
            'reason': self.reason,
            'is_adjusted': self.is_adjusted,
        }
