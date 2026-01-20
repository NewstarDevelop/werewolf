# Configuration Reference

This document covers all environment variables supported by Werewolf AI.

## Quick Reference

### Minimum Required

```bash
JWT_SECRET_KEY=<random-32-char-string>
OPENAI_API_KEY=<your-api-key>
```

### Minimum for Testing

```bash
JWT_SECRET_KEY=test-key
LLM_USE_MOCK=true
```

## Configuration Groups

### 1. Core Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `JWT_SECRET_KEY` | Yes | - | JWT signing key. Generate with `openssl rand -hex 32` |
| `OPENAI_API_KEY` | Recommended | - | Default OpenAI API key |
| `OPENAI_BASE_URL` | No | OpenAI official | Custom API endpoint |

### 2. LLM Model Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `LLM_MODEL` | `gpt-4o-mini` | Default model |
| `LLM_MAX_RETRIES` | `2` | API retry count |
| `LLM_USE_MOCK` | `false` | Use mock responses (no API calls) |

### 3. Application Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | Log level: DEBUG, INFO, WARNING, ERROR |
| `DATA_DIR` | `data` | Data storage directory |

### 4. Admin Features

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV_MANAGEMENT_ENABLED` | `false` | Allow .env editing via admin panel |

> **Note**: Enabling this requires single-process deployment. Changes require service restart.

### 5. Security

| Variable | Default | Description |
|----------|---------|-------------|
| `ADMIN_PASSWORD` | - | Admin panel login password |
| `ADMIN_KEY` | - | Alternative admin authentication |
| `ADMIN_KEY_ENABLED` | `false` | Enable admin key auth |
| `DEBUG_MODE` | `false` | Enable debug endpoints |
| `TRUSTED_PROXIES` | - | Comma-separated proxy IPs/CIDRs |
| `CORS_ORIGINS` | - | Allowed origins for CORS |

> **Warning**: Setting `CORS_ORIGINS=*` disables cookie authentication.

### 6. JWT Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `JWT_ALGORITHM` | `HS256` | JWT signing algorithm |
| `JWT_EXPIRE_MINUTES` | `10080` | Token expiration (7 days) |

### 7. OAuth (linux.do)

| Variable | Description |
|----------|-------------|
| `LINUXDO_CLIENT_ID` | OAuth app client ID |
| `LINUXDO_CLIENT_SECRET` | OAuth app client secret |
| `LINUXDO_REDIRECT_URI` | Callback URL |
| `LINUXDO_AUTHORIZE_URL` | Authorization endpoint |
| `LINUXDO_TOKEN_URL` | Token endpoint |
| `LINUXDO_USERINFO_URL` | User info endpoint |
| `LINUXDO_SCOPES` | OAuth scopes |

### 8. Game Analysis

| Variable | Default | Description |
|----------|---------|-------------|
| `ANALYSIS_PROVIDER` | - | Separate provider for analysis |
| `ANALYSIS_MODEL` | `gpt-4o` | Analysis model |
| `ANALYSIS_MODE` | `comprehensive` | Mode: comprehensive, quick, custom |
| `ANALYSIS_LANGUAGE` | `auto` | Language: auto, zh, en |
| `ANALYSIS_CACHE_ENABLED` | `true` | Cache analysis results |
| `ANALYSIS_MAX_TOKENS` | `4000` | Max response tokens |
| `ANALYSIS_TEMPERATURE` | `0.7` | Model temperature |

### 9. Multi-Provider Configuration

Each provider supports these variables (replace `{PREFIX}` with provider name):

| Variable | Description |
|----------|-------------|
| `{PREFIX}_API_KEY` | API key |
| `{PREFIX}_BASE_URL` | API endpoint |
| `{PREFIX}_MODEL` | Default model |
| `{PREFIX}_MAX_RETRIES` | Retry count |
| `{PREFIX}_TEMPERATURE` | Model temperature |
| `{PREFIX}_MAX_TOKENS` | Max tokens |

Supported prefixes: `OPENAI`, `DEEPSEEK`, `ANTHROPIC`, `MOONSHOT`, `QWEN`, `GLM`, `DOUBAO`, `MINIMAX`

### 10. Per-Player AI

See [Per-Player AI Configuration](per-player-ai.md) for detailed guide.

| Variable | Description |
|----------|-------------|
| `AI_PLAYER_{N}_PROVIDER` | Map seat N to provider |
| `AI_PLAYER_{N}_API_KEY` | Dedicated key for seat N |
| `AI_PLAYER_MAPPING` | JSON batch mapping |

### 11. Rate Limiting

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_REQUESTS_PER_MINUTE` | `60` | Default rate limit |
| `DEFAULT_MAX_CONCURRENCY` | `5` | Max concurrent requests |
| `DEFAULT_BURST` | `3` | Burst allowance |
| `LLM_MAX_WAIT_SECONDS` | `8` | Max wait for LLM response |
| `LLM_PER_GAME_MIN_INTERVAL` | `0.5` | Min interval between requests |
| `LLM_PER_GAME_MAX_CONCURRENCY` | `2` | Max concurrent per game |

### 12. Redis Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | - | Redis connection URL |

Format: `redis://[:password]@host:port/db`

> **Note**: Redis is optional. Without it, notifications work only within single instance.

### 13. Frontend (Vite)

| Variable | Description |
|----------|-------------|
| `VITE_API_URL` | Backend API URL |
| `VITE_API_BASE_URL` | Alternative API URL |
| `VITE_SENTRY_DSN` | Sentry error tracking |
| `VITE_SENTRY_ENV` | Sentry environment |
| `VITE_SENTRY_TRACES_SAMPLE_RATE` | Performance sampling |
| `VITE_SENTRY_ENABLE_REPLAY` | Session replay |

### 14. Database

| Variable | Default | Description |
|----------|---------|-------------|
| `RUN_DB_MIGRATIONS` | `true` | Auto-run migrations on startup |

## Configuration Examples

### Development

```bash
JWT_SECRET_KEY=dev-key-not-for-production
DEBUG=true
LOG_LEVEL=DEBUG
LLM_USE_MOCK=true
CORS_ORIGINS=http://localhost:5173
```

### Production

```bash
JWT_SECRET_KEY=<generate-secure-key>
OPENAI_API_KEY=sk-xxx
DEBUG=false
LOG_LEVEL=WARNING
CORS_ORIGINS=https://your-domain.com
```

### Multi-Provider Battle

```bash
JWT_SECRET_KEY=xxx
OPENAI_API_KEY=sk-xxx
DEEPSEEK_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-ant-xxx
AI_PLAYER_MAPPING={"2":"openai","3":"deepseek","4":"anthropic"}
```
