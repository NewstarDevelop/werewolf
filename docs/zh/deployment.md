# Docker 部署指南

## 前置要求

- Docker 20.10+
- Docker Compose 2.0+
- 至少 2GB 内存
- 能够访问 LLM API 的网络环境

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/NewstarDevelop/werewolf.git
cd werewolf
```

### 2. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，设置必要的值：

```bash
# 必填
JWT_SECRET_KEY=至少32位的随机字符串

# 二选一：
OPENAI_API_KEY=sk-your-key-here
# 或
LLM_USE_MOCK=true
```

### 3. 启动服务

```bash
docker-compose up -d
```

### 4. 验证部署

```bash
# 检查容器状态
docker-compose ps

# 检查后端健康状态
curl http://localhost:8082/health

# 查看日志
docker-compose logs -f
```

## 服务端点

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:8081 | 游戏界面 |
| 后端 API | http://localhost:8082 | REST API |
| API 文档 | http://localhost:8082/docs | Swagger UI |
| ReDoc | http://localhost:8082/redoc | 备选文档 |

## 配置

### 必要设置

| 变量 | 必填 | 说明 |
|------|------|------|
| `JWT_SECRET_KEY` | 是 | 认证密钥 |
| `OPENAI_API_KEY` | 推荐 | 默认 LLM Provider |
| `CORS_ORIGINS` | 生产环境 | 你的域名 |

### 生产环境设置

```bash
# 生产环境 .env
JWT_SECRET_KEY=<生成的密钥>
OPENAI_API_KEY=<你的密钥>
CORS_ORIGINS=https://your-domain.com
DEBUG=false
LOG_LEVEL=WARNING
```

> **警告**：生产环境不要使用 `CORS_ORIGINS=*`，这会禁用 Cookie 认证。

## 数据卷挂载

| 挂载路径 | 用途 |
|----------|------|
| `./data:/app/data` | SQLite 数据库持久化 |
| `./.env:/app/.env` | 运行时配置（需启用 ENV_MANAGEMENT_ENABLED） |

## 健康检查

后端内置健康检查：

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

## 数据库迁移

启动时自动执行迁移。如需跳过：

```bash
RUN_DB_MIGRATIONS=false
```

手动执行迁移：

```bash
docker-compose exec backend alembic upgrade head
```

## 扩展约束

> **重要**：不要扩展到多个实例。

游戏状态存储在内存中，扩展会导致：
- 实例间状态不一致
- 游戏会话丢失
- 认证失败

如需水平扩展，必须先将游戏状态外置到 Redis 或 PostgreSQL。

## 故障排查

### 容器启动失败

```bash
# 查看日志
docker-compose logs backend

# 常见原因：
# - JWT_SECRET_KEY 未设置
# - OPENAI_API_KEY 无效
# - 数据库迁移失败
```

### 无法访问前端

```bash
# 确认前端容器运行中
docker-compose ps frontend

# 查看 nginx 日志
docker-compose logs frontend
```

### API 返回 401

- 确认 `JWT_SECRET_KEY` 已设置
- 检查 `CORS_ORIGINS` 包含你的域名
- 确保浏览器启用了 Cookie

### AI 无响应

- 检查 `LLM_USE_MOCK` 设置
- 验证 API Key 是否有效
- 检查速率限制设置

## 更新

```bash
# 拉取最新代码
git pull

# 重新构建并重启
docker-compose up -d --build
```

## 备份

```bash
# 备份数据库
cp data/werewolf.db data/werewolf.db.backup

# 备份配置
cp .env .env.backup
```
