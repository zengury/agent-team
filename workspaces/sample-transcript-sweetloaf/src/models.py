"""
数据库模型 - SweetLoaf 烘焙坊运营管理平台

基于PRD需求，包含以下核心模型：
1. Store - 门店管理
2. Employee - 员工管理
3. Product - 产品管理（成品）
4. Ingredient - 原料管理
5. Inventory - 库存记录
6. Order - 订单管理
7. Schedule - 排班管理
8. Member - 会员管理
9. SaleRecord - 销售记录
"""
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, date, time

db = SQLAlchemy()


# ============================================================
# 门店管理
# ============================================================
class Store(db.Model):
    """门店模型 - 对应SweetLoaf的三家门店"""
    __tablename__ = 'stores'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='门店名称')
    location = db.Column(db.String(200), nullable=False, comment='门店地址/区域')
    phone = db.Column(db.String(20), comment='门店电话')
    is_active = db.Column(db.Boolean, default=True, comment='是否营业')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联
    employees = db.relationship('Employee', backref='store', lazy='dynamic')
    inventories = db.relationship('Inventory', backref='store', lazy='dynamic')
    orders = db.relationship('Order', backref='store', lazy='dynamic')
    schedules = db.relationship('Schedule', backref='store', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'phone': self.phone,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================================
# 员工管理
# ============================================================
class Employee(db.Model):
    """员工模型 - 12名员工信息"""
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False, comment='员工姓名')
    phone = db.Column(db.String(20), comment='联系电话')
    role = db.Column(db.String(50), nullable=False, comment='岗位：烘焙师/店员/店长')
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False, comment='所属门店')
    is_active = db.Column(db.Boolean, default=True, comment='在职状态')
    hire_date = db.Column(db.Date, default=date.today, comment='入职日期')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联
    schedules = db.relationship('Schedule', backref='employee', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'phone': self.phone,
            'role': self.role,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'is_active': self.is_active,
            'hire_date': self.hire_date.isoformat() if self.hire_date else None
        }


# ============================================================
# 产品管理（成品）
# ============================================================
class Product(db.Model):
    """产品模型 - 面包、蛋糕、饼干等成品"""
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='产品名称')
    category = db.Column(db.String(50), nullable=False, comment='分类：面包/蛋糕/饼干')
    price = db.Column(db.Float, nullable=False, default=0.0, comment='售价')
    cost = db.Column(db.Float, default=0.0, comment='成本')
    is_signature = db.Column(db.Boolean, default=False, comment='是否招牌产品')
    is_limited = db.Column(db.Boolean, default=False, comment='是否限量供应')
    description = db.Column(db.Text, comment='产品描述')
    image_url = db.Column(db.String(200), comment='产品图片URL')
    is_active = db.Column(db.Boolean, default=True, comment='是否在售')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联
    inventories = db.relationship('Inventory', backref='product', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'price': self.price,
            'cost': self.cost,
            'is_signature': self.is_signature,
            'is_limited': self.is_limited,
            'description': self.description,
            'is_active': self.is_active
        }


# ============================================================
# 原料管理
# ============================================================
class Ingredient(db.Model):
    """原料模型 - 面粉、黄油、奶油芝士等"""
    __tablename__ = 'ingredients'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, comment='原料名称')
    unit = db.Column(db.String(20), nullable=False, default='kg', comment='单位：kg/g/L/个')
    unit_price = db.Column(db.Float, default=0.0, comment='单价')
    safety_stock = db.Column(db.Float, default=0.0, comment='安全库存量')
    supplier = db.Column(db.String(100), comment='常用供应商')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关联
    inventories = db.relationship('Inventory', backref='ingredient', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'unit': self.unit,
            'unit_price': self.unit_price,
            'safety_stock': self.safety_stock,
            'supplier': self.supplier,
            'is_active': self.is_active
        }


