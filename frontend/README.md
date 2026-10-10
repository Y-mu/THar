# THar Frontend

THar 的 Web 客户端，使用 Next.js App Router、React 和 TypeScript。

## 项目结构

```text
frontend/
├── app/                         # 按页面组织的业务模块
│   ├── chat/
│   │   ├── components/
│   │   │   └── ChatPage.tsx    # 会话列表与流式对话界面
│   │   ├── chat.ts             # Conversation API 与 SSE 解析
│   │   ├── page.tsx            # /chat 路由入口
│   │   └── types.ts            # 对话页面类型
│   ├── login/
│   │   ├── components/
│   │   │   └── LoginForm.tsx   # 登录页面组件
│   │   ├── login.ts            # 登录接口调用
│   │   ├── page.tsx            # /login 路由入口
│   │   └── types.ts            # 登录页面类型
│   ├── globals.css
│   ├── layout.tsx
│   └── page.tsx
├── shared/                      # 不包含业务语义的共享代码
│   └── api/
│       └── client.ts           # 通用 HTTP 客户端
└── public/                      # 静态资源
```

## 依赖规则

- `app` 下的每个页面目录都是独立模块，相关组件、请求和类型就近存放。
- 页面模块之间不直接引用内部文件；需要跨页面复用时再移动到 `shared`。
- `shared` 只放跨页面复用且不包含具体页面语义的代码，并且不能依赖 `app`。
- 暂时不创建空的 `hooks`、`stores`、`services` 等目录，实际需要时再在对应页面中增加。

## 本地运行

先在项目根目录启动 FastAPI：

```bash
source env/bin/activate
uvicorn langHar.main:app --reload --host 127.0.0.1 --port 8000
```

再启动前端：

```bash
npm install
cp .env.example .env.local
npm run dev
```

浏览器访问 <http://localhost:3000>，登录页地址为 <http://localhost:3000/login>，
对话页地址为 <http://localhost:3000/chat>。
Next.js 会将 `/api/*` 同源转发到 `BACKEND_URL`，使后端 HttpOnly Cookie
可以直接用于前端登录状态。

对话页面支持创建和切换 Conversation、读取历史消息，并通过 POST 请求消费
`token`、`tool_start`、`tool_end`、`final` 和 `error` SSE 事件。

演示账号：

```text
admin / password  # admin
tony / 123456     # user
```

## 验证

```bash
npm run lint
npm run build
```
