# Operations Guide

This guide covers monitoring, maintenance, and operational tasks for Werewolf AI.

## Monitoring

### Health Checks

Backend health endpoint:

```bash
curl http://localhost:8082/health
```

Response:
```json
{"status": "healthy"}
```

### Application Status

Root endpoint provides runtime info:

```bash
curl http://localhost:8082/
```

Response:
```json
{
  "status": "ok",
  "message": "Werewolf AI Game API is running",
  "version": "1.0.0",
  "llm_mode": "real"  // or "mock"
}
```

### Docker Health

```bash
# Container status
docker-compose ps

# Container health
docker inspect werewolf-backend --format='{{.State.Health.Status}}'
```

## Logging

### Log Levels

Configure via environment:

```bash
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR
```

### Viewing Logs

```bash
# Docker logs
docker-compose logs -f backend

# Last 100 lines
docker-compose logs --tail=100 backend

# Specific time range
docker-compose logs --since="2024-01-01" backend
```

### Log Format

```
2024-01-15 10:30:45 - app.main - INFO - Game logging initialized
```

Components:
- Timestamp
- Logger name
- Level
- Message

### Important Log Patterns

| Pattern | Meaning |
|---------|---------|
| `WL-001` | Room created |
| `WL-011` | Orphaned room reset |
| `LLM call` | AI request made |
| `WebSocket` | Connection events |

## Database

### SQLite Location

Default: `./data/werewolf.db`

### Backup

```bash
# Stop writes (optional but recommended)
docker-compose stop backend

# Copy database
cp data/werewolf.db data/werewolf.db.backup

# Resume
docker-compose start backend
```

### Migrations

Check status:
```bash
docker-compose exec backend alembic current
```

Apply migrations:
```bash
docker-compose exec backend alembic upgrade head
```

Rollback:
```bash
docker-compose exec backend alembic downgrade -1
```

### PostgreSQL (Alternative)

For production, consider PostgreSQL:

1. Update database URL in configuration
2. Adjust Docker Compose for PostgreSQL service
3. Run migrations

## Memory Management

### Game State

Game state is stored in memory. Monitor with:

```bash
# Container memory usage
docker stats werewolf-backend
```

### Memory Limits

Add to Docker Compose:

```yaml
backend:
  deploy:
    resources:
      limits:
        memory: 1G
```

## Security

### Rotate Secrets

Periodically rotate:
- `JWT_SECRET_KEY`
- `ADMIN_PASSWORD`
- API keys

Process:
1. Generate new secret
2. Update .env
3. Restart service
4. Active sessions will be invalidated

### Access Logs

Monitor for suspicious activity:

```bash
docker-compose logs backend | grep "401\|403"
```

## Updates

### Update Process

```bash
# Pull latest code
git pull origin main

# Rebuild containers
docker-compose build

# Restart with new version
docker-compose up -d

# Verify deployment
curl http://localhost:8082/health
```

### Rollback

```bash
# Revert to previous commit
git checkout <previous-commit>

# Rebuild and restart
docker-compose up -d --build
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs backend

# Common issues:
# - Missing required env vars
# - Database migration failure
# - Port conflict
```

### High Memory Usage

- Check for game session leaks
- Monitor active WebSocket connections
- Consider restarting periodically

### Slow Responses

- Check LLM provider status
- Review rate limiting settings
- Monitor database query times

## Maintenance Windows

### Planned Maintenance

1. Notify users of upcoming maintenance
2. Wait for active games to complete
3. Stop services
4. Perform maintenance
5. Start services
6. Verify functionality

### Emergency Maintenance

1. Stop services immediately
2. Active games will be lost (in-memory)
3. Perform emergency fixes
4. Restart services

## Scaling Notes

Current architecture limitations:
- Single instance only
- Game state in memory
- Single worker process

For horizontal scaling:
1. Externalize game state to Redis/PostgreSQL
2. Implement distributed locking
3. Use sticky sessions or shared session store