# ============================================================
# 库存记录
# ============================================================
class Inventory(db.Model):
    """库存模型 - 记录每家店的原料和成品库存"""
    __tablename__ = 'inventories'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True, comment='成品ID')
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=True, comment='原料ID')
    quantity = db.Column(db.Float, nullable=False, default=0.0, comment='当前库存数量')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        result = {
            'id': self.id,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'quantity': self.quantity,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        if self.product:
            result['product_id'] = self.product.id
            result['product_name'] = self.product.name
            result['item_type'] = 'product'
        if self.ingredient:
            result['ingredient_id'] = self.ingredient.id
            result['ingredient_name'] = self.ingredient.name
            result['item_type'] = 'ingredient'
        return result


# ============================================================
# 库存变动记录（入库/出库/报废）
# ============================================================
class InventoryTransaction(db.Model):
    """库存变动记录 - 入库、出库、报废等操作"""
    __tablename__ = 'inventory_transactions'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=True)
    ingredient_id = db.Column(db.Integer, db.ForeignKey('ingredients.id'), nullable=True)
    transaction_type = db.Column(db.String(20), nullable=False, comment='类型：in/out/waste')
    quantity = db.Column(db.Float, nullable=False, comment='变动数量')
    reason = db.Column(db.String(200), comment='原因说明（如：报废原因）')
    operator = db.Column(db.String(50), comment='操作人')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    store = db.relationship('Store', backref='inventory_transactions')
    product = db.relationship('Product', backref='inventory_transactions')
    ingredient = db.relationship('Ingredient', backref='inventory_transactions')

    def to_dict(self):
        result = {
            'id': self.id,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'transaction_type': self.transaction_type,
            'quantity': self.quantity,
            'reason': self.reason,
            'operator': self.operator,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
        if self.product:
            result['product_id'] = self.product.id
            result['product_name'] = self.product.name
            result['item_type'] = 'product'
        if self.ingredient:
            result['ingredient_id'] = self.ingredient.id
            result['ingredient_name'] = self.ingredient.name
            result['item_type'] = 'ingredient'
        return result


# ============================================================
# 订单管理
# ============================================================
class Order(db.Model):
    """订单模型 - 预订订单（生日蛋糕、团购等）"""
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_no = db.Column(db.String(50), unique=True, nullable=False, comment='订单编号')
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False, comment='取货门店')
    customer_name = db.Column(db.String(100), nullable=False, comment='客户姓名')
    customer_phone = db.Column(db.String(20), comment='客户电话')
    channel = db.Column(db.String(20), default='phone', comment='订单渠道：phone/line/store')
    status = db.Column(
        db.String(20), default='pending',
        comment='状态：pending/confirmed/production/completed/cancelled'
    )
    total_amount = db.Column(db.Float, default=0.0, comment='订单总金额')
    pickup_date = db.Column(db.Date, nullable=False, comment='取货日期')
    pickup_time = db.Column(db.String(20), comment='取货时间段')
    notes = db.Column(db.Text, comment='备注')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    items = db.relationship('OrderItem', backref='order', lazy='dynamic',
                            cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'order_no': self.order_no,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'channel': self.channel,
            'status': self.status,
            'total_amount': self.total_amount,
            'pickup_date': self.pickup_date.isoformat() if self.pickup_date else None,
            'pickup_time': self.pickup_time,
            'notes': self.notes,
            'items': [item.to_dict() for item in self.items.all()],
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class OrderItem(db.Model):
    """订单明细"""
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, default=0.0)
    subtotal = db.Column(db.Float, default=0.0)

    def to_dict(self):
        return {
            'id': self.id,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'subtotal': self.subtotal
        }


# ============================================================
# 员工排班
# ============================================================
class Schedule(db.Model):
    """排班模型"""
    __tablename__ = 'schedules'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    work_date = db.Column(db.Date, nullable=False, comment='工作日期')
    start_time = db.Column(db.String(10), nullable=False, comment='上班时间，如 08:00')
    end_time = db.Column(db.String(10), nullable=False, comment='下班时间，如 17:00')
    status = db.Column(db.String(20), default='scheduled',
                       comment='状态：scheduled/confirmed/completed/absent')
    notes = db.Column(db.String(200), comment='备注（如调班说明）')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.name if self.employee else None,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'work_date': self.work_date.isoformat() if self.work_date else None,
            'start_time': self.start_time,
            'end_time': self.end_time,
            'status': self.status,
            'notes': self.notes
        }


