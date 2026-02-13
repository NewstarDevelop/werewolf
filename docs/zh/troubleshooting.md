# 故障排查指南

Werewolf AI 常见问题与解决方案。

## 安装问题

### Docker 构建失败

**现象**：`docker-compose build` 失败

**解决方案**：
1. 检查 Docker 是否在运行
2. 确保磁盘空间充足
3. 尝试不使用缓存构建：
   ```bash
   docker-compose build --no-cache
   ```

### 容器启动后立即退出

**现象**：容器启动后马上停止

**查看日志**：
```bash
docker-compose logs backend
```

**常见原因**：
- `JWT_SECRET_KEY` 未设置
- 数据库路径无效
- 端口已被占用

## 配置问题

### 必要变量缺失

**现象**：后端启动时报配置错误

**解决方案**：检查所有必要变量已设置：
```bash
# 最低必要配置
JWT_SECRET_KEY=xxx
```

### CORS 错误

**现象**：浏览器控制台显示 CORS 错误

**解决方案**：
```bash
# 设置为你的前端域名
CORS_ORIGINS=http://localhost:5173
```

> 不要使用 `*` —— 这会禁用 Cookie 认证。

### API Key 无效

**现象**：AI 响应失败，返回 401/403

**解决方案**：
1. 验证 Key 是否正确
2. 检查 Key 是否有必要权限
3. 确保 .env 中没有多余空格

## 认证问题

### 登录返回 401

**原因**：
1. `JWT_SECRET_KEY` 未设置
2. Token 已过期
3. 凭据无效

**解决方案**：
```bash
# 验证 JWT_SECRET_KEY 是否已设置
grep JWT_SECRET_KEY .env

# 检查 Token 过期时间
JWT_EXPIRE_MINUTES=10080
```

### OAuth 重定向失败

**现象**：OAuth 登录重定向到错误页面

**检查**：
1. `LINUXDO_REDIRECT_URI` 完全匹配
2. Client ID/Secret 正确
3. OAuth 应用处于活跃状态

### 管理面板访问被拒绝

**解决方案**：
```bash
# 设置管理员密码
ADMIN_PASSWORD=your-password
```

## 游戏问题

### AI 无响应

**原因**：
1. API Key 无效
2. 速率限制超额
3. Provider 服务故障

**调试**：
```bash
# 启用调试日志
LOG_LEVEL=DEBUG

# 查看日志
docker-compose logs -f backend | grep LLM
```

### WebSocket 断开连接

**原因**：
1. 网络问题
2. 代理超时
3. 服务器重启

**解决方案**：
1. 检查网络稳定性
2. 增加代理超时时间
3. 前端会自动重连

### 游戏状态丢失

**原因**：服务器重启（游戏状态存储在内存中）

**预防措施**：
- 在活跃游戏期间避免重启
- 在低活跃期安排维护

## 性能问题

### AI 响应缓慢

**原因**：
1. Provider 延迟
2. 速率限制
3. 上下文过大

**解决方案**：
```bash
# 增加超时时间
LLM_MAX_WAIT_SECONDS=15

# 减少并发请求
LLM_PER_GAME_MAX_CONCURRENCY=1
```

### 内存使用过高

**原因**：
1. 活跃游戏过多
2. 内存泄漏
3. 日志过大

**解决方案**：
1. 重启容器
2. 限制并发游戏数
3. 检查是否有失控进程

### 数据库缓慢

**解决方案**：
1. 切换到 PostgreSQL
2. 添加数据库索引
3. 归档旧数据

## 前端问题

### 白屏

**检查**：
1. 浏览器控制台错误
2. 网络标签中的失败请求
3. 前端容器日志

### 样式未加载

**原因**：构建问题

**解决方案**：
```bash
# 重新构建前端
docker-compose build frontend --no-cache
docker-compose up -d frontend
```

### 语言切换不工作

**原因**：i18n 配置问题

**解决方案**：
1. 检查翻译文件是否存在
2. 清除浏览器缓存
3. 验证语言检测设置

## 数据库问题

### 迁移失败

**现象**：后端无法启动，日志中有迁移错误

**解决方案**：
```bash
# 检查迁移状态
docker-compose exec backend alembic current

# 手动执行迁移
docker-compose exec backend alembic upgrade head

# 如果损坏，重置（会丢失数据）
rm data/werewolf.db
docker-compose restart backend
```

### 数据库锁定

**原因**：SQLite 并发访问

**解决方案**：
1. 重启后端
2. 检查是否有多个进程
3. 考虑使用 PostgreSQL

## Docker 问题

### 卷权限被拒绝

**原因**：文件所有权不正确

**解决方案**：
```bash
# 修复权限
chmod -R 777 data/
```

### 容器网络问题

**现象**：服务间无法通信

**解决方案**：
```bash
# 重新创建网络
docker-compose down
docker network prune
docker-compose up -d
```

## 获取帮助

### 收集调试信息

```bash
# 系统信息
docker version
docker-compose version

# 容器状态
docker-compose ps

# 最近日志
docker-compose logs --tail=500 > debug.log

# 配置信息（隐藏密钥）
grep -v "KEY\|SECRET\|PASSWORD" .env > config.txt
```

### 提交问题

1. 先检查 GitHub 上已有的 Issues
2. 附上调试信息
3. 描述复现步骤
4. 说明期望行为与实际行为
