# Redis 通知系统

Werewolf AI 使用 Redis 实现跨实例的通知广播。

## 概览

Redis 提供以下功能：
- 跨实例的实时通知
- 发布/订阅消息
- 会话状态共享（未来规划）

> **注意**：Redis 是可选的。单实例模式下系统可在无 Redis 的情况下正常运行。

## 配置

```bash
REDIS_URL=redis://localhost:6379/0
```

### URL 格式

```
redis://[:password]@host:port/db
```

示例：
```bash
# 本地无密码
REDIS_URL=redis://localhost:6379/0

# 带密码
REDIS_URL=redis://:mypassword@localhost:6379/0

# 远程服务器
REDIS_URL=redis://:pass@redis.example.com:6379/0
```

## 回退行为

未配置 Redis 时：

| 功能 | 行为 |
|------|------|
| 通知 | 仅在单实例内工作 |
| 游戏状态 | 保持内存存储（无变化） |
| WebSocket | 正常工作 |

系统会记录警告日志但继续运行。

## 使用场景

### 通知

Redis 可用时：
- 管理员广播到达所有实例
- 系统告警传播到所有节点
- 用户通知保持一致

### 未来：状态共享

Redis 可实现：
- 多实例游戏状态
- 水平扩展
- 会话复制

> **当前状态**：游戏状态仍存储在内存中。Redis 仅用于通知系统。

## Docker Compose 配置

在部署中添加 Redis：

```yaml
services:
  redis:
    image: redis:7-alpine
    container_name: werewolf-redis
    restart: unless-stopped
    ports:
      - "6379:6379"
    volumes:
      - redis-data:/data

  backend:
    environment:
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - redis

volumes:
  redis-data:
```

## 健康检查

后端在启动时检查 Redis 连接状态：
- 成功：启用 Redis 通知
- 失败：回退到单实例模式

## 性能

Redis 增加的开销极小：
- 发布/订阅是轻量级操作
- Redis 中不存储游戏关键数据
- Redis 失败时优雅降级

## 故障排查

### 连接被拒绝

- 确认 Redis 正在运行
- 检查网络连通性
- 确认端口可访问

```bash
# 测试连接
redis-cli -h localhost -p 6379 ping
```

### 认证失败

- 检查 REDIS_URL 中的密码
- 验证 Redis AUTH 配置
- 确保特殊字符已正确转义

### 通知不工作

- 检查 REDIS_URL 是否已设置
- 查看后端日志中的 Redis 连接信息
- 手动测试发布/订阅：

```bash
# 终端 1：订阅
redis-cli subscribe notifications

# 终端 2：发布
redis-cli publish notifications "test"
```

## 扩展考虑

仅有 Redis 并不能完全实现后端的水平扩展：

| 组件 | 扩展状态 |
|------|----------|
| 通知 | Redis 就绪 |
| 游戏状态 | 需要架构变更 |
| WebSocket | 需要粘性会话 |

要完全扩展，必须将游戏状态外置到 Redis 或数据库。