# ============================================================
# 调班/请假申请
# ============================================================
class ShiftRequest(db.Model):
    """调班/请假申请"""
    __tablename__ = 'shift_requests'

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    request_type = db.Column(db.String(20), nullable=False, comment='类型：swap/leave')
    target_date = db.Column(db.Date, nullable=False, comment='目标日期')
    reason = db.Column(db.String(200), comment='原因')
    swap_with_employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True,
                                      comment='调班对象')
    status = db.Column(db.String(20), default='pending',
                       comment='状态：pending/approved/rejected')
    approved_by = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True,
                            comment='审批人')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    employee = db.relationship('Employee', foreign_keys=[employee_id],
                               backref='shift_requests')
    swap_with = db.relationship('Employee', foreign_keys=[swap_with_employee_id])
    approver = db.relationship('Employee', foreign_keys=[approved_by])

    def to_dict(self):
        return {
            'id': self.id,
            'employee_id': self.employee_id,
            'employee_name': self.employee.name if self.employee else None,
            'request_type': self.request_type,
            'target_date': self.target_date.isoformat() if self.target_date else None,
            'reason': self.reason,
            'swap_with_employee_id': self.swap_with_employee_id,
            'swap_with_name': self.swap_with.name if self.swap_with else None,
            'status': self.status,
            'approved_by': self.approved_by
        }


# ============================================================
# 会员管理
# ============================================================
class Member(db.Model):
    """会员模型"""
    __tablename__ = 'members'

    id = db.Column(db.Integer, primary_key=True)
    phone = db.Column(db.String(20), unique=True, nullable=False, comment='手机号（唯一标识）')
    name = db.Column(db.String(50), comment='会员姓名')
    gender = db.Column(db.String(10), comment='性别')
    birthday = db.Column(db.Date, comment='生日')
    total_spent = db.Column(db.Float, default=0.0, comment='累计消费金额')
    points = db.Column(db.Integer, default=0, comment='积分')
    level = db.Column(db.String(20), default='regular', comment='等级：regular/silver/gold')
    tags = db.Column(db.String(200), comment='标签，逗号分隔')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 关联
    sale_records = db.relationship('SaleRecord', backref='member', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id,
            'phone': self.phone,
            'name': self.name,
            'gender': self.gender,
            'birthday': self.birthday.isoformat() if self.birthday else None,
            'total_spent': self.total_spent,
            'points': self.points,
            'level': self.level,
            'tags': self.tags.split(',') if self.tags else [],
            'is_active': self.is_active
        }


# ============================================================
# 销售记录
# ============================================================
class SaleRecord(db.Model):
    """销售记录 - 每日销售数据"""
    __tablename__ = 'sale_records'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    member_id = db.Column(db.Integer, db.ForeignKey('members.id'), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    sale_date = db.Column(db.Date, nullable=False, default=date.today)
    sale_time = db.Column(db.String(10), comment='销售时间 HH:MM')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    store = db.relationship('Store', backref='sale_records')
    product = db.relationship('Product', backref='sale_records')

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'member_id': self.member_id,
            'member_name': self.member.name if self.member else None,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total_amount': self.total_amount,
            'sale_date': self.sale_date.isoformat() if self.sale_date else None,
            'sale_time': self.sale_time
        }


# ============================================================
# 生产记录
# ============================================================
class ProductionRecord(db.Model):
    """生产记录 - 每日生产情况"""
    __tablename__ = 'production_records'

    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.Integer, db.ForeignKey('stores.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    planned_quantity = db.Column(db.Integer, default=0, comment='计划生产数量')
    actual_quantity = db.Column(db.Integer, default=0, comment='实际生产数量')
    waste_quantity = db.Column(db.Integer, default=0, comment='报废数量')
    waste_reason = db.Column(db.String(100), comment='报废原因')
    production_date = db.Column(db.Date, nullable=False, default=date.today)
    operator = db.Column(db.String(50), comment='操作人')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    store = db.relationship('Store', backref='production_records')
    product = db.relationship('Product', backref='production_records')

    def to_dict(self):
        return {
            'id': self.id,
            'store_id': self.store_id,
            'store_name': self.store.name if self.store else None,
            'product_id': self.product_id,
            'product_name': self.product.name if self.product else None,
            'planned_quantity': self.planned_quantity,
            'actual_quantity': self.actual_quantity,
            'waste_quantity': self.waste_quantity,
            'waste_reason': self.waste_reason,
            'production_date': self.production_date.isoformat() if self.production_date else None,
            'operator': self.operator
        }
