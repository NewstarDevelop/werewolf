# Environment Variable Management

Werewolf AI includes an admin feature to edit environment variables through the web interface.

## Overview

When enabled, administrators can:
- View all environment variables
- Edit non-sensitive values
- Update configuration without server access
- See which variables are required

## Enabling the Feature

```bash
ENV_MANAGEMENT_ENABLED=true
```

> **Important**: This feature requires single-process deployment. See constraints below.

## Using the Feature

### Access

1. Login to admin panel
2. Navigate to "Settings" or "Configuration"
3. View and edit environment variables

### Variable Categories

| Category | Behavior |
|----------|----------|
| Required | Must be set for the application to work |
| Sensitive | Values are masked, require confirmation to update |
| Editable | Can be modified through the interface |
| Read-only | Displayed but cannot be edited |

### Making Changes

1. Edit the variable value
2. For sensitive variables, confirm the change
3. Click Save
4. **Restart the service** for changes to take effect

## Constraints

### Single Process Requirement

The feature uses `threading.Lock` for file access synchronization:

```python
# This only works within a single process
with self._lock:
    # Write to .env file
```

This means:
- **Do NOT** use with `--workers > 1`
- **Do NOT** scale to multiple instances
- **Do NOT** use in Kubernetes with multiple replicas

### Restart Required

Environment variables are loaded at startup. Changes require:

```bash
# Docker
docker-compose restart backend

# Local
# Stop and restart uvicorn
```

### File Permissions

The backend process needs write access to `.env`:

```bash
# Docker - ensure volume is writable
volumes:
  - ./.env:/app/.env
```

## Production Recommendations

### Option 1: Disable Feature

For multi-process or multi-instance deployments:

```bash
ENV_MANAGEMENT_ENABLED=false
```

### Option 2: External Config Management

Use dedicated tools:
- AWS Secrets Manager
- HashiCorp Vault
- Kubernetes ConfigMaps/Secrets
- Docker Secrets

### Option 3: Single Instance

If you must use this feature:
- Run single backend instance
- Use `--workers=1`
- Accept the scaling limitation

## Security Considerations

### Access Control

- Requires admin authentication
- Actions are logged
- Sensitive values masked

### Sensitive Variables

The following are marked sensitive:
- API keys (`*_API_KEY`)
- Secrets (`*_SECRET*`)
- Passwords (`*_PASSWORD`)
- Tokens

### Audit Trail

Changes are logged with:
- Timestamp
- Changed variable
- Previous value (masked for sensitive)
- New value (masked for sensitive)

## Troubleshooting

### Changes Not Taking Effect

- Confirm service was restarted
- Check file permissions
- Verify variable name is correct

### Permission Denied

- Check .env file ownership
- Verify Docker volume mount
- Ensure write permissions

### Concurrent Access Issues

If you see lock-related errors:
- Ensure single process deployment
- Check for multiple backend instances
- Review Docker Compose replicas setting

## API Reference

### Get Variables

```
GET /api/admin/env
Authorization: Bearer <token>
```

### Update Variables

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

Response includes restart requirement:

```json
{
  "success": true,
  "restart_required": true
}
```
