"""
SweetLoaf 面包店数字化管理系统 - 配置管理
"""
import os

basedir = os.path.abspath(os.path.dirname(__file__))


class Config:
    """应用配置类"""
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'sweetloaf-secret-key-2026'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(os.path.dirname(basedir), 'sweetloaf.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # 门店配置
    STORES = {
        'main': {'name': '总店（中央厨房）', 'address': '台南市东区'},
        'east': {'name': '东区店', 'address': '台南市东区'},
        'central': {'name': '中西区店', 'address': '台南市中西区'},
        'north': {'name': '北区店', 'address': '台南市北区'},
    }

    # 库存预警阈值
    STOCK_ALERT_THRESHOLD = 10

    # 会员积分比例 (消费金额:积分)
    POINTS_RATIO = 10  # 每10元得1积分
    POINTS_EXCHANGE_RATE = 10  # 10积分抵扣1元

    # 会员等级
    MEMBER_LEVELS = {
        '普通': {'min_points': 0, 'discount': 1.0},
        '银卡': {'min_points': 200, 'discount': 0.95},
        '金卡': {'min_points': 500, 'discount': 0.9},
    }

    # 生产建议参数
    PRODUCTION_FORECAST_DAYS = 7
    PRODUCTION_FORECAST_HOUR = 18  # 每天下午6点生成建议

    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}
