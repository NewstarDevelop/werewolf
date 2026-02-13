# 环境变量管理

Werewolf AI 内置管理功能，可通过 Web 界面编辑环境变量。

## 概览

启用后，管理员可以：
- 查看所有环境变量
- 编辑非敏感值
- 无需服务器访问即可更新配置
- 查看哪些变量是必填的

## 启用功能

```bash
ENV_MANAGEMENT_ENABLED=true
```

> **重要**：此功能需要单进程部署。详见下方约束说明。

## 使用方式

### 访问

1. 登录管理面板
2. 导航到"设置"或"系统配置"
3. 查看和编辑环境变量

### 变量分类

| 分类 | 行为 |
|------|------|
| 必填 | 应用正常运行必须设置 |
| 敏感 | 值已脱敏，更新需确认 |
| 可编辑 | 可通过界面修改 |
| 只读 | 仅显示，不可编辑 |

### 修改流程

1. 编辑变量值
2. 敏感变量需确认修改
3. 点击保存
4. **重启服务**使修改生效

## 约束条件

### 单进程要求

此功能使用 `threading.Lock` 进行文件访问同步：

```python
# 仅在单进程内有效
with self._lock:
    # 写入 .env 文件
```

这意味着：
- **不要**使用 `--workers > 1`
- **不要**扩展为多实例
- **不要**在 Kubernetes 中使用多副本

### 需要重启

环境变量在启动时加载。修改后需要：

```bash
# Docker
docker-compose restart backend

# 本地开发
# 停止并重启 uvicorn
```

### 文件权限

后端进程需要 `.env` 的写入权限：

```bash
# Docker - 确保卷可写
volumes:
  - ./.env:/app/.env
```

## 生产环境建议

### 方案 1：禁用功能

适用于多进程或多实例部署：

```bash
ENV_MANAGEMENT_ENABLED=false
```

### 方案 2：外部配置管理

使用专用工具：
- AWS Secrets Manager
- HashiCorp Vault
- Kubernetes ConfigMaps/Secrets
- Docker Secrets

### 方案 3：单实例

如必须使用此功能：
- 运行单个后端实例
- 使用 `--workers=1`
- 接受扩展限制

## 安全考虑

### 访问控制

- 需要管理员认证
- 操作有日志记录
- 敏感值已脱敏

### 敏感变量

以下变量标记为敏感：
- API 密钥（`*_API_KEY`）
- 密钥（`*_SECRET*`）
- 密码（`*_PASSWORD`）
- Token

### 审计追踪

变更记录包括：
- 时间戳
- 修改的变量
- 旧值（敏感变量已脱敏）
- 新值（敏感变量已脱敏）

## 故障排查

### 修改未生效

- 确认服务已重启
- 检查文件权限
- 验证变量名是否正确

### 权限被拒绝

- 检查 .env 文件所有权
- 验证 Docker 卷挂载
- 确保有写入权限

### 并发访问问题

如遇到锁相关错误：
- 确保单进程部署
- 检查是否有多个后端实例
- 检查 Docker Compose 副本设置

## API 参考

### 获取变量

```
GET /api/admin/env
Authorization: Bearer <token>
```

### 更新变量

```
PUT /api/admin/env
Authorization: Bearer <token>
Content-Type: application/json

{
  "updates": [
    {"name": "LOG_LEVEL", "action": "set", "value": "DEBUG"},
    {"name": "OLD_VAR", "action": "unset"}
  ]
}
```

响应中包含是否需要重启：

```json
{
  "success": true,
  "restart_required": true
}
```
