# Troubleshooting Guide

Common issues and solutions for Werewolf AI.

## Installation Issues

### Docker Build Fails

**Symptom**: `docker-compose build` fails

**Solutions**:
1. Check Docker is running
2. Ensure sufficient disk space
3. Try with `--no-cache`:
   ```bash
   docker-compose build --no-cache
   ```

### Container Exits Immediately

**Symptom**: Container starts then stops

**Check logs**:
```bash
docker-compose logs backend
```

**Common causes**:
- Missing `JWT_SECRET_KEY`
- Invalid database path
- Port already in use

## Configuration Issues

### Missing Required Variables

**Symptom**: Backend fails to start with config error

**Solution**: Check all required variables are set:
```bash
# Minimum required
JWT_SECRET_KEY=xxx
```

### CORS Errors

**Symptom**: Browser console shows CORS errors

**Solution**:
```bash
# Set to your frontend domain
CORS_ORIGINS=http://localhost:5173
```

> Do not use `*` - it disables cookie authentication.

### Invalid API Key

**Symptom**: AI responses fail with 401/403

**Solution**:
1. Verify key is correct
2. Check key has required permissions
3. Ensure no extra whitespace in .env

## Authentication Issues

### Login Returns 401

**Causes**:
1. `JWT_SECRET_KEY` not set
2. Token expired
3. Invalid credentials

**Solution**:
```bash
# Verify JWT_SECRET_KEY is set
grep JWT_SECRET_KEY .env

# Check token expiration
JWT_EXPIRE_MINUTES=10080
```

### OAuth Redirect Fails

**Symptom**: OAuth login redirects to error

**Check**:
1. `LINUXDO_REDIRECT_URI` matches exactly
2. Client ID/Secret are correct
3. OAuth app is active

### Admin Panel Access Denied

**Solution**:
```bash
# Set admin password
ADMIN_PASSWORD=your-password
```

## Game Issues

### AI Not Responding

**Causes**:
1. Invalid API key
2. Rate limit exceeded
3. Provider outage

**Debug**:
```bash
# Enable debug logging
LOG_LEVEL=DEBUG

# Check logs
docker-compose logs -f backend | grep LLM
```

### WebSocket Disconnects

**Causes**:
1. Network issues
2. Proxy timeout
3. Server restart

**Solutions**:
1. Check network stability
2. Increase proxy timeout
3. Frontend auto-reconnects

### Game State Lost

**Cause**: Server restart (game state is in-memory)

**Prevention**:
- Avoid restarts during active games
- Plan maintenance during low-activity periods

## Performance Issues

### Slow AI Responses

**Causes**:
1. Provider latency
2. Rate limiting
3. Large context

**Solutions**:
```bash
# Increase timeout
LLM_MAX_WAIT_SECONDS=15

# Reduce concurrent requests
LLM_PER_GAME_MAX_CONCURRENCY=1
```

### High Memory Usage

**Causes**:
1. Many active games
2. Memory leak
3. Large logs

**Solutions**:
1. Restart container
2. Limit concurrent games
3. Check for runaway processes

### Slow Database

**Solutions**:
1. Switch to PostgreSQL
2. Add database indexes
3. Archive old data

## Frontend Issues

### Blank Page

**Check**:
1. Browser console for errors
2. Network tab for failed requests
3. Frontend container logs

### Styles Not Loading

**Cause**: Build issue

**Solution**:
```bash
# Rebuild frontend
docker-compose build frontend --no-cache
docker-compose up -d frontend
```

### Language Not Switching

**Cause**: i18n configuration

**Solution**:
1. Check translation files exist
2. Clear browser cache
3. Verify language detection settings

## Database Issues

### Migration Failed

**Symptom**: Backend won't start, migration error in logs

**Solution**:
```bash
# Check migration status
docker-compose exec backend alembic current

# Try manual migration
docker-compose exec backend alembic upgrade head

# If corrupt, reset (loses data)
rm data/werewolf.db
docker-compose restart backend
```

### Database Locked

**Cause**: Concurrent access to SQLite

**Solution**:
1. Restart backend
2. Check for multiple processes
3. Consider PostgreSQL

## Docker Issues

### Volume Permission Denied

**Cause**: Incorrect file ownership

**Solution**:
```bash
# Fix permissions
chmod -R 777 data/
```

### Container Network Issues

**Symptom**: Services can't communicate

**Solution**:
```bash
# Recreate network
docker-compose down
docker network prune
docker-compose up -d
```

## Getting Help

### Collect Debug Info

```bash
# System info
docker version
docker-compose version

# Container status
docker-compose ps

# Recent logs
docker-compose logs --tail=500 > debug.log

# Configuration (hide secrets)
grep -v "KEY\|SECRET\|PASSWORD" .env > config.txt
```

### Report Issues

1. Check existing issues on GitHub
2. Include debug info
3. Describe steps to reproduce
4. Note expected vs actual behavior
