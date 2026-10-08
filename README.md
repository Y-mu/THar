# langHar 服务端意图优先 Agent

`langHar` 是独立实现，不导入或运行 `thar` 目录中的代码。

## 调用流程

```text
用户输入
  → JevIntention：只负责意图识别
  → IntentRouter：检查未知意图和置信度
      ├─ 拒绝：返回澄清提示，不创建 Agent
      └─ 接受：调用启动时已创建的单 Agent
```

服务启动时，`create_agent_service()` 只创建一个 Agent。请求期间不重复创建
模型或 Agent；路由结果用于从 `INTENT_CATALOG` 选择系统提示词。

当前是便于继续手写的最小骨架，Agent 暂未注册业务工具。天气和计算工具的
动态授权、执行与工具事件可在下一步逐项接入。

关键文件：

- `langHar/agents/jev_intention.py`：JEV 意图识别适配器。
- `langHar/agents/intent_router.py`：故障关闭的路由策略。
- `langHar/agents/intent_catalog.py`：意图、criteria、提示词和工具权限的单一配置源。
- `langHar/bootstrap.py`：服务端 composition root，只在启动阶段调用一次。
- `langHar/agents/agent.py`：长生命周期 `AgentService`，供后续接口层调用。
- `langHar/agents/langchain_agent.py`：创建并封装唯一的 LangChain Agent。
- `langHar/agents/core/agent_event.py`：框架无关的流式事件。
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

## 服务端接入

在 Web 服务的 startup/lifespan 阶段创建一次：

```python
from langHar.bootstrap import create_agent_service

agent_service = create_agent_service()
```

后续接口取得会话历史后调用：

```python
answer = await agent_service.handle_message(
    "北京天气怎么样",
    session_id="session-123",
    history=history,
)
```

流式接口使用 `stream_message(...)`，当前只产出 `token` 和 `final` 事件。
接口层负责读取和持久化会话历史，并且只应保存用户消息和 `final` 回答。
所有调用都必须传入非空 `session_id`，并始终先经过意图路由。

## 测试

测试使用假的意图识别器，不会请求 JEV 或 DeepSeek：

```bash
python -m unittest discover -s tests -v
python -m compileall -q langHar tests
```
