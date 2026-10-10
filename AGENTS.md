# THar 项目记忆

## 产品目标

THar 是意图优先的 LLM 对话编排器。用户请求必须先经过可信的意图分类和安全策略，才能运行对应 Agent，并可在受权限约束下使用 RAG 知识库。

## 稳定约束

- 不允许绕过意图路由直接调用 LLM Agent。
- 分类不可用、未知意图或低置信度必须故障关闭，只能进入澄清流程。
- Agent 工具按意图最小授权，通用对话 Agent 不注册业务工具。
- 服务调用必须显式传入非空 `session_id`。
- 会话历史只持久化用户消息和最终助手消息，不持久化跨 Agent 的内部工具记录。
- 外部 I/O 端口优先使用 async；流式协议保留 token、工具事件和最终回答。
- 意图和 criteria 以 `INTENT_CATALOG` 为单一配置源；Prompt 资产由 `capabilities/prompts` 管理；工具注册、意图工具映射和身份权限由 `capabilities/tools` 管理。
- Bootstrap 必须在启动时校验意图、Prompt、工具和权限配置的完整性，配置不一致时拒绝启动。
- RAG 检索必须先通过意图路由和 Tool Policy，API 和 Agent 不得绕过编排层直接访问向量库。
- RAG 的用户、租户、知识库和文档 ACL 必须来自可信 `AgentContext`，不得接受模型作为工具参数传入。
- 知识库意图在无权限、检索不可用或无足够证据时必须故障关闭，不得退化为无依据的模型回答。
- RAG 回答必须保留可追溯引用；检索片段和内部工具记录不写入对话历史。
- API 必须按业务模块组织；每个模块自主拥有 `route.py`、`schemas.py` 和专用传输逻辑，不设全局 API Schemas 目录。
- 测试不得调用真实 LLM、Embedding、Reranker 或产生 API 费用。

## 当前架构

- `langHar/api`：FastAPI 接入层，已按 `auth`、`chat`、`session` 和 `health` 业务模块组织。
- `langHar/core`：当前已有的框架无关 Agent 数据契约。
- `langHar/orchestration`：当前已有的认证、意图路由、Agent、聊天和会话编排。
- `langHar/capabilities`：当前已有的 Prompt 和 Tool 能力资产。
- `langHar/infrastructure`：当前已有的 JEV、LangChain 和模型供应商适配器。
- `langHar/config`：Settings 和环境变量入口。
- `langHar/bootstrap.py`：唯一 composition root。
- `langHar/main.py`：服务端程序入口。

当前代码处于向最终目标架构演进的阶段。当前目录是实现选择，不是不可改变的产品约束。重构时优先维持稳定约束、清晰职责和单向依赖，不为保留目录形式制造空抽象。

## 长期最终目标架构

以下结构是 THar 的最终项目目标，用于约束新功能的职责归属和演进方向。它不代表当前阶段必须一次性创建全部目录和抽象。

