# 认证配置

Werewolf AI 支持多种认证方式以适应不同使用场景。

## 认证方式

| 方式 | 使用场景 | 配置 |
|------|----------|------|
| JWT Token | 玩家会话 | `JWT_SECRET_KEY` |
| OAuth SSO | linux.do 登录 | `LINUXDO_*` 变量 |
| 管理员密码 | 管理面板 | `ADMIN_PASSWORD` |
| 管理员密钥 | API 认证 | `ADMIN_KEY` |

## JWT 配置

### 必要设置

```bash
# 可用以下命令生成：openssl rand -hex 32
JWT_SECRET_KEY=至少32位的密钥字符串
```

### 可选设置

```bash
JWT_ALGORITHM=HS256        # 签名算法
JWT_EXPIRE_MINUTES=10080   # 默认 7 天
```

### Token 用途

JWT Token 用于：
- 玩家身份验证
- WebSocket 连接
- API 请求
- 会话管理

## OAuth（linux.do）

Werewolf AI 支持通过 linux.do 进行 OAuth 单点登录。

### 配置步骤

1. 在 linux.do 开发者控制台**创建 OAuth 应用**
2. **配置回调 URI** 与你的部署地址匹配
3. **设置环境变量**

### 配置

```bash
LINUXDO_CLIENT_ID=你的客户端ID
LINUXDO_CLIENT_SECRET=你的客户端密钥
LINUXDO_REDIRECT_URI=https://your-domain.com/api/auth/callback/linuxdo
```

### OAuth 端点（默认值）

通常无需修改：

```bash
LINUXDO_AUTHORIZE_URL=https://connect.linux.do/oauth2/authorize
LINUXDO_TOKEN_URL=https://connect.linux.do/oauth2/token
LINUXDO_USERINFO_URL=https://connect.linux.do/api/user
LINUXDO_SCOPES=user
```

### OAuth 流程

```
用户 -> 前端 -> 后端 -> linux.do -> 回调 -> JWT Token -> 用户
```

1. 用户点击"通过 linux.do 登录"
2. 前端重定向到后端 OAuth 端点
3. 后端重定向到 linux.do 授权页
4. 用户授权应用
5. linux.do 重定向到回调 URL
6. 后端用授权码交换 Token
7. 后端获取用户信息
8. 后端签发 JWT Token
9. 用户登录成功

## 管理员认证

### 管理员密码（推荐）

管理面板的简单密码认证：

```bash
ADMIN_PASSWORD=你的安全密码
```

使用方式：
- 通过管理面板登录页输入
- 密码经过哈希校验

### 管理员密钥（旧版）

API 密钥认证：

```bash
ADMIN_KEY=你的API密钥
ADMIN_KEY_ENABLED=true
```

使用方式：
- 包含在请求头中
- 主要用于 API 自动化

> **注意**：管理员密钥默认禁用。Web 访问请使用管理员密码。

## 安全设置

### CORS 配置

```bash
# 生产环境 - 指定你的域名
CORS_ORIGINS=https://your-domain.com

# 多个域名
CORS_ORIGINS=https://app.example.com,https://www.example.com

# 开发环境
CORS_ORIGINS=http://localhost:5173
```

> **警告**：使用 `*` 会禁用 Cookie 认证。

### 可信代理

用于反向代理后的正确客户端 IP 检测：

```bash
TRUSTED_PROXIES=127.0.0.1,10.0.0.0/8
```

### 调试模式

```bash
# 启用调试端点（不要在生产环境使用）
DEBUG_MODE=false
```

## Token 安全

### 最佳实践

1. **定期轮换 JWT_SECRET_KEY**
2. **生产环境使用 HTTPS**
3. 根据安全需求**设置合适的过期时间**
4. **不要在日志或 URL 中暴露 Token**

### Token 刷新

Token 在 `JWT_EXPIRE_MINUTES` 后过期。过期后用户需重新认证。

## 故障排查

### OAuth 重定向不匹配

- 确认 `LINUXDO_REDIRECT_URI` 与控制台配置完全一致
- 包含协议（https://）
- 包含正确的路径

### 登录时 CORS 错误

- 检查 `CORS_ORIGINS` 包含你的前端域名
- 确保没有尾部斜杠
- 确认协议匹配（http vs https）

### 管理员登录失败

- 确认 `ADMIN_PASSWORD` 已设置
- 检查密码中是否有特殊字符
- 确保 .env 中没有尾部空白
