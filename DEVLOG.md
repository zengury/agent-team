# DevLog — deepseek-chat vs deepseek-v4-pro 对比 + 两次执行差异

## 一、模型对比

| | deepseek-chat (V3) | deepseek-v4-pro |
|---|---|---|
| 类型 | 标准对话模型 | 推理模型(chain-of-thought) |
| 速度 | 每个请求 2-10s | 每个请求 20-60s |
| 输出 | 直接回答 | 先 internal reasoning → 再回答 |
| API 格式 | 标准 chat completions | 额外 `reasoning_content` 字段 |
| 工具调用 | 稳定 | 需回传 reasoning_content |
| 取经耗时 | **9分钟** | 卡死在定方向(估计 30min+) |
| 适用场景 | 多轮工具调用 | 单轮深度分析 |

**结论**: 工具调用循环场景用 chat，深度分析场景用 v4-pro。系统已兼容两者，只需改 `config/agents.yaml` 一行。

## 二、两次完整取经对比

| 维度 | 第一次 (老key) `631e1ff` | 第二次 (pi的key) `a1ab921` |
|---|---|---|
| **commit** | 631e1ff | a1ab921 |
| **API key** | `sk-` (已过期) | `sk-39f669...` (pi的key) |
| **app.py** | 36KB | **42KB (+17%)** |
| **models.py** | 26KB | 18KB |
| **test_app.py** | ✅ 11KB | ❌ 缺失 |
| **conftest.py** | ✅ 5.4KB | ✅ 3.7KB |
| **PRD.md** | ✅ 14KB | ✅ 13KB |
| **用户指南** | ✅ 13KB | ✅ 14KB |
| **部署指南** | ✅ 11KB | ✅ 15KB |
| **FAQ.md** | ✅ 13KB | ✅ **16KB** |
| **README.md** | ✅ 4KB | ✅ 3.3KB |
| **IMPLEMENTATION.md** | ✅ 507B | ✅ 527B |
| **POST 端点** | 10 | **15 (+50%)** |
| **总文件数** | 15 | 13 |

### 核心差异

```
v3 (老key):    代码更强 (26KB models, test_app.py 存在)
v3+ (pi的key): 文档更全 (FAQ 16KB, 部署指南 15KB, POST 多50%)
```

**随机性**: test_app.py 在两次运行中一次有、一次无——LLM 的非确定性。需要后续加后验证层（文件完整性检查）。

## 三、契约验证现状

两次运行契约覆盖率都显示 0%——不是没覆盖，是关键词匹配太严。

实际覆盖情况:
- R001-R004 (订单录入): PRD 提到了"新建订单"，但没提"LINE自动抓取"
- R005 (厨房看板): PRD 有所涉及
- R006 (漏单提醒): 未覆盖
- R007 (LINE API集成): PRD 提到但代码无实际集成

**契约验证的提取层准确（LLM提取了7条真实需求），比对层需要改进。**

## 四、推理模型适配记录

为支持 deepseek-v4-pro 做了以下改动:
1. LLMResponse 增加 `reasoning_content` 字段
2. DeepSeek provider: 用 `getattr` 安全获取 reasoning_content
3. BaseAgent: 工具调用消息中回传 reasoning_content
4. max_tokens 提升到 16K

问题: v4-pro 的工具调用需要将 reasoning_content 原样回传，否则 400 错误。已修复。

## 五、基础设施

- **HTTPS push 被墙** → 改用 SSH: `git push git@github.com:zengury/agent-team.git`
- **仓库**: github.com/zengury/agent-team (agent-team 分支)
- **镜像**: github.com/zengury/teamup (agent-team 分支)
- **Control Plane**: http://localhost:8866
- **SweetLoaf 演示**: http://localhost:5099/dashboard
