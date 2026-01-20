# Authentication Configuration

Werewolf AI supports multiple authentication methods for different use cases.

## Authentication Methods

| Method | Use Case | Configuration |
|--------|----------|---------------|
| JWT Token | Player sessions | `JWT_SECRET_KEY` |
| OAuth SSO | linux.do login | `LINUXDO_*` variables |
| Admin Password | Admin panel | `ADMIN_PASSWORD` |
| Admin Key | API authentication | `ADMIN_KEY` |

## JWT Configuration

### Required Settings

```bash
# Generate with: openssl rand -hex 32
JWT_SECRET_KEY=your-secret-key-at-least-32-characters
```

### Optional Settings

```bash
JWT_ALGORITHM=HS256        # Signing algorithm
JWT_EXPIRE_MINUTES=10080   # 7 days default
```

### Token Usage

JWT tokens are used for:
- Player authentication
- WebSocket connections
- API requests
- Session management

## OAuth (linux.do)

Werewolf AI supports OAuth SSO through linux.do.

### Setup Steps

1. **Create OAuth App** on linux.do developer console
2. **Configure Redirect URI** to match your deployment
3. **Set Environment Variables**

### Configuration

```bash
LINUXDO_CLIENT_ID=your_client_id
LINUXDO_CLIENT_SECRET=your_client_secret
LINUXDO_REDIRECT_URI=https://your-domain.com/api/auth/callback/linuxdo
```

### OAuth Endpoints (Defaults)

Usually no need to change:

```bash
LINUXDO_AUTHORIZE_URL=https://connect.linux.do/oauth2/authorize
LINUXDO_TOKEN_URL=https://connect.linux.do/oauth2/token
LINUXDO_USERINFO_URL=https://connect.linux.do/api/user
LINUXDO_SCOPES=user
```

### OAuth Flow

```
User -> Frontend -> Backend -> linux.do -> Callback -> JWT Token -> User
```

1. User clicks "Login with linux.do"
2. Frontend redirects to backend OAuth endpoint
3. Backend redirects to linux.do authorization
4. User authorizes the application
5. linux.do redirects to callback URL
6. Backend exchanges code for token
7. Backend fetches user info
8. Backend issues JWT token
9. User is logged in

## Admin Authentication

### Admin Password (Recommended)

Simple password for admin panel:

```bash
ADMIN_PASSWORD=your-secure-password
```

Usage:
- Login via admin panel login page
- Password is verified against hash

### Admin Key (Legacy)

API key authentication:

```bash
ADMIN_KEY=your-api-key
ADMIN_KEY_ENABLED=true
```

Usage:
- Include in request headers
- Primarily for API automation

> **Note**: Admin Key is disabled by default. Use Admin Password for web access.

## Security Settings

### CORS Configuration

```bash
# Production - specify your domain
CORS_ORIGINS=https://your-domain.com

# Multiple domains
CORS_ORIGINS=https://app.example.com,https://www.example.com

# Development
CORS_ORIGINS=http://localhost:5173
```

> **Warning**: Using `*` disables cookie authentication.

### Trusted Proxies

For correct client IP detection behind reverse proxies:

```bash
TRUSTED_PROXIES=127.0.0.1,10.0.0.0/8
```

### Debug Mode

```bash
# Enable debug endpoints (not for production)
DEBUG_MODE=false
```

## Token Security

### Best Practices

1. **Rotate JWT_SECRET_KEY** periodically
2. **Use HTTPS** in production
3. **Set appropriate expiration** based on security needs
4. **Never expose tokens** in logs or URLs

### Token Refresh

Tokens expire after `JWT_EXPIRE_MINUTES`. Users must re-authenticate after expiration.

## Troubleshooting

### OAuth Redirect Mismatch

- Verify `LINUXDO_REDIRECT_URI` matches console configuration exactly
- Include protocol (https://)
- Include correct path

### CORS Errors on Login

- Check `CORS_ORIGINS` includes your frontend domain
- Ensure no trailing slashes
- Verify protocol matches (http vs https)

### Admin Login Failed

- Verify `ADMIN_PASSWORD` is set
- Check for special characters in password
- Ensure no trailing whitespace in .env
