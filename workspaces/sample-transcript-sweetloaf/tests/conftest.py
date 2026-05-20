"""
SweetLoaf 烘焙管理系统 - pytest 配置与测试夹具
"""
import os
import sys
import pytest

# 确保能找到 src 包
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from app import create_app
from models import db as _db


@pytest.fixture(scope='session')
def app():
    """创建测试应用实例，使用内存数据库"""
    app = create_app()
    app.config.update({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
        'SQLALCHEMY_TRACK_MODIFICATIONS': False,
    })
    return app


@pytest.fixture(scope='function')
def client(app):
    """创建测试客户端，每次测试前重建表"""
    with app.app_context():
        _db.create_all()
        yield app.test_client()
        _db.session.remove()
        _db.drop_all()


@pytest.fixture(scope='function')
def db(app):
    """提供数据库会话"""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.remove()
        _db.drop_all()
