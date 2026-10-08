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
- 意图、criteria、系统提示词和工具权限以 `INTENT_CATALOG` 为单一配置源。
- 测试不得调用真实模型或产生 API 费用。

## 当前架构

- `thar/core`：框架无关的可序列化类型与端口。
- `thar/application`：意图目录和应用策略。
- `thar/orchestration`：LangGraph 状态、节点和工作流，是唯一流程所有者。
- `thar/integrations`：外部 SDK、模型、工具和存储适配器。
- `thar/bootstrap.py`：唯一 composition root。
- `thar/cli.py`：CLI 输入输出适配器。

当前目录是实现选择，不是不可改变的产品约束。重构时优先维持稳定约束、清晰职责和单向依赖，不为保留目录形式制造空抽象。

## 依赖规则

- Core 不依赖 Application、Orchestration、Integrations 或任何 AI 框架。
- Application 只依赖 Core。
- Orchestration 依赖 Application 和 Core，但不知道具体 Integrations。
- Integrations 可实现 Core 端口并读取 Application 配置，但不能控制 Orchestration。
- Bootstrap 是唯一允许同时引用所有区域的地方。

`tests/test_architecture.py` 自动检查这些边界。

## 修改策略

- 不为旧路径或旧接口保留兼容层；需求变化时整体修改实现、测试和文档。
- 不新增只有一行转发逻辑的 Service、Repository 或 Adapter。
- 新增意图优先修改 `INTENT_CATALOG`，编排图不应出现按意图硬编码的节点。
- 新增模型、分类器或存储供应商时，实现现有端口并在 Bootstrap 替换组装。
- 不把 LangChain、LangGraph 或供应商 SDK 类型泄漏到 Core。

## 验证

```bash
python -m unittest discover -v
python -m compileall -q thar tests
```

提交前同步 README、`.env.example`、测试和实现。