```text
langHar/
├── api/                          # 接入层
│   ├── app.py                    # FastAPI 实例与 lifespan
│   ├── deps.py                   # 仅保留容器取值等跨模块依赖
│   ├── auth/
│   │   ├── route.py              # 登录、退出和当前用户接口
│   │   ├── schemas.py            # 认证请求与响应模型
│   │   └── deps.py               # Cookie 解析和当前用户依赖
│   ├── chat/
│   │   ├── route.py              # 对话消息接口
│   │   ├── schemas.py            # 对话请求与流式事件模型
│   │   ├── deps.py               # ChatService 依赖
│   │   └── sse.py                # AgentEvent 到 SSE 的传输映射
│   ├── session/
│   │   ├── route.py              # Agent 对话会话管理
│   │   ├── schemas.py            # 会话和历史消息响应模型
│   │   └── deps.py               # SessionManager 依赖
│   ├── knowledge/
│   │   ├── route.py              # 知识库、文档和索引管理接口
│   │   ├── schemas.py            # 入库、索引和引用的 API 模型
│   │   └── deps.py               # 知识库管理权限依赖
│   └── health/
│       └── route.py              # 存活和就绪检查
│
├── core/                         # 框架无关的跨层契约
│   ├── agent.py                   # AgentContext、AgentEvent 和 ChatMessage
│   └── knowledge.py               # Document、Chunk、Citation 和 Retrieval DTO
│
├── orchestration/                # 编排层，唯一流程所有者
│   ├── agent_service.py          # Agent 调用用例和总流程
│   ├── intent_router.py          # 意图结果校验、故障关闭与路由
│   ├── agent_executor.py         # Agent 执行端口
│   ├── knowledge_ingestion.py    # 文档入库、版本和索引编排
│   ├── retrieval_service.py      # 检索、权限过滤、重排和引用组装
│   ├── retrieval_ports.py        # 文档、Embedding、向量检索端口
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
│   │   └── builtin/
│   │       ├── calculator.py       # 计算工具
│   │       ├── weather.py          # 天气工具
│   │       ├── search.py           # 通用搜索工具
│   │       └── knowledge_search.py # 受权限约束的知识检索工具
│   ├── knowledge/
│   │   ├── catalog.py            # 知识库定义、数据域和可用意图
│   │   └── policy.py             # 切块、Top-K、阈值、引用和证据策略
│   └── mcp/
│       ├── client.py             # MCP 协议客户端
│       └── servers.yaml          # MCP Server 配置
│
├── infrastructure/               # 外部系统和技术适配层
│   ├── llm/
│   │   ├── gateway.py            # LLM 统一网关、路由、重试与降级
│   │   └── providers/            # OpenAI、Anthropic 和本地模型
│   ├── intent_recognition/       # 外部意图识别实现
│   ├── rag/
│   │   ├── loaders/              # PDF、Markdown、HTML 等文档加载与解析
│   │   ├── embeddings/
│   │   │   ├── gateway.py        # Embedding 统一端口适配
│   │   │   └── providers/        # OpenAI、本地 Embedding 等实现
│   │   ├── vector_store.py       # pgvector、Qdrant 等向量检索适配
│   │   ├── document_store.py     # 原文、分块和来源元数据存储
│   │   ├── reranker.py           # 可选的检索结果重排适配
│   │   └── index_jobs.py         # 后台入库任务适配
│   ├── memory/
│   │   ├── short_term.py         # Redis 短期记忆
│   │   └── long_term.py          # 用户个人长期记忆，不代表 RAG 知识库
│   ├── storage/
│   │   ├── db.py                 # 数据库连接
│   │   └── repositories/         # 数据访问实现
│   ├── cache/                    # 缓存适配器
│   └── observability/
│       ├── tracing.py            # LangSmith 与 OpenTelemetry
│       └── metrics.py            # Prometheus 指标
│
├── config/                       # Settings 与环境配置
├── bootstrap.py                  # 唯一 composition root
└── main.py                       # 程序入口
```

### 最终边界

- API 只负责 HTTP/Cookie/SSE 的输入输出、身份提取和参数校验，不执行意图决策、工具授权或 Agent 业务流程。
- API 以 `auth`、`chat`、`session`、`knowledge` 等业务模块为组织单元，每个模块自主管理路由、Pydantic Schemas、专用依赖和传输映射。
- API 业务模块之间不直接引用对方内部文件；真正跨层共享的数据契约放在 `core`，而不是全局 API `schemas`。
- Core 只保存框架无关、可序列化的类型和契约，不依赖 FastAPI、Pydantic、LangChain 或供应商 SDK。
- Orchestration 是唯一流程所有者，负责意图路由、安全策略、Agent 执行和多步骤工作流，但不直接依赖具体供应商 SDK。
- `intent_recognition` 只负责返回意图分类结果、置信度和模型信息；未知意图、低置信度和失败关闭由 Orchestration 决定。
- Capabilities 管理 Prompt、Skill、Tool 和 MCP 能力资产；工具权限必须在 `capabilities/tools` 中定义，不得回流到意图识别模块。
- Infrastructure 封装模型、数据库、缓存、记忆和可观测性等外部 I/O，通过端口被编排层调用。
- RAG 入库与在线检索是两条独立流程：入库负责来源、校验和、版本、解析、切块、Embedding 与索引；检索负责 ACL 过滤、召回、重排、证据阈值和引用。
- RAG 知识库与 Memory 必须分离：Memory 存储用户对话派生的个人记忆，RAG 存储经管理的文档知识，两者使用独立的权限、保留期、索引和清理策略。
- 检索内容是不可信输入，不得将文档中的指令视为系统指令；Prompt 和工具执行权仍以系统策略为准。
- API 专用 Schema 必须放在对应业务模块中；只有不包含 HTTP/Pydantic 语义的跨层契约才能进入 `core`。
- Web 登录会话与 Agent 对话会话是两个独立概念：前者管理登录身份和 Cookie，后者管理对话历史和 Agent Context。

