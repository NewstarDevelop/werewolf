# Werewolf

[English](./README.en.md) | [简体中文](./README.md)

An AI-powered online Werewolf game supporting human and AI players. Built with FastAPI + React + Docker, providing a smooth gaming experience with intelligent AI opponents.

Live Demo: https://werewolf.newstardev.de

(Mock mode enabled, no real API key configured)

![Game Screenshot](https://img.shields.io/badge/Game-Werewolf-red)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![React](https://img.shields.io/badge/React-18.3-61dafb)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ed)

## Features

- **Complete Gameplay**: Classic roles including Werewolf, Seer, Witch, Hunter
- **AI Players**: Intelligent AI powered by OpenAI GPT with mock mode support
- **Multi-Room System**: Multiple concurrent games with room creation and joining
- **Mixed Mode**: Support for pure human, pure AI, or human+AI hybrid games
- **Real-time Chat**: In-game chat system with message logging
- **Modern UI**: Beautiful interface built with shadcn/ui, pure black theme
- **Docker Ready**: One-click deployment, out-of-the-box
- **Responsive Design**: Desktop and mobile support
- **Data Persistence**: SQLite database for room storage
- **Multi-language**: Switch between English and Chinese
- **AI Game Analysis**: View AI-generated game analysis after matches

## Game Roles

| Role | Faction | Ability |
|------|---------|---------|
| Werewolf | Werewolf Faction | Can eliminate a player each night |
| Seer | Village Faction | Can inspect a player's identity each night |
| Witch | Village Faction | Has one healing potion and one poison potion; cannot use poison on the same night after using the healing potion |
| Hunter | Village Faction | Can shoot a player when eliminated |
| Villager | Village Faction | No special abilities |

## Quick Start

### Prerequisites

- Docker and Docker Compose
- (Optional) OpenAI API Key for real AI opponents

### Start with Docker (Recommended)

```bash
git clone https://github.com/NewstarDevelop/Werewolf.git
cd Werewolf
cp .env.example .env
nano .env
```

**After filling in your API credentials:**
```bash
docker compose up
```

**Access the Game**
- Frontend: http://localhost:8081
- Backend API: http://localhost:8082
- API Documentation: http://localhost:8082/docs

### Local Development

#### Backend Development

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Frontend Development

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

### Language Switching

- Click the language switcher in the top-right corner of the game interface
- Or set `LANGUAGE=en` in the `.env` file for default English mode

## Project Structure

```
Werewolf/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── api/            # API routes
│   │   │   └── endpoints/
│   │   │       ├── game.py      # Game API
│   │   │       └── room.py      # Room API
│   │   ├── core/           # Core configuration
│   │   │   └── database.py      # Database config
│   │   ├── models/         # Data models
│   │   │   ├── game.py          # Game model
│   │   │   └── room.py          # Room model
│   │   ├── schemas/        # Pydantic schemas
│   │   └── services/       # Business logic
│   │       ├── game_engine.py   # Game engine
│   │       ├── room_manager.py  # Room manager
│   │       ├── llm.py           # AI service
│   │       └── prompts.py       # AI prompts
│   ├── data/               # Data storage
│   │   └── werewolf.db          # SQLite database
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # React components
│   │   │   ├── game/      # Game components
│   │   │   └── ui/        # UI components
│   │   ├── hooks/         # Custom hooks
│   │   ├── services/      # API services
│   │   │   ├── api.ts          # Game API
│   │   │   └── roomApi.ts      # Room API
│   │   ├── pages/         # Page components
│   │   │   ├── RoomLobby.tsx   # Room lobby
│   │   │   ├── RoomWaiting.tsx # Room waiting
│   │   │   └── GamePage.tsx    # Game page
│   │   └── utils/         # Utilities
│   │       └── player.ts       # Player ID management
│   ├── public/
│   │   └── locales/       # Translation files (zh/en)
│   ├── Dockerfile
│   └── package.json
├── docker-compose.yml
├── PROGRESS.md             # Development progress and issues
└── README.md
```

## Gameplay

### Game Modes

#### Mixed Mode (Human + AI)
1. Create a room and wait for players to join
2. Room owner clicks "Fill AI and Start"
3. System automatically fills remaining seats with AI
4. Example: 3 humans + 6 AI

### Game Flow

1. **Start Game**: Create or join a game through the room system
2. **Role Assignment**: System automatically assigns roles (3 Werewolves, 3 Villagers, Seer, Witch, Hunter)
3. **Night Phase**:
   - Werewolves choose a kill target
   - Seer inspects a player's identity
   - Witch first decides whether to use healing potion, then whether to use poison potion (cannot use poison on the same night after using healing potion)
4. **Day Phase**:
   - All players speak in turn
   - Vote to eliminate a suspicious player
5. **Victory Conditions**:
   - Village wins: Eliminate all werewolves
   - Werewolves win: Werewolf count >= Villager count, or all villagers dead (villager massacre), or all special roles dead (special role massacre)

### Controls

- **Speaking**: During day phase, enter your message in the input box and click "Confirm"
- **Voting**: During voting phase, click on a player's avatar to vote
- **Using Abilities**: During night phase, click the "Skill" button to use your role's ability

## Tech Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Pydantic**: Data validation and serialization
- **OpenAI API**: AI decision-making engine
- **Uvicorn**: ASGI server

### Frontend
- **React 18**: UI framework
- **TypeScript**: Type safety
- **Vite**: Build tool
- **TanStack Query**: Data fetching and state management
- **shadcn/ui**: UI component library
- **Tailwind CSS**: Styling framework
- **i18next**: Internationalization
- **React Router**: Routing

### Infrastructure
- **Docker & Docker Compose**: Containerized deployment
- **Nginx**: Static file serving

## Configuration

### AI Debug Panel (Thought Process)

The AI debug panel only displays content when `DEBUG_MODE=true` is configured in the `.env` file.

### Environment Variables

Create a `.env` file in the project root:

```env
# OpenAI API Configuration
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini

# Language Setting (zh: Chinese, en: English)
LANGUAGE=en

# Application Configuration
DEBUG=false
CORS_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
```

### Per-Player LLM Configuration

You can configure individual LLM providers for each AI player (seats 2-9):

```env
# Configure LLM for Player 2
AI_PLAYER_2_NAME=player2
AI_PLAYER_2_API_KEY=your_api_key
AI_PLAYER_2_BASE_URL=https://api.openai.com/v1
AI_PLAYER_2_MODEL=gpt-4o-mini
AI_PLAYER_2_TEMPERATURE=0.7
AI_PLAYER_2_MAX_TOKENS=500
```

**Supported configuration options**:
- `AI_PLAYER_X_NAME`: Player name (optional)
- `AI_PLAYER_X_API_KEY`: API key
- `AI_PLAYER_X_BASE_URL`: API base URL (optional, defaults to OpenAI)
- `AI_PLAYER_X_MODEL`: Model name (default: gpt-4o-mini)
- `AI_PLAYER_X_TEMPERATURE`: Temperature parameter (default: 0.7)
- `AI_PLAYER_X_MAX_TOKENS`: Maximum tokens (default: 500)
- `AI_PLAYER_X_MAX_RETRIES`: Maximum retry attempts (default: 2)

Where `X` is the seat number (2-9, seat 1 is the human player).

### Mock Mode

If `OPENAI_API_KEY` is not configured, the system will automatically enter Mock mode, and AI players will use preset random strategies.

### AI Game Analysis Configuration

After the game ends, you can view AI-generated game analysis reports. Configuration example:

```env
# AI Analysis Configuration (optional, defaults to OpenAI configuration if not set)
ANALYSIS_PROVIDER=openai          # Dedicated analysis provider (optional)
ANALYSIS_MODEL=gpt-4o             # Recommended: use advanced models for better analysis quality
ANALYSIS_MODE=comprehensive       # Analysis mode: comprehensive/quick/custom
ANALYSIS_LANGUAGE=auto            # Analysis language: auto/zh/en
ANALYSIS_CACHE_ENABLED=true       # Enable caching
ANALYSIS_MAX_TOKENS=4000          # Maximum tokens
ANALYSIS_TEMPERATURE=0.7          # Temperature parameter
```

**Configuration Notes**:
- If `ANALYSIS_PROVIDER` is not separately configured, it will use the default `OPENAI_API_KEY` for analysis
- Recommended to use `gpt-4o` or higher models for more detailed and accurate analysis
- `comprehensive` mode provides detailed analysis (3-5 minutes), `quick` mode provides quick summary (1-2 minutes)
- Analysis results are cached to avoid redundant computation

## API Documentation

After starting the service, visit http://localhost:8082/docs to view the complete API documentation (Swagger UI).

### Main API Endpoints

#### Room Management
- `POST /api/rooms` - Create room
- `GET /api/rooms` - Get room list (filterable by status)
- `GET /api/rooms/{room_id}` - Get room details
- `POST /api/rooms/{room_id}/join` - Join room
- `POST /api/rooms/{room_id}/ready` - Toggle ready status
- `POST /api/rooms/{room_id}/start` - Start game (supports AI fill)
- `DELETE /api/rooms/{room_id}` - Delete room (owner only)

#### Game Operations
- `POST /api/game/start` - Start new game (integrated into room system)
- `GET /api/game/{game_id}/state` - Get game state
- `POST /api/game/{game_id}/action` - Player action
- `POST /api/game/{game_id}/step` - Advance game progress

## Troubleshooting

### Docker Issues

**Problem: Container fails to start**
```bash
# View logs
docker-compose logs -f

# Restart services
docker-compose restart
```

**Problem: Port in use**
```bash
# Modify port mapping in docker-compose.yml
# For example: change 8081:80 to 8082:80
```

## Contributing

Issues and Pull Requests are welcome!

1. Fork this repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Development Progress

### Latest Version (v1.3 - 2024-12-30)

#### Security & Stability
- JWT Authentication - Complete token-based auth system
- Async LLM Calls - Non-blocking AI operations
- Game State Locking - Prevent race conditions
- Memory Management - Game limits and auto-cleanup
- Input Sanitization - Prevent prompt injection

#### Game Features
- Werewolf Self-Kill - Allow werewolves to target themselves
- Win Condition Fix - Correct werewolf victory logic
- Action Validation - Comprehensive target validation

### Completed Features
| Version | Date | Highlights |
|---------|------|------------|
| v1.3 | 2024-12-30 | Security fixes, stability, self-kill |
| v1.2 | 2024-12-30 | Multi-room, AI fill, mixed mode |
| v1.1 | 2024-12-28 | AI game analysis, caching |
| v1.0 | 2024-12-27 | Initial release, i18n support |

### Planned Features
- [ ] Add more game roles (Guardian, Witch Hunter, etc.)
- [ ] Add game replay feature
- [ ] Optimize AI strategy
- [ ] WebSocket real-time communication
- [ ] User account system

> For detailed documentation, see the [docs/](./docs/) directory:
> - [Changelog](./docs/changelog.md) - Full version history
> - [Architecture](./docs/architecture.md) - System design
> - [Security Audit](./docs/security-audit.md) - Security fix details

## License

This project is licensed under the MIT License.

---

If this project helps you, please give it a Star!
