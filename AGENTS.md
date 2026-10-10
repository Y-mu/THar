# THar 项目记忆

## 产品目标

THar 是意图优先的 LLM 对话编排器。用户请求必须先经过可信的意图分类和安全策略，才能运行对应 Agent。

## 稳定约束

- 不允许绕过意图路由直接调用 LLM Agent。
- 分类不可用、未知意图或低置信度必须故障关闭，只能进入澄清流程。
- Agent 工具按意图最小授权，通用对话 Agent 不注册业务工具。
- 服务调用必须显式传入非空 `session_id`。
- 会话历史只持久化用户消息和最终助手消息，不持久化跨 Agent 的内部工具记录。
- 外部 I/O 端口优先使用 async；流式协议保留 token、工具事件和最终回答。
- 意图和 criteria 以 `INTENT_CATALOG` 为单一配置源；Prompt 资产由 `capabilities/prompts` 管理；工具注册、意图工具映射和身份权限由 `capabilities/tools` 管理。
- Bootstrap 必须在启动时校验意图、Prompt、工具和权限配置的完整性，配置不一致时拒绝启动。
- 测试不得调用真实模型或产生 API 费用。

## 当前架构

- `langHar/api`：FastAPI 接入层，当前按 `auth`、`chat`、`conversation` 和 `health` 模块组织。
- `langHar/agents`：当前的 Agent 编排、意图识别和 LangChain 适配代码。
- `langHar/tools`：当前的本地工具实现和注册表。
- `langHar/config.py`：当前的环境配置入口。

当前代码处于向最终目标架构演进的阶段。当前目录是实现选择，不是不可改变的产品约束。重构时优先维持稳定约束、清晰职责和单向依赖，不为保留目录形式制造空抽象。

## 长期最终目标架构

以下结构是 THar 的最终项目目标，用于约束新功能的职责归属和演进方向。它不代表当前阶段必须一次性创建全部目录和抽象。

```text
langHar/
├── api/                          # 接入层
│   ├── app.py                    # FastAPI 实例与 lifespan
│   ├── deps.py                   # 全局依赖注入
│   └── routes/
│       ├── auth.py               # 登录、身份和 Cookie 接口
│       ├── chat.py               # 对话接口
│       ├── session.py            # 对话会话管理
│       └── health.py             # 健康检查
│
├── orchestration/                # 编排层，唯一流程所有者
│   ├── agent_service.py          # Agent 调用用例和总流程
│   ├── intent_router.py          # 意图结果校验、故障关闭与路由
│   ├── agent_executor.py         # Agent 执行端口
│   ├── workflow_engine.py        # 多步骤工作流
│   └── session_manager.py        # Agent 对话状态读写
│
├── capabilities/                 # Agent 可使用的能力与资产
│   ├── prompts/
│   │   ├── registry.py           # Prompt 注册表与 LangSmith Hub 加载
│   │   └── templates/            # 本地兜底模板
│   ├── skills/
│   │   ├── loader.py             # 按需加载 SKILL.md
│   │   └── defs/                 # Skill 定义
│   ├── tools/
│   │   ├── registry.py           # 工具注册表
│   │   ├── catalog.py            # 意图工具映射和身份权限
│   │   ├── policy.py             # 最小授权决策
│   │   └── builtin/              # 内置工具
│   └── mcp/
│       ├── client.py             # MCP 协议客户端
│       └── servers.yaml          # MCP Server 配置
│
├── infrastructure/               # 外部系统和技术适配层
│   ├── llm/
│   │   ├── gateway.py            # LLM 统一网关、路由、重试与降级
│   │   └── providers/            # OpenAI、Anthropic 和本地模型
│   ├── intent_recognition/       # 外部意图识别实现
│   ├── memory/
│   │   ├── short_term.py         # Redis 短期记忆
│   │   └── long_term.py          # 向量库长期记忆
│   ├── storage/
│   │   ├── db.py                 # 数据库连接
│   │   └── repositories/         # 数据访问实现
│   ├── cache/                    # 缓存适配器
│   └── observability/
│       ├── tracing.py            # LangSmith 与 OpenTelemetry
│       └── metrics.py            # Prometheus 指标
│
├── schemas/                      # 跨模块请求、响应和内部 DTO
├── config/                       # Settings 与环境配置
├── bootstrap.py                  # 唯一 composition root
└── main.py                       # 程序入口
```

### 最终边界

- API 只负责 HTTP/Cookie/SSE 的输入输出、身份提取和参数校验，不执行意图决策、工具授权或 Agent 业务流程。
- Orchestration 是唯一流程所有者，负责意图路由、安全策略、Agent 执行和多步骤工作流，但不直接依赖具体供应商 SDK。
- `intent_recognition` 只负责返回意图分类结果、置信度和模型信息；未知意图、低置信度和失败关闭由 Orchestration 决定。
- Capabilities 管理 Prompt、Skill、Tool 和 MCP 能力资产；工具权限必须在 `capabilities/tools` 中定义，不得回流到意图识别模块。
- Infrastructure 封装模型、数据库、缓存、记忆和可观测性等外部 I/O，通过端口被编排层调用。
- `schemas` 只保存跨模块 DTO；单个 API 专用的 Schema 优先和对应路由放在一起。
- Web 登录会话与 Agent 对话会话是两个独立概念：前者管理登录身份和 Cookie，后者管理对话历史和 Agent Context。

### 演进原则

- 最终目标结构是职责归属约束，不是要求立即创建所有目录。
- 只在出现真实用例时增加 `workflow_engine`、Skills、MCP、Redis、向量库、多模型网关和可观测性实现。
- 迁移采用小步、可测试、可独立验证的方式，每次只移动一类职责。
- 不得为了匹配最终目录树而创建空包、空 Service 或一行转发 Adapter。

## 依赖规则

- API 可依赖 Orchestration 的公开用例和 Schemas，不得直接依赖 Infrastructure 中的具体供应商实现。
- Orchestration 可依赖框架无关的端口、Schemas 和 Capabilities 策略，不得导入 LangChain、LangGraph 或供应商 SDK 类型。
- Capabilities 不得反向控制 Orchestration；工具和 MCP 运行时通过显式端口使用。
- Infrastructure 实现端口，但不能控制 Orchestration。
- Bootstrap/composition root 是唯一允许同时引用 Orchestration、Capabilities 和 Infrastructure 具体实现的地方。

最终由 `tests/test_architecture.py` 自动检查这些边界；在该测试落地前，修改时仍必须人工遵守。

## 修改策略

- 不为旧路径或旧接口保留兼容层；需求变化时整体修改实现、测试和文档。
- 不新增只有一行转发逻辑的 Service、Repository 或 Adapter。
- 新增意图优先修改 `INTENT_CATALOG`，再补充对应 Prompt 和 Tool Policy；编排流程不应出现按意图硬编码的分支。
- 新增模型、分类器或存储供应商时，实现现有端口并在 Bootstrap 替换组装。
- 不把 LangChain、LangGraph 或供应商 SDK 类型泄漏到 Orchestration 公开端口和跨模块 Schemas。

## 验证

```bash
python -m unittest discover -v
python -m compileall -q langHar tests
```

提交前同步 README、`.env.example`、测试和实现。
