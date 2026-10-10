# langHar 服务端意图优先 Agent

`langHar` 是独立实现，不导入或运行 `thar` 目录中的代码。

# 启动项目

```bash
source env/bin/activate
python -m pip install -e .
uvicorn langHar.api.app:app --reload --host 127.0.0.1 --port 8000
```

接口文档：<http://127.0.0.1:8000/docs>

## 调用流程

```text
用户输入
  → IntentRecognitionService
      → JevIntention：调用外部识别服务
      → 检查未知意图和置信度
      ├─ 拒绝：返回澄清提示，不创建 Agent
      └─ 接受：ToolPolicy 检查意图和身份等级
          ├─ 拒绝：返回无权限提示，不执行工具
          └─ 接受：调用启动时已创建的单 Agent
```

服务启动时，`create_agent_service()` 只创建一个 Agent。请求期间不重复创建
模型或 Agent；路由结果用于从 `INTENT_CATALOG` 选择系统提示词。

每次调用通过 `AgentContext` 显式传入 `session_id`、`user_id`、身份等级和
历史消息。LangChain 中间件只向模型暴露本次获得授权的工具，并在工具实际
执行前再次检查权限。

关键文件：

- `langHar/agents/intent_recognition`：意图目录、识别契约、JEV 适配器和故障关闭服务。
- `langHar/agents/factory.py`：创建并组装服务端 Agent，只在启动阶段调用一次。
- `langHar/agents/agent_service.py`：无状态的意图路由与 Agent 执行服务。
- `langHar/agents/core/agent_context.py`：一次 Agent 调用的身份和历史上下文。
- `langHar/agents/tool_policy.py`：意图与身份等级的工具授权策略。
- `langHar/agents/langchain_agent.py`：创建并封装唯一的 LangChain Agent。
- `langHar/agents/core/agent_event.py`：框架无关的流式事件。
- `langHar/api/app.py`：FastAPI 应用和 lifespan。
- `langHar/api/modules/auth`：Cookie 登录会话、当前用户和认证路由。
- `langHar/api/modules/conversation`：用户对话、消息历史和 CRUD 路由。
- `langHar/api/modules/chat`：协调 Conversation 历史、Agent 调用和最终消息保存。
- `langHar/api/modules/chat/sse.py`：将应用事件映射并编码为 SSE 传输事件。
- `langHar/api/modules/health`：存活和就绪检查路由。
- `langHar/tools/base_tools.py`：工具注册表。

## 安装和配置

需要 Python 3.11 或更高版本。macOS 自带的 `/usr/bin/python3` 可能仍是
Python 3.9，请用 3.11+ 创建虚拟环境。

```bash
python3.13 -m venv env
source env/bin/activate
python -m pip install -e .
cp .env.example .env
```

至少配置：

```dotenv
DEEPSEEK_API_KEY=你的_DeepSeek_Key
TYPESAFE_API_KEY=你的_JEV_Token
```

同时兼容 `LLM_API_KEY` 和 `JEV_API_KEY`。

当前 MVP 在 `AuthService.login()` 中写死了两组演示账号：

```text
admin / password  # admin，可使用天气和计算工具
tony / 123456     # user，可使用天气工具
```

后续接入数据库时，应删除硬编码账号并使用密码哈希。

## API 使用

登录并保存 Cookie：

```bash
curl -i -c cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"username":"admin","password":"password"}' \
  http://127.0.0.1:8000/api/v1/users/login
```

创建 Conversation：

```bash
curl -b cookies.txt -X POST \
  http://127.0.0.1:8000/api/v1/conversations
```

向 Agent 发送消息（将 `{conversation_id}` 替换为创建结果）：

```bash
curl -N -b cookies.txt \
  -H 'Content-Type: application/json' \
  -d '{"content":"你好"}' \
  http://127.0.0.1:8000/api/v1/chat/{conversation_id}/messages
```

该接口返回 `text/event-stream`。每个事件的 `data` 都是 `ChatResponse`
序列化后的 JSON，事件类型包括 `token`、`tool_start`、`tool_end`、`final`
和 `error`。只有收到 `final` 时，服务端才会持久化本轮用户消息和最终回答。

当前用户、会话和登录 Cookie 都保存在单进程内存中，服务重启后会丢失。
这是便于继续手写的开发版本；接入数据库后再使用多 worker 部署。

## 服务端接入

在 Web 服务的 startup/lifespan 阶段创建一次：

```python
from langHar.agents.factory import create_agent_service

agent_service = create_agent_service()
```

后续接口取得会话历史后调用：

```python
from langHar.agents.core.agent_context import AgentContext, IdentityLevel

final_event = await agent_service.invoke(
    "北京天气怎么样",
    context=AgentContext(
        session_id="session-123",
        user_id=0,
        identity_level=IdentityLevel.ADMIN,
        history=history,
    ),
)
```

非流式接口 `invoke(...)` 返回最终 `AgentEvent`；流式接口 `stream(...)`
产出 `token`、工具和 `final` 事件。
接口层负责读取和持久化会话历史，并且只应保存用户消息和 `final` 回答。
所有调用都必须通过 `AgentContext` 传入非空 `session_id`，并始终先经过
意图路由和工具授权。

## 测试

测试使用假的意图识别器，不会请求 JEV 或 DeepSeek：

```bash
python -m unittest discover -s tests -v
python -m compileall -q langHar tests
```