### 演进原则

- 最终目标结构是职责归属约束，不是要求立即创建所有目录。
- 只在出现真实用例时增加 `workflow_engine`、Skills、MCP、Redis、RAG、多模型网关和可观测性实现。
- 迁移采用小步、可测试、可独立验证的方式，每次只移动一类职责。
- 不得为了匹配最终目录树而创建空包、空 Service 或一行转发 Adapter。

### RAG 数据与执行流

```text
文档入库
  API 身份校验
    → KnowledgeIngestion
    → 来源与文件校验
    → Loader / Parser
    → Chunk Policy
    → Embedding
    → Document Store + Vector Store

在线问答
  Chat
    → IntentRouter
    → ToolPolicy
    → knowledge_search
    → RetrievalService
    → 可信上下文 ACL 过滤
    → Vector Search + 可选 Reranker
    → Chunks + Citations
    → Agent 最终回答
```

每个可检索分块至少保留 `tenant_id`、`knowledge_base_id`、`document_id`、`source_id`、`version`、`checksum`、`acl`、页码或段落位置等元数据，以支持权限过滤、去重、更新、删除和引用追溯。

RAG 建设顺序：

1. 定义 Document、Chunk、Citation、RetrievalQuery/Result 和 async 端口，使用内存 Fake 完成无费用测试。
2. 实现单一文档格式的入库、固定切块和一个 Embedding/向量库适配器。
3. 将 `knowledge_search` 注册为受意图与身份限制的工具，返回结构化证据和引用。
4. 增加多知识库 ACL、文档版本、后台索引任务、重排、评测集与可观测性。

## 依赖规则

- Core 不依赖 API、Orchestration、Capabilities、Infrastructure 或任何 Web/AI 框架。
- API 业务模块可依赖 Orchestration 的公开用例和 Core 契约，不得直接依赖 Infrastructure 中的具体供应商实现。
- Orchestration 可依赖 Core 契约、框架无关端口和 Capabilities 策略，不得导入 FastAPI、Pydantic、LangChain、LangGraph 或供应商 SDK 类型。
- Capabilities 不得反向控制 Orchestration；工具和 MCP 运行时通过显式端口使用。
- Infrastructure 实现端口，但不能控制 Orchestration。
- RAG Loader、Embedding、Vector Store 和 Reranker 都是 Infrastructure 适配器；Orchestration 只能依赖 `retrieval_ports.py` 中的框架无关端口。
- Bootstrap/composition root 是唯一允许同时引用 Orchestration、Capabilities 和 Infrastructure 具体实现的地方。

最终由 `tests/test_architecture.py` 自动检查这些边界；在该测试落地前，修改时仍必须人工遵守。

## 修改策略

- 不为旧路径或旧接口保留兼容层；需求变化时整体修改实现、测试和文档。
- 不新增只有一行转发逻辑的 Service、Repository 或 Adapter。
- 新增 API 时必须先确定所属业务模块，再在该模块内增加 `route.py`、`schemas.py` 或专用传输文件；不得回退到按技术类型集中组织的 `routes/` 或 `schemas/`。
- 新增意图优先修改 `INTENT_CATALOG`，再补充对应 Prompt 和 Tool Policy；编排流程不应出现按意图硬编码的分支。
- 新增模型、分类器或存储供应商时，实现现有端口并在 Bootstrap 替换组装。
- 新增知识库时，先声明所属数据域、可用意图、身份/ACL、引用策略和失败行为，再配置检索工具。
- 不把 FastAPI、Pydantic、LangChain、LangGraph 或供应商 SDK 类型泄漏到 Core 和 Orchestration 公开端口。

## 验证

```bash
python -m unittest discover -v
python -m compileall -q langHar tests
```

提交前同步 README、`.env.example`、测试和实现。
