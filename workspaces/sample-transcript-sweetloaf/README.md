# SweetLoaf 烘焙坊运营管理平台

## 项目概述

SweetLoaf 烘焙坊运营管理平台，专为台南 SweetLoaf 中型烘焙坊（3家门店、12名员工）量身定制。

基于真实客户访谈（2026-05-15）开发的智能管理系统，解决以下核心痛点：

- **高损耗**：库存管理靠人脑，成品损耗率高达15%-20%
- **低效率**：订单靠手写、排班靠Excel、沟通靠Line群组
- **弱客户关系**：无会员体系，无法复购营销

## 功能模块

| 模块 | 功能 | 优先级 |
|:---|:---|:---:|
| 📦 智能库存管理 | 多门店实时库存看板、入库/出库/报废记录、库存预警与补货建议 | Must-have |
| 📋 订单管理 | 多渠道订单统一管理、订单日历视图、状态跟踪 | Must-have |
| 👥 员工排班 | 可视化排班表、调班/请假申请与审批 | Must-have |
| 📊 数据看板 | 核心经营指标（销售额、Top产品、损耗率、库存预警） | Must-have |
| 🎯 会员管理 | 手机号注册、消费积分、标签画像 | Should-have |
| 📱 移动端支持 | 员工/店主可通过手机查看数据和处理审批 | Should-have |

## 技术栈

- **后端框架**：Flask 2.3
- **数据库**：SQLAlchemy 2.0 + SQLite（开发环境）
- **API风格**：RESTful JSON API

## 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd sample-transcript-sweetloaf

# 2. 安装依赖
pip install -r src/requirements.txt

# 3. 启动服务
python src/app.py
```

### 访问服务

服务启动后，访问 http://localhost:5000

## API 接口

### 基础路径：`http://localhost:5000`

| 方法 | 路径 | 说明 |
|:---|:---|:---|
| GET | `/` | API首页/状态检查 |
| GET | `/api/stores` | 获取所有门店 |
| POST | `/api/stores` | 创建门店 |
| GET | `/api/employees` | 获取员工列表（支持?store_id=筛选） |
| POST | `/api/employees` | 创建员工 |
| GET | `/api/products` | 获取产品列表（支持?category=筛选） |
| POST | `/api/products` | 创建产品 |
| GET | `/api/ingredients` | 获取原料列表 |
| POST | `/api/ingredients` | 创建原料 |
| GET | `/api/inventory` | 获取库存看板（支持?store_id=&type=筛选） |
| POST | `/api/inventory/transactions` | 创建库存变动（入库/出库/报废） |
| GET | `/api/inventory/alerts` | 获取库存预警 |
| GET | `/api/orders` | 获取订单列表 |
| POST | `/api/orders` | 创建订单 |
| GET | `/api/orders/calendar` | 获取订单日历视图 |
| GET | `/api/schedules` | 获取排班表 |
| POST | `/api/schedules` | 创建排班 |
| GET | `/api/shift-requests` | 获取调班/请假申请 |
| POST | `/api/shift-requests` | 提交调班/请假申请 |
| GET | `/api/members` | 获取会员列表 |
| POST | `/api/members` | 注册会员 |
| GET | `/api/sales` | 获取销售记录 |
| POST | `/api/sales` | 创建销售记录 |
| GET | `/api/production` | 获取生产记录 |
| POST | `/api/production` | 创建生产记录 |
| GET | `/api/dashboard` | 获取核心经营数据仪表盘 |

## 项目结构

```
sample-transcript-sweetloaf/
├── docs/
│   └── PRD.md              # 产品需求文档
├── src/
│   ├── app.py              # Flask主入口 + 所有API路由
│   ├── models.py           # 数据库模型
│   ├── config.py           # 配置管理
│   └── requirements.txt    # Python依赖
├── README.md               # 本文件
└── sweetloaf.db            # SQLite数据库（运行后自动生成）
```

## 开发说明

### 数据库

开发环境默认使用SQLite，数据库文件自动生成在项目根目录的 `sweetloaf.db`。

首次启动时自动创建所有表并初始化种子数据（3家门店、12名员工、10种产品、10种原料、示例订单和排班）。

### 配置

通过环境变量配置：

```bash
export FLASK_ENV=development   # 开发模式（默认）
export FLASK_ENV=production    # 生产模式
export SECRET_KEY=your-secret  # 自定义密钥
export DATABASE_URL=sqlite:///path/to/db  # 自定义数据库
```

## 许可证

MIT License
