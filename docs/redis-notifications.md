# Redis Notifications

Werewolf AI uses Redis for cross-instance notification broadcasting.

## Overview

Redis enables:
- Real-time notifications across instances
- Pub/sub messaging
- Session state sharing (future)

> **Note**: Redis is optional. The system works without it in single-instance mode.

## Configuration

```bash
REDIS_URL=redis://localhost:6379/0
```

### URL Format

```
redis://[:password]@host:port/db
```

Examples:
```bash
# Local without password
REDIS_URL=redis://localhost:6379/0

# With password
REDIS_URL=redis://:mypassword@localhost:6379/0

# Remote server
REDIS_URL=redis://:pass@redis.example.com:6379/0
```

## Fallback Behavior

Without Redis configuration:

| Feature | Behavior |
|---------|----------|
| Notifications | Work only within single instance |
| Game state | Remains in-memory (no change) |
| WebSocket | Still works normally |

The system logs a warning but continues to function.

## Use Cases

### Notifications

When Redis is available:
- Admin broadcasts reach all instances
- System alerts propagate everywhere
- User notifications are consistent

### Future: State Sharing

Redis could enable:
- Multi-instance game state
- Horizontal scaling
- Session replication

> **Current Status**: Game state is still in-memory. Redis is only used for notifications.

## Docker Compose Setup

To add Redis to your deployment:

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

## Health Checks

The backend checks Redis connectivity on startup:
- Success: Redis notifications enabled
- Failure: Falls back to single-instance mode

## Performance

Redis adds minimal overhead:
- Pub/sub is lightweight
- No game-critical data in Redis
- Graceful degradation if Redis fails

## Troubleshooting

### Connection Refused

- Verify Redis is running
- Check network connectivity
- Confirm port is accessible

```bash
# Test connection
redis-cli -h localhost -p 6379 ping
```

### Authentication Failed

- Check password in REDIS_URL
- Verify Redis AUTH configuration
- Ensure no special characters need escaping

### Notifications Not Working

- Check REDIS_URL is set
- Verify backend logs for Redis connection
- Test pub/sub manually:

```bash
# Terminal 1: Subscribe
redis-cli subscribe notifications

# Terminal 2: Publish
redis-cli publish notifications "test"
```

## Scaling Considerations

Redis alone does not enable horizontal scaling of the backend:

| Component | Scaling Status |
|-----------|----------------|
| Notifications | Ready with Redis |
| Game State | Requires architecture change |
| WebSocket | Requires sticky sessions |

To fully scale, game state must be externalized to Redis or a database.
