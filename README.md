# 🏔️ 西游Agent团队

**Journey to the West — Five-Agent AI Delivery Team**

借鉴 [任川 (clockless.ai)](https://clockless.ai) OPC（一人公司）模式，以西游记角色构建的五智能体团队。

```
        师父（你）←→ SME 客户
              │
              │ 对话记录 / 取经需求
              ▼
      ┌───────────────────┐
      │   👑 唐僧          │  ← GPT-4.5 · 细致·情绪稳定·执着·永不放弃
      │   协调者 · Leader   │
      │   定方向 · 派任务    │
      └──┬──────┬──────┬──┘
         │      │      │
    ┌────▼─┐ ┌─▼───┐ ┌▼────┐  ┌────────┐
    │🐷八戒 │ │🐵悟空│ │🐟沙僧│  │🐉白龙马 │
    │ 产品  │ │ 开发 │ │ 测试 │  │客户成功 │
    │Sonnet │ │4.7  │ │Sonnet│  │ GPT-4.5 │
    └──────┘ └─────┘ └─────┘  └────────┘
```

## 取经队伍

| 角色 | 法号 | 模型 | 职责 |
|------|------|------|------|
| 👑 Leader | **唐僧** | GPT-4.5 | 定方向、派任务、审成果。细致、执着、永不放弃 |
| 🐷 产品 | **八戒** | Claude Sonnet | 出主意、写PRD。有品位、想法多、善沟通 |
| 🐵 开发 | **悟空** | GPT-4.7 | 核心战斗力。火眼金睛、快速执行、活儿都是他干 |
| 🐟 测试 | **沙僧** | Claude Sonnet | 任劳任怨、持续输出、不挑活儿 |
| 🐉 客服 | **白龙马** | GPT-4.5 | 最有服务态度、关心客户、提供客户价值 |

## 🖥️ Control Plane 实时控制面板

**这是最核心的功能！** 可视化看到五个 Agent 的实时运行情况：

```bash
agent-team control-plane
# 打开 → http://localhost:8765
```

### 面板功能：
- 🎨 **Agent 关系图** — Canvas 实时渲染五节点 + 委派关系动画
- 📡 **实时事件流** — WebSocket 推送每个 Agent 的工作状态
- 📄 **产出内容查看** — 按 Agent 筛选查看 PRD/代码/测试/文档
- ⚡ **并行任务可视化** — 动效显示哪些 Agent 正在并行工作
- 🏔️ **西游主题** — 金色/暗色中国风，适合给客户展示

## 快速开始

```bash
# 1. 设置 API Key
export ANTHROPIC_API_KEY="sk-ant-..."
export OPENAI_API_KEY="sk-..."

# 2. 初始化项目
agent-team init acme-bakery

# 3. 提交客户对话
agent-team analyze recordings/call.txt

# 4. 与唐僧讨论
agent-team chat

# 5. 启动取经工作流
agent-team workflow qujing

# 6. 启动控制面板查看实时状态
agent-team control-plane
```

## 三种取经路线

| 命令 | 说明 |
|------|------|
| `qujing` (完整取经) | 八戒PRD → 悟空开发 → 沙僧测试 → 白龙马文档 → 唐僧交付 |
| `tanlu` (快速探路) | 精简PRD → 快速开发 → 冒烟测试 → 交付 |
| `xiance` (军师献策) | 只出方案不写代码，唐僧+八戒+白龙马出谋划策 |

## 唐僧的委派格式

唐僧使用 `@法号:` 语法委派任务，系统自动解析并执行：

```
@bajie: 根据面包店的需求，写一份订单Agent的PRD
@wukong: 用FastAPI搭建订单管理后端
@shaseng: 测试订单API的所有端点和边界情况
@bailongma: 写一份给面包店老板的用户使用手册
```

## 项目结构

```
agent-team/
├── config/
│   ├── agents.yaml         # Agent角色配置（可自定义模型和System Prompt）
│   └── workflows.yaml      # 工作流定义
├── src/agent_team/
│   ├── orchestrator.py     # 取经编排引擎（带实时事件系统）
│   ├── agents/             # 五个Agent实现
│   ├── llm/                # LLM后端（Anthropic + OpenAI）
│   ├── control_plane/      # 控制面板服务器 + Dashboard HTML
│   └── main.py             # CLI入口
├── workspaces/             # 每个客户一个目录
└── skills/                 # 示例对话记录
```
