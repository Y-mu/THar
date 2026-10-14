# THar MVP 项目记忆

## 范围

当前 MVP 保留普通对话、知识库目录、Markdown/TXT 上传和受控问答。
用户已要求移除登录功能，直接运行 langgraph dev 并连接 LangGraph Studio。
不恢复项目登录、token、Cookie、演示账号或终端登录客户端。
不要恢复天气、搜索、计算示例、多格式解析或空的规划目录。
启动直接使用 `langgraph dev`；可选脚本 `bash scripts/dev.sh` 固定项目虚拟环境和配置。

## 运行架构

- `langgraph.json` 注册唯一主图和挂载 HTTP app；无自定义 Server 认证。
- Studio 只通过明确的 CORS 白名单接入；私有网络预检仅在 local_dev 允许。
- `composition/graph.py`：START → IntentRouter + ToolPolicy → 普通 Agent / 知识库节点 / 澄清 / 拒绝。
- 普通 Agent 使用 LangChain `create_agent()`，不注册业务工具。
- 知识库节点在一轮内执行授权工具、成文、引用校验，只在校验后提交最终消息。
- LangGraph Server 的 thread/checkpointer 管理历史、运行和原生流式协议。
- HTTP API 按 knowledge、health 模块组织，只负责上传与健康检查。
- Bootstrap 是唯一具体依赖组装入口；图入口与 HTTP 入口不构造另一套调度层。

## 必须保留

- 请求必须先通过可信意图分类和工具授权，不能直接调用 Agent 或检索。
- 未知意图、低置信度、分类服务不可用必须故障关闭，仅澄清。
- 服务调用必须显式传入非空 thread_id（对应 AgentContext.session_id）。
- 公开图输入只有 messages；Studio 使用原生 thread/run 和状态调试功能。
- 无登录模式使用应用固定的本地上下文：user_id=0、ADMIN、default 租户和知识库；不能从输入、configurable、模型参数或旧检查点选择身份或数据范围。
- thread 由 LangGraph Server 管理，无用户所有权隔离；不要保留旧认证钩子。
- 工具可见性和执行受意图、身份最小授权约束；普通对话 Agent 没有业务工具。
- 当前只有 default 租户和 default 知识库；新增范围时必须由应用配置决定。
- 知识检索须验证租户、知识库和文档 ACL，模型不能选择检索范围或传入 runtime。
- 目录读取 ACL 过滤后的元数据，不能使用 Top-K 相似度检索枚举目录。
- 无权限、检索不可用、证据不足、引用缺失或伪造必须拒答，不得退化为模型常识回答。
- 每轮必须重新检索；历史工具结果不能替代本轮证据。
- 检索内容是不可信数据，文档指令不得成为系统指令。
- 知识库计划和成文调用带 TAG_NOSTREAM，未审计草稿不进入 messages/values/updates/检查点。
- Checkpointer 保存完整消息协议，包括工具调用与结果；中断后的协议补齐由服务端完成。
- 分块保留 tenant_id、knowledge_base_id、document_id、source_id、version、checksum、acl 和位置。
- INTENT_CATALOG 是意图与 criteria 的单一来源；Prompt、工具注册和权限属于 capabilities。
- Bootstrap 在构造模型前检查意图、Prompt、工具、回答策略和权限配置，不一致拒绝启动。
- 外部 I/O 优先 async；服务器保留 LangGraph 原生 token、工具消息和最终状态协议。
- 测试不得调用真实 LLM、JEV、Embedding、Reranker 或产生 API 费用。

## 依赖边界

- Core 只保存框架无关契约，不依赖其他业务层或 FastAPI、Pydantic、LangChain、LangGraph。
- API 可依赖 Core 和自己拥有的端口；不能导入编排、能力或基础设施具体实现。
- API Schema 属于对应业务模块，不创建全局 schemas/routes。
- Orchestration 保存意图、ACL、检索与引用规则及框架无关端口，不依赖供应商或 AI/Web 框架。
- Composition 使用 LangGraph/LangChain，依赖 Core、Orchestration 和 Capabilities，不导入 API 或 Infrastructure。
- Infrastructure 实现 I/O 端口，不控制业务路由；RAG 和个人 Memory 不混合。
- Bootstrap 是唯一允许同时引用各层具体实现的地方。
- 图工厂不内置 checkpointer，由 Server 注入；测试可注入 InMemorySaver。

## 修改与验证

不保留旧路径兼容层，不新增空包或只有转发逻辑的 Adapter。
按真实 MVP 用例增加实现，同步 README、.env.example、测试和配置。
本地文档、模型、索引和环境配置属于用户数据，精简代码时不要删除。

```bash
python -m unittest discover -v
python -m compileall -q langHar tests
```
