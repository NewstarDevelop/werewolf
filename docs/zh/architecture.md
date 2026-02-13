# 系统架构

## 概览

Werewolf AI 采用现代 Web 应用架构，具备实时通信能力。

```
+------------------+       +------------------+       +------------------+
|      前端        |       |      后端        |       |   LLM Providers  |
|    (React)       | <---> |    (FastAPI)     | <---> |  (OpenAI 等)     |
+------------------+       +------------------+       +------------------+
        |                          |
        |                          |
        v                          v
   浏览器存储              SQLite/PostgreSQL
                                   |
                                   v
                              Redis (可选)
```

## 组件

### 前端

| 组件 | 技术 | 用途 |
|------|------|------|
| 框架 | React 18.3+ | UI 渲染 |
| 语言 | TypeScript 5.0+ | 类型安全 |
| 构建 | Vite 5.0+ | 快速开发 |
| 样式 | TailwindCSS | 原子化 CSS |
| 组件 | shadcn/ui | 统一设计 |
| 状态 | React Query | 服务端状态管理 |
| 国际化 | i18next | 多语言支持 |
| 实时 | WebSocket | 游戏实时更新 |

### 后端

| 组件 | 技术 | 用途 |
|------|------|------|
| 框架 | FastAPI 0.104+ | API 服务 |
| ORM | SQLAlchemy 2.0+ | 数据库抽象 |
| 迁移 | Alembic | 数据库版本控制 |
| 认证 | JWT + OAuth2 | 身份验证 |
| AI | OpenAI SDK | LLM 集成 |
| 缓存 | Redis (可选) | 通知系统 |

## 数据流

### 游戏状态

```
玩家操作 --> WebSocket --> GameStore (内存) --> 广播
                                |
                                v
                          数据库 (持久化)
```

> **警告**：游戏状态存储在内存中（GameStore）。这要求单实例部署。

### 认证流程

```
用户 --> OAuth (linux.do) --> 后端 --> JWT Token --> 客户端
     --> 密码登录          --> 后端 --> JWT Token --> 客户端
```

### LLM 请求流程

```
游戏事件 --> LLM 服务 --> Provider 选择 --> API 调用 --> 响应
                |
                v
         速率限制器 --> 重试逻辑 --> 错误处理
```

## 目录结构

```
werewolf/
├── backend/
│   ├── app/
│   │   ├── api/          # REST 接口
│   │   ├── core/         # 配置、安全
│   │   ├── models/       # SQLAlchemy 模型
│   │   ├── schemas/      # Pydantic 模式
│   │   ├── services/     # 业务逻辑
│   │   │   ├── llm/      # LLM Providers
│   │   │   └── game/     # 游戏逻辑
│   │   └── i18n/         # 翻译文件
│   ├── migrations/       # Alembic 迁移
│   └── scripts/          # 工具脚本
│
├── frontend/
│   ├── src/
│   │   ├── components/   # UI 组件
│   │   ├── pages/        # 页面组件
│   │   ├── hooks/        # 自定义 Hooks
│   │   ├── lib/          # 工具函数
│   │   └── types/        # TypeScript 类型
│   └── public/           # 静态资源
│
├── docs/                 # 文档
├── data/                 # SQLite 数据库 (Docker)
└── docker-compose.yml    # 容器编排
```

## 部署约束

### 单实例要求

当前架构将游戏状态存储在内存中（`GameStore` 类）。这意味着：

- **不要**扩展为多副本
- **不要**使用 uvicorn 的 `--workers > 1`
- **不要**使用负载均衡跨多容器

要实现水平扩展，必须先将游戏状态外置到 Redis 或数据库。

### 单进程要求

环境变量管理使用 `threading.Lock`，仅在单进程内有效：

- 使用 `uvicorn app.main:app --workers=1`
- 或在多进程环境中禁用 `ENV_MANAGEMENT_ENABLED`

## 网络端口

| 服务 | 内部端口 | 外部端口 |
|------|----------|----------|
| 后端 | 8000 | 8082 |
| 前端 | 80 | 8081 |

## 安全考虑

- JWT Token 用于无状态认证
- 需要配置 CORS 以支持 Cookie 认证
- 管理面板中敏感配置已脱敏
- LLM API 调用有速率限制
