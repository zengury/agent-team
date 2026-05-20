"""
SweetLoaf 面包店数字化管理系统 - pytest配置
"""
import os
import sys
import pytest

# 确保能正确导入src包
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.app import create_app
from src.models import db as _db
from src.config import Config


class TestConfig(Config):
    """测试配置 - 使用内存数据库"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = 'test-secret-key'
    # 简化门店配置用于测试
    STORES = {
        'main': {'name': '总店（中央厨房）', 'address': '台南市东区'},
        'east': {'name': '东区店', 'address': '台南市东区'},
    }


@pytest.fixture(scope='function')
def app():
    """创建测试应用实例"""
    app = create_app('testing')
    app.config.from_object(TestConfig)
    
    with app.app_context():
        _db.create_all()
        yield app
        _db.drop_all()


@pytest.fixture(scope='function')
def client(app):
    """测试客户端"""
    return app.test_client()


@pytest.fixture(scope='function')
def db(app):
    """数据库实例"""
    return _db


@pytest.fixture(scope='function')
def init_products(app, db):
    """初始化测试产品数据"""
    from src.models import Product, Stock
    
    products_data = [
        {'name': '台南红豆包', 'category': '面包', 'price': 45.0, 'cost': 18.0, 'unit': '个'},
        {'name': '北海道牛奶吐司', 'category': '面包', 'price': 120.0, 'cost': 45.0, 'unit': '条'},
        {'name': '法式可颂', 'category': '面包', 'price': 35.0, 'cost': 12.0, 'unit': '个'},
        {'name': '经典巧克力蛋糕', 'category': '蛋糕', 'price': 280.0, 'cost': 95.0, 'unit': '个'},
        {'name': '冰美式咖啡', 'category': '饮品', 'price': 60.0, 'cost': 15.0, 'unit': '杯'},
    ]
    
    created_products = []
    for p_data in products_data:
        product = Product(**p_data)
        db.session.add(product)
        db.session.flush()
        
        # 为所有门店初始化库存
        for store_code in TestConfig.STORES:
            stock = Stock(product_id=product.id, store_code=store_code, quantity=20)
            db.session.add(stock)
        
        created_products.append(product)
    
    db.session.commit()
    return created_products


@pytest.fixture(scope='function')
def init_materials(app, db):
    """初始化测试原材料数据"""
    from src.models import RawMaterial, RawMaterialStock
    
    materials_data = [
        {'name': '高筋面粉', 'unit': '公斤', 'min_stock': 10.0},
        {'name': '低筋面粉', 'unit': '公斤', 'min_stock': 5.0},
        {'name': '无盐黄油', 'unit': '公斤', 'min_stock': 5.0},
        {'name': '细砂糖', 'unit': '公斤', 'min_stock': 10.0},
        {'name': '鲜牛奶', 'unit': '升', 'min_stock': 10.0},
    ]
    
    created_materials = []
    for m_data in materials_data:
        material = RawMaterial(**m_data)
        db.session.add(material)
        db.session.flush()
        
        # 初始化原材料库存
        stock = RawMaterialStock(material_id=material.id, store_code='main', quantity=50.0)
        db.session.add(stock)
        
        created_materials.append(material)
    
    db.session.commit()
    return created_materials


@pytest.fixture(scope='function')
def init_member(app, db):
    """初始化测试会员数据"""
    from src.models import Member
    
    member = Member(
        phone='0912345678',
        name='王小明',
        points=150,
        level='银卡',
        total_spent=3500.0,
    )
    db.session.add(member)
    db.session.commit()
    return member
