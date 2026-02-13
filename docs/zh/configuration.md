# 配置参考

本文档涵盖 Werewolf AI 支持的所有环境变量。

## 快速参考

### 最低必要配置

```bash
JWT_SECRET_KEY=<随机32位字符串>
OPENAI_API_KEY=<你的API密钥>
```

### 测试最低配置

```bash
JWT_SECRET_KEY=test-key
LLM_USE_MOCK=true
```

## 配置分组

### 1. 核心配置

| 变量 | 必填 | 默认值 | 说明 |
|------|------|--------|------|
| `JWT_SECRET_KEY` | 是 | - | JWT 签名密钥。可用 `openssl rand -hex 32` 生成 |
| `OPENAI_API_KEY` | 推荐 | - | 默认 OpenAI API 密钥 |
| `OPENAI_BASE_URL` | 否 | OpenAI 官方 | 自定义 API 端点 |

### 2. LLM 模型设置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `LLM_MODEL` | `gpt-4o-mini` | 默认模型 |
| `LLM_MAX_RETRIES` | `2` | API 重试次数 |
| `LLM_USE_MOCK` | `false` | 使用模拟响应（不调用 API） |

### 3. 应用设置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEBUG` | `false` | 启用调试模式 |
| `LOG_LEVEL` | `INFO` | 日志级别：DEBUG, INFO, WARNING, ERROR |
| `DATA_DIR` | `data` | 数据存储目录 |

### 4. 管理功能

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ENV_MANAGEMENT_ENABLED` | `false` | 允许通过管理面板编辑 .env |

> **注意**：启用此功能需要单进程部署。修改后需重启服务。

### 5. 安全设置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ADMIN_PASSWORD` | - | 管理面板登录密码 |
| `ADMIN_KEY` | - | 备选管理员认证密钥 |
| `ADMIN_KEY_ENABLED` | `false` | 启用管理员密钥认证 |
| `DEBUG_MODE` | `false` | 启用调试端点 |
| `TRUSTED_PROXIES` | - | 可信代理 IP/CIDR，逗号分隔 |
| `CORS_ORIGINS` | - | CORS 允许的来源 |

> **警告**：设置 `CORS_ORIGINS=*` 会禁用 Cookie 认证。

### 6. JWT 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `JWT_ALGORITHM` | `HS256` | JWT 签名算法 |
| `JWT_EXPIRE_MINUTES` | `10080` | Token 过期时间（默认 7 天） |

### 7. OAuth（linux.do）

| 变量 | 说明 |
|------|------|
| `LINUXDO_CLIENT_ID` | OAuth 应用客户端 ID |
| `LINUXDO_CLIENT_SECRET` | OAuth 应用客户端密钥 |
| `LINUXDO_REDIRECT_URI` | 回调 URL |
| `LINUXDO_AUTHORIZE_URL` | 授权端点 |
| `LINUXDO_TOKEN_URL` | Token 端点 |
| `LINUXDO_USERINFO_URL` | 用户信息端点 |
| `LINUXDO_SCOPES` | OAuth 权限范围 |

### 8. 对局分析

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `ANALYSIS_PROVIDER` | - | 分析专用 Provider |
| `ANALYSIS_MODEL` | `gpt-4o` | 分析模型 |
| `ANALYSIS_MODE` | `comprehensive` | 模式：comprehensive, quick, custom |
| `ANALYSIS_LANGUAGE` | `auto` | 语言：auto, zh, en |
| `ANALYSIS_CACHE_ENABLED` | `true` | 缓存分析结果 |
| `ANALYSIS_MAX_TOKENS` | `4000` | 最大响应 Token 数 |
| `ANALYSIS_TEMPERATURE` | `0.7` | 模型温度 |

### 9. 多 Provider 配置

每个 Provider 支持以下变量（将 `{PREFIX}` 替换为 Provider 名称）：

| 变量 | 说明 |
|------|------|
| `{PREFIX}_API_KEY` | API 密钥 |
| `{PREFIX}_BASE_URL` | API 端点 |
| `{PREFIX}_MODEL` | 默认模型 |
| `{PREFIX}_MAX_RETRIES` | 重试次数 |
| `{PREFIX}_TEMPERATURE` | 模型温度 |
| `{PREFIX}_MAX_TOKENS` | 最大 Token 数 |

支持的前缀：`OPENAI`, `DEEPSEEK`, `ANTHROPIC`, `MOONSHOT`, `QWEN`, `GLM`, `DOUBAO`, `MINIMAX`

### 10. 玩家级别 AI

详见 [玩家级别 AI 配置](per-player-ai.md)。

| 变量 | 说明 |
|------|------|
| `AI_PLAYER_{N}_PROVIDER` | 将座位 N 映射到 Provider |
| `AI_PLAYER_{N}_API_KEY` | 座位 N 的专用密钥 |
| `AI_PLAYER_MAPPING` | JSON 批量映射 |

### 11. 速率限制

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEFAULT_REQUESTS_PER_MINUTE` | `60` | 默认速率限制 |
| `DEFAULT_MAX_CONCURRENCY` | `5` | 最大并发请求数 |
| `DEFAULT_BURST` | `3` | 突发允许量 |
| `LLM_MAX_WAIT_SECONDS` | `8` | LLM 最大等待时间 |
| `LLM_PER_GAME_MIN_INTERVAL` | `0.5` | 请求最小间隔 |
| `LLM_PER_GAME_MAX_CONCURRENCY` | `2` | 每局最大并发数 |

### 12. Redis 配置

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REDIS_URL` | - | Redis 连接 URL |

格式：`redis://[:password]@host:port/db`

> **注意**：Redis 是可选的。没有 Redis 时，通知仅在单实例内工作。

### 13. 前端（Vite）

| 变量 | 说明 |
|------|------|
| `VITE_API_URL` | 后端 API 地址 |
| `VITE_API_BASE_URL` | 备选 API 地址 |
| `VITE_SENTRY_DSN` | Sentry 错误追踪 |
| `VITE_SENTRY_ENV` | Sentry 环境 |
| `VITE_SENTRY_TRACES_SAMPLE_RATE` | 性能采样率 |
| `VITE_SENTRY_ENABLE_REPLAY` | 会话回放 |

### 14. 数据库

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `RUN_DB_MIGRATIONS` | `true` | 启动时自动执行迁移 |

## 配置示例

### 开发环境

```bash
JWT_SECRET_KEY=dev-key-not-for-production
DEBUG=true
LOG_LEVEL=DEBUG
LLM_USE_MOCK=true
CORS_ORIGINS=http://localhost:5173
```

### 生产环境

```bash
JWT_SECRET_KEY=<生成安全密钥>
OPENAI_API_KEY=sk-xxx
DEBUG=false
LOG_LEVEL=WARNING
CORS_ORIGINS=https://your-domain.com
```

### 多 Provider 对战

```bash
JWT_SECRET_KEY=xxx
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
AI_PLAYER_MAPPING={"2":"openai","3":"deepseek","4":"anthropic"}
```
