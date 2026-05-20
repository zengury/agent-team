# DevLog — 2026-05-20/21

## 构建了西游Agent团队 — 五AI Agent交付系统

### 1. 团队设计

| Agent | 角色 | 模型 | 性格 |
|-------|------|------|------|
| 👑 唐僧 | CEO/协调者 | deepseek-chat | 细致·情绪稳定·执着·永不放弃 |
| 🐷 八戒 | 产品经理 | deepseek-chat | 有品位·想法多·善于沟通 |
| 🐵 悟空 | 核心开发者 | deepseek-chat | 能力最强·火眼金睛·快速执行 |
| 🐟 沙僧 | 测试工程师 | deepseek-chat | 认真·任劳任怨·持续输出 |
| 🐉 白龙马 | 客户成功 | deepseek-chat | 最有服务态度·关心客户 |

### 2. 技术架构

```
src/agent_team/
├── orchestrator.py    — 编排引擎 + 事件系统 + 状态机
├── agents/            — 五个Agent实现 (支持Function Calling)
├── llm/               — DeepSeek/Anthropic/OpenAI 三后端
├── control_plane/     — FastAPI + WebSocket 实时控制面板
├── harness/           — 工程保障层
│   ├── guardrails.py  — 输入/输出/工具调用校验
│   ├── tracing.py     — Span追踪 + JSON导出
│   ├── handoffs.py    — Agent间交接过滤
│   ├── state_machine.py — 可恢复/可重放状态机(16个checkpoint)
│   ├── human_loop.py  — 审核/暂停/恢复
│   └── contract.py    — 需求契约验证(需求→PRD→代码覆盖)
└── tools/
    └── registry.py    — 工具注册表(read_file/write_file/list_dir/run_shell)
```

### 3. 端到端交付验证 — SweetLoaf 面包店

客户: 台南 SweetLoaf 烘焙坊，3家门店，12人
需求: LINE/WhatsApp 订单自动录入，消除手动 Excel 抄单

**工作流**: 唐僧分析 → 八戒PRD → 悟空开发 → 沙僧测试 → 白龙马文档 → 唐僧交付

**产出**:
- 36KB Flask应用，27个API端点 (GET/POST/PUT)
- 11个数据模型 (Store/Product/Order/Inventory/Member...)
- 16个测试用例 (pytest)
- 15KB PRD + 用户指南 + 部署指南 + FAQ
- 需求契约验证: LLM提取6条需求，自动检测PRD/代码覆盖

**耗时**: 9分40秒

### 4. 关键发现

**需求传递衰减问题**:
- 客户反复说"LINE自动接单"，但八戒PRD漏掉了这个核心需求
- 悟空按PRD做，也没有订单录入功能
- 后来加了需求契约验证层(contract.py)，用LLM提取需求→验证PRD覆盖→自动触发修复

**LLM Function Calling稳定性**:
- DeepSeek 的 tool call JSON 有概率格式错误（中文内容/引号转义）
- 加了 regex 修复 + 降级策略

**真实代码 vs 文字方案**:
- v1(无工具): 产出38KB "实现方案描述"
- v3(有工具+契约): 产出可运行的 Flask 应用 + 测试 + 文档

### 5. 待解决

- [ ] LINE Bot 对接（需要外部API，纯代码生成做不到）
- [ ] 测试未实际执行（pytest 跑在了空数据库上）
- [ ] FAQ.md 生成不稳定（随机丢失）
- [ ] app.py 的 `today` 变量未定义 bug（LLM 写代码的典型问题）
- [ ] 控制面板与 CLI 共享状态（目前两个独立进程）

### 6. Git

https://github.com/zengury/agent-team/tree/agent-team
