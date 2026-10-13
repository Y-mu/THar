# 参与贡献

感谢你愿意参与 THar。项目仍处于 Alpha 阶段，当前目标是保持脚手架简单、可运行，并逐步验证真实的 Agent 服务端需求。

## 开始之前

- Bug、文档修正和小型重构可以直接提交 Pull Request。
- 新架构层、大型依赖或行为变化，建议先创建 Issue 说明使用场景和设计取舍。
- 不要提交 API Key、Cookie、真实用户数据或本地 `.env`。
- 测试必须使用 Fake 实现，不得调用真实模型或产生 API 费用。

## 本地开发

后端：

```bash
python3 -m venv env
source env/bin/activate
python -m pip install -e .
python -m unittest discover -v
python -m compileall -q langHar tests
```

前端：

```bash
cd frontend
npm ci
npm run lint
npm run build
```

## 架构约束

- 用户请求必须先经过意图路由，不允许直接绕过路由调用 Agent。
- 未知意图、低置信度或分类服务异常必须进入澄清流程。
- 工具根据意图和身份等级进行最小授权。
- Core 不依赖 FastAPI、LangChain、LangGraph 或供应商 SDK。
- API 只能通过自身定义的端口调用 Agent，不直接导入 Agent 具体实现。
- Bootstrap 是唯一可以同时组装 API、Agent 编排层与基础设施层的位置。
- 会话只保存用户消息和最终回答，不保存内部工具记录。

完整约束和长期目标参见 [AGENTS.md](./AGENTS.md)。

## Pull Request 检查清单

- 变更范围小而清晰，没有无需求支撑的空抽象。
- 新行为有测试，异常和越权路径采用故障关闭策略。
- README、`.env.example`、测试和实现保持一致。
- 后端测试与编译检查通过；涉及前端时，Lint 和生产构建通过。
- Pull Request 说明包含修改原因、验证方式和必要的设计取舍。
