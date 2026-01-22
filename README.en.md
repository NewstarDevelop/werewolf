# Werewolf AI

<p align="center">
  <strong>AI-Powered Online Werewolf Game - Human vs AI Mixed Gameplay</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/docker-ready-blue?style=flat-square" alt="Docker">
  <img src="https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square" alt="FastAPI">
  <img src="https://img.shields.io/badge/frontend-React_18-61DAFB?style=flat-square" alt="React">
  <img src="https://img.shields.io/badge/lang-TypeScript-3178C6?style=flat-square" alt="TypeScript">
</p>

---

## Overview

Werewolf AI is an innovative online Werewolf (Mafia) game. AI players are powered by Large Language Models, capable of logical reasoning, strategic decision-making, and natural language interaction.

**Key Features**:

- **Multi-Model Support** - 9+ LLM providers including OpenAI, DeepSeek, Gemini, Anthropic
- **Per-Player AI** - Configure different AI models for different seats for diverse gameplay
- **Real-time Gameplay** - WebSocket-based real-time game state synchronization
- **Internationalization** - Bilingual interface (Chinese/English)
- **OAuth Login** - Supports linux.do SSO
- **Docker Deployment** - One-click start, ready to use

## Quick Start

### Docker Deployment (Recommended)

```bash
# 1. Clone and configure
git clone https://github.com/NewstarDevelo/werewolf.git
cd werewolf && cp .env.example .env

# 2. Edit .env, set JWT_SECRET_KEY and OPENAI_API_KEY
nano .env

# 3. Start (using deploy script, auto-handles permissions)
chmod +x deploy.sh && ./deploy.sh

# Or manual start (first time requires data directory permissions)
# sudo chown -R 1000:1000 ./data && docker compose up -d
```

After starting:
- Frontend: http://localhost:8081
- API: http://localhost:8082
- Docs: http://localhost:8082/docs

### Local Development

See [Development Guide](docs/development.md).

## Tech Stack

| Layer | Technology |
|-------|------------|
| Backend | FastAPI, SQLAlchemy, Alembic, JWT |
| Frontend | React 18, TypeScript, Vite, TailwindCSS, shadcn/ui |
| AI | OpenAI API (multi-provider compatible) |
| Deployment | Docker Compose |

## Documentation

| Document | Description |
|----------|-------------|
| [Overview](docs/overview.md) | Business positioning and core capabilities |
| [Architecture](docs/architecture.md) | Technical architecture and data flow |
| [Deployment](docs/deployment.md) | Docker Compose deployment guide |
| [Development](docs/development.md) | Local development setup |
| [Configuration](docs/configuration.md) | Complete environment variable reference |
| [LLM Providers](docs/llm-providers.md) | Multi-provider configuration |
| [Per-Player AI](docs/per-player-ai.md) | Seat-level AI configuration |
| [Authentication](docs/auth.md) | JWT and OAuth configuration |
| [Troubleshooting](docs/troubleshooting.md) | Common issues and solutions |

## Runtime Constraints

> **Important**: Game state is stored in memory. Must run in single-instance, single-worker mode.
> Externalize game state to Redis or database before scaling.

- Single process: `uvicorn app.main:app --workers=1`
- Service restart required after environment variable changes
- Redis is only for notifications, not core game functionality

## License

[MIT License](LICENSE)

## Contributing

Issues and Pull Requests are welcome.

---

[Chinese](README.md) | [Full Documentation](docs/index.md)
