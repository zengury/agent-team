# SweetLoaf 面包店数字化管理系统

## 项目概述

SweetLoaf 是一家位于台湾台南的中型烘焙坊，由陈老板经营，拥有12名员工和3家门店。本系统旨在解决其库存管理混乱、多门店数据割裂、会员与营销体系缺失三大核心痛点。

## 核心功能

### Must have (必须有)
1. **多门店实时库存管理** - 原材料入库、生产消耗、门店调拨、销售出库全链路管理
2. **统一销售数据看板** - 实时展示各门店营收、热销/滞销排行榜
3. **基础会员管理** - 手机号注册、消费积分、会员等级

### Should have (应该有)
4. **智能生产建议** - 基于历史销量自动生成次日生产建议
5. **门店间调拨申请** - 调拨申请、审批、执行全流程
6. **简易营销工具** - 优惠券发放、生日祝福

### Could have (可以有)
7. 线上预订与自提
8. 员工排班与考勤
9. 简易财务报表

## 技术栈

- **后端框架**: Flask 2.3.3
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **ORM**: Flask-SQLAlchemy 3.1.1
- **认证**: Werkzeug 密码哈希

## 安装与运行

### 环境要求

- Python 3.8+
- pip

### 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd sample-transcript-sweetloaf

# 2. 安装依赖
pip install -r src/requirements.txt

# 3. 初始化数据库并启动服务
python src/app.py
```

服务启动后，访问 http://localhost:5000 即可。

### 生产环境部署

```bash
# 使用 gunicorn 启动
gunicorn -w 4 -b 0.0.0.0:5000 "src.app:app"
```

## API 接口概览

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | / | 系统状态 |
| GET | /health | 健康检查 |
| GET | /api/products | 产品列表 |
| POST | /api/products | 创建产品 |
| GET | /api/stocks | 库存查询 |
| POST | /api/inventory/purchase | 原材料入库 |
| POST | /api/production | 生产产品 |
| POST | /api/sales | 创建销售 |
| GET | /api/sales | 销售记录查询 |
| GET | /api/dashboard/summary | 销售看板汇总 |
| GET | /api/dashboard/top-products | 热销/滞销排行榜 |
| POST | /api/transfers | 创建调拨申请 |
| POST | /api/transfers/<id>/approve | 审批调拨 |
| POST | /api/transfers/<id>/deliver | 执行调拨 |
| POST | /api/members | 注册会员 |
| GET | /api/members/phone/<phone> | 按手机号查询会员 |
| POST | /api/members/<id>/exchange | 积分兑换 |
| GET | /api/production-suggestions | 生产建议 |
| GET | /api/alerts | 库存预警 |
| GET | /api/members/birthday-today | 今日生日会员 |

## 默认账号

| 用户名 | 密码 | 角色 |
|--------|------|------|
| admin | admin123 | 管理员（陈老板） |
| manager_east | 123456 | 东区店长 |
| baker1 | 123456 | 阿旺师傅 |
| cashier1 | 123456 | 收银员小美 |

## 项目结构

```
sample-transcript-sweetloaf/
├── README.md
├── docs/
│   └── PRD.md              # 产品需求文档
├── src/
│   ├── app.py              # Flask主入口 + 所有路由
│   ├── models.py           # 数据库模型
│   ├── config.py           # 配置管理
│   └── requirements.txt    # 依赖清单
└── sweetloaf.db            # SQLite数据库文件（运行后生成）
```
