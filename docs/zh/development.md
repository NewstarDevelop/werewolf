# 本地开发指南

## 前置要求

- Python 3.10+
- Node.js 18+
- Git

## 后端搭建

### 1. 创建虚拟环境

```bash
cd backend

# 创建虚拟环境
python -m venv venv

# 激活（Linux/macOS）
source venv/bin/activate

# 激活（Windows）
venv\Scripts\activate
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

```bash
# 从项目根目录
cp .env.example .env
```

编辑 `.env`：

```bash
JWT_SECRET_KEY=dev-secret-key-for-local-development
OPENAI_API_KEY=sk-your-key-here
DEBUG=true
LOG_LEVEL=DEBUG
```

### 4. 初始化数据库

```bash
# 执行迁移
alembic upgrade head
```

### 5. 启动后端

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端访问地址：http://localhost:8000

## 前端搭建

### 1. 安装依赖

```bash
cd frontend
npm install
```

### 2. 配置 API 地址（可选）

不使用 Docker 时直接连接后端：

```bash
# 创建 .env.local
echo "VITE_API_URL=http://localhost:8000" > .env.local
```

### 3. 启动开发服务器

```bash
npm run dev
```

前端访问地址：http://localhost:5173

## 开发工作流

### 同时运行两个服务

打开两个终端：

**终端 1 - 后端：**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

**终端 2 - 前端：**
```bash
cd frontend
npm run dev
```

### 代码质量

**后端：**
```bash
# 格式化代码
black app/

# 类型检查
mypy app/

# 代码检查
ruff check app/
```

**前端：**
```bash
# 类型检查
npm run typecheck

# 代码检查
npm run lint

# 格式化
npx prettier --write src/
```

### 测试

**后端：**
```bash
cd backend
pytest

# 带覆盖率
pytest --cov=app
```

**前端：**
```bash
cd frontend
npm run test

# 带 UI
npm run test:ui

# 带覆盖率
npm run test:coverage
```

### 数据库迁移

创建新迁移：

```bash
cd backend
alembic revision --autogenerate -m "Add new table"
```

应用迁移：

```bash
alembic upgrade head
```

回滚：

```bash
alembic downgrade -1
```

## 项目结构

### 后端关键文件

| 文件 | 用途 |
|------|------|
| `app/main.py` | FastAPI 应用入口 |
| `app/core/config.py` | 配置加载 |
| `app/api/api.py` | API 路由注册 |
| `app/services/game/` | 游戏逻辑 |
| `app/services/llm/` | LLM Providers |

### 前端关键文件

| 文件 | 用途 |
|------|------|
| `src/App.tsx` | 应用入口 |
| `src/pages/` | 页面组件 |
| `src/components/` | 可复用组件 |
| `src/hooks/` | 自定义 React Hooks |
| `src/lib/` | 工具函数 |

## 调试

### 后端调试

使用 VS Code：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload"],
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

### 前端调试

React DevTools 和浏览器开发者工具可直接使用。

VS Code + Chrome 调试：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "chrome",
      "request": "launch",
      "name": "React",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/frontend/src"
    }
  ]
}
```

## Mock 模式

无需 LLM API 费用的开发模式：

```bash
LLM_USE_MOCK=true
```

AI 玩家将使用预设消息回复，而不调用 API。

## 常见问题

### CORS 错误

确保后端 CORS 已配置：

```bash
CORS_ORIGINS=http://localhost:5173
```

### WebSocket 连接失败

- 检查后端是否在正确端口运行
- 确认没有代理阻止 WebSocket

### 数据库锁定

SQLite 在并发访问时可能锁定。解决方案：
- 重启后端
- 使用 PostgreSQL 进行重度开发
