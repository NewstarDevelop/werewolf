# Docker Deployment Guide

## Prerequisites

- Docker 20.10+
- Docker Compose 2.0+
- At least 2GB RAM
- Network access to LLM API endpoints

## Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/your-username/werewolf.git
cd werewolf
```

### 2. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and set the required values:

```bash
# Required
JWT_SECRET_KEY=your-random-secret-key-at-least-32-characters

# Choose one:
OPENAI_API_KEY=sk-your-key-here
# OR
LLM_USE_MOCK=true
```

### 3. Start Services

```bash
docker-compose up -d
```

### 4. Verify Deployment

```bash
# Check container status
docker-compose ps

# Check backend health
curl http://localhost:8082/health

# Check logs
docker-compose logs -f
```

## Service Endpoints

| Service | URL | Description |
|---------|-----|-------------|
| Frontend | http://localhost:8081 | Game interface |
| Backend API | http://localhost:8082 | REST API |
| API Docs | http://localhost:8082/docs | Swagger UI |
| ReDoc | http://localhost:8082/redoc | Alternative docs |

## Configuration

### Essential Settings

| Variable | Required | Description |
|----------|----------|-------------|
| `JWT_SECRET_KEY` | Yes | Authentication key |
| `OPENAI_API_KEY` | Recommended | Default LLM provider |
| `CORS_ORIGINS` | For production | Your domain(s) |

### Production Settings

```bash
# .env for production
JWT_SECRET_KEY=<generated-secret>
OPENAI_API_KEY=<your-key>
CORS_ORIGINS=https://your-domain.com
DEBUG=false
LOG_LEVEL=WARNING
```

> **Warning**: Do not use `CORS_ORIGINS=*` in production. This disables cookie authentication.

## Volume Mounts

| Mount | Purpose |
|-------|---------|
| `./data:/app/data` | SQLite database persistence |
| `./.env:/app/.env` | Runtime config (if ENV_MANAGEMENT_ENABLED) |

## Health Checks

The backend includes built-in health checks:

```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 30s
```

## Database Migrations

Migrations run automatically on startup. To skip:

```bash
RUN_DB_MIGRATIONS=false
```

To run manually:

```bash
docker-compose exec backend alembic upgrade head
```

## Scaling Constraints

> **Critical**: Do NOT scale beyond a single instance.

Game state is stored in memory. Scaling would cause:
- State inconsistency between instances
- Lost game sessions
- Authentication failures

For horizontal scaling, first externalize game state to Redis or PostgreSQL.

## Troubleshooting

### Container fails to start

```bash
# Check logs
docker-compose logs backend

# Common issues:
# - Missing JWT_SECRET_KEY
# - Invalid OPENAI_API_KEY
# - Database migration failure
```

### Cannot access frontend

```bash
# Verify frontend is running
docker-compose ps frontend

# Check nginx logs
docker-compose logs frontend
```

### API returns 401

- Verify `JWT_SECRET_KEY` is set
- Check `CORS_ORIGINS` includes your domain
- Ensure cookies are enabled in browser

### AI not responding

- Check `LLM_USE_MOCK` setting
- Verify API key is valid
- Check rate limiting settings

## Updating

```bash
# Pull latest changes
git pull

# Rebuild and restart
docker-compose up -d --build
```

## Backup

```bash
# Backup database
cp data/werewolf.db data/werewolf.db.backup

# Backup configuration
cp .env .env.backup
```
