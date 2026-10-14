# 参与贡献

THar 当前验证Studio 接入、普通对话和受控知识库问答。启动步骤见 [README.md](./README.md)，
架构与安全约束见 [AGENTS.md](./AGENTS.md)。

```bash
python -m pip install -e '.[dev]'
python -m unittest discover -v
python -m compileall -q langHar tests
```

修改时保持 MVP 范围，不恢复占位功能或引入空抽象。新意图先修改 INTENT_CATALOG，
补齐 Prompt、工具权限和失败关闭测试。知识检索始终使用应用固定的本地上下文和本轮证据。

测试必须使用 Fake，不能调用真实模型或产生费用。不要提交密钥、环境文件、
索引或用户文档。PR 说明应包含具体行为变化和验证结果；同步文档与 .env.example。
