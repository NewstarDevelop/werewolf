# 运维指南

本指南涵盖 Werewolf AI 的监控、维护和运维任务。

## 监控

### 健康检查

后端健康端点：

```bash
curl http://localhost:8082/health
```

响应：
```json
{"status": "healthy"}
```

### 应用状态

根端点提供运行时信息：

```bash
curl http://localhost:8082/
```

响应：
```json
{
  "status": "ok",
  "message": "Werewolf AI Game API is running",
  "version": "1.0.0",
  "llm_mode": "real"  // 或 "mock"
}
```

### Docker 健康状态

```bash
# 容器状态
docker-compose ps

# 容器健康检查
docker inspect werewolf-backend --format='{{.State.Health.Status}}'
```

## 日志

### 日志级别

通过环境变量配置：

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### 查看日志

```bash
# Docker 日志
docker-compose logs -f backend

# 最近 100 行
docker-compose logs --tail=100 backend

# 指定时间范围
docker-compose logs --since="2024-01-01" backend
```

### 日志格式

```
2024-01-15 10:30:45 - app.main - INFO - Game logging initialized
```

组成部分：
- 时间戳
- 日志器名称
- 级别
- 消息

### 重要日志模式

| 模式 | 含义 |
|------|------|
| `WL-001` | 房间已创建 |
| `WL-011` | 孤立房间已重置 |
| `LLM call` | AI 请求已发出 |
| `WebSocket` | 连接事件 |

## 数据库

### SQLite 位置

默认：`./data/werewolf.db`

### 备份

```bash
# 停止写入（可选但推荐）
docker-compose stop backend

# 复制数据库
cp data/werewolf.db data/werewolf.db.backup

# 恢复运行
docker-compose start backend
```

### 迁移

检查状态：
```bash
docker-compose exec backend alembic current
```

应用迁移：
```bash
docker-compose exec backend alembic upgrade head
```

回滚：
```bash
docker-compose exec backend alembic downgrade -1
```

### PostgreSQL（备选方案）

生产环境可考虑 PostgreSQL：

1. 更新配置中的数据库 URL
2. 调整 Docker Compose 添加 PostgreSQL 服务
3. 执行迁移

## 内存管理

### 游戏状态

游戏状态存储在内存中。通过以下方式监控：

```bash
# 容器内存使用
docker stats werewolf-backend
```

### 内存限制

在 Docker Compose 中添加：

```yaml
backend:
  deploy:
    resources:
      limits:
        memory: 1G
```

## 安全

### 密钥轮换

定期轮换以下密钥：
- `JWT_SECRET_KEY`
- `ADMIN_PASSWORD`
- API 密钥

流程：
1. 生成新密钥
2. 更新 .env
3. 重启服务
4. 活跃会话将失效

### 访问日志

监控可疑活动：

```bash
docker-compose logs backend | grep "401\|403"
```

## 更新

### 更新流程

```bash
# 拉取最新代码
git pull origin main

# 重新构建容器
docker-compose build

# 使用新版本重启
docker-compose up -d

# 验证部署
curl http://localhost:8082/health
```

### 回滚

```bash
# 回退到之前的提交
git checkout <previous-commit>

# 重新构建并重启
docker-compose up -d --build
```

## 故障排查

### 容器无法启动

```bash
# 查看日志
docker-compose logs backend

# 常见原因：
# - 必要环境变量缺失
# - 数据库迁移失败
# - 端口冲突
```

### 内存使用过高

- 检查游戏会话是否有泄漏
- 监控活跃 WebSocket 连接
- 考虑定期重启

### 响应缓慢

- 检查 LLM Provider 状态
- 检查速率限制设置
- 监控数据库查询耗时

## 维护窗口

### 计划维护

1. 通知用户即将进行维护
2. 等待活跃游戏结束
3. 停止服务
4. 执行维护
5. 启动服务
6. 验证功能

### 紧急维护

1. 立即停止服务
2. 活跃游戏将丢失（内存存储）
3. 执行紧急修复
4. 重启服务

## 扩展说明

当前架构限制：
- 仅支持单实例
- 游戏状态存储在内存中
- 单 Worker 进程

水平扩展需要：
1. 将游戏状态外置到 Redis/PostgreSQL
2. 实现分布式锁
3. 使用粘性会话或共享会话存储
