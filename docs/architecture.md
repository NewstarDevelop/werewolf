# System Architecture

## Overview

Werewolf AI uses a modern web application architecture with real-time capabilities.

```
+------------------+       +------------------+       +------------------+
|    Frontend      |       |     Backend      |       |   LLM Providers  |
|    (React)       | <---> |    (FastAPI)     | <---> |  (OpenAI, etc.)  |
+------------------+       +------------------+       +------------------+
        |                          |
        |                          |
        v                          v
   Browser Storage           SQLite/PostgreSQL
                                   |
                                   v
                              Redis (optional)
```

## Components

### Frontend

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | React 18.3+ | UI rendering |
| Language | TypeScript 5.0+ | Type safety |
| Build | Vite 5.0+ | Fast development |
| Styling | TailwindCSS | Utility-first CSS |
| Components | shadcn/ui | Consistent design |
| State | React Query | Server state management |
| i18n | i18next | Internationalization |
| Real-time | WebSocket | Live game updates |

### Backend

| Component | Technology | Purpose |
|-----------|------------|---------|
| Framework | FastAPI 0.104+ | API server |
| ORM | SQLAlchemy 2.0+ | Database abstraction |
| Migration | Alembic | Schema versioning |
| Auth | JWT + OAuth2 | Authentication |
| AI | OpenAI SDK | LLM integration |
| Cache | Redis (optional) | Notifications |

## Data Flow

### Game State

```
Player Action --> WebSocket --> GameStore (Memory) --> Broadcast
                                     |
                                     v
                              Database (Persistent)
```

> **Warning**: Game state is stored in memory (GameStore). This requires single-instance deployment.

### Authentication Flow

```
User --> OAuth (linux.do) --> Backend --> JWT Token --> Client
     --> Password Login    --> Backend --> JWT Token --> Client
```

### LLM Request Flow

```
Game Event --> LLM Service --> Provider Selection --> API Call --> Response
                   |
                   v
           Rate Limiter --> Retry Logic --> Error Handling
```

## Directory Structure

```
werewolf/
├── backend/
│   ├── app/
│   │   ├── api/          # REST endpoints
│   │   ├── core/         # Configuration, security
│   │   ├── models/       # SQLAlchemy models
│   │   ├── schemas/      # Pydantic schemas
│   │   ├── services/     # Business logic
│   │   │   ├── llm/      # LLM providers
│   │   │   └── game/     # Game logic
│   │   └── i18n/         # Translations
│   ├── migrations/       # Alembic migrations
│   └── scripts/          # Utilities
│
├── frontend/
│   ├── src/
│   │   ├── components/   # UI components
│   │   ├── pages/        # Page components
│   │   ├── hooks/        # Custom hooks
│   │   ├── lib/          # Utilities
│   │   └── types/        # TypeScript types
│   └── public/           # Static assets
│
├── docs/                 # Documentation
├── data/                 # SQLite database (Docker)
└── docker-compose.yml    # Container orchestration
```

## Deployment Constraints

### Single Instance Requirement

The current architecture stores game state in memory (`GameStore` class). This means:

- **Do NOT** scale to multiple replicas
- **Do NOT** use `--workers > 1` with uvicorn
- **Do NOT** use load balancing across multiple containers

To enable horizontal scaling, game state must be externalized to Redis or a database.

### Single Process Requirement

Environment variable management uses `threading.Lock`, which only works within a single process:

- Use `uvicorn app.main:app --workers=1`
- Or disable `ENV_MANAGEMENT_ENABLED` in multi-process setups

## Network Ports

| Service | Internal Port | External Port |
|---------|--------------|---------------|
| Backend | 8000 | 8082 |
| Frontend | 80 | 8081 |

## Security Considerations

- JWT tokens for stateless authentication
- CORS configuration required for cookie-based auth
- Sensitive config masked in admin panel
- Rate limiting on LLM API calls
