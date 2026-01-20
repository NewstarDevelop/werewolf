# Local Development Guide

## Prerequisites

- Python 3.10+
- Node.js 18+
- Git

## Backend Setup

### 1. Create Virtual Environment

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Environment

```bash
# From project root
cp .env.example .env
```

Edit `.env`:

```bash
JWT_SECRET_KEY=dev-secret-key-for-local-development
OPENAI_API_KEY=sk-your-key-here
DEBUG=true
LOG_LEVEL=DEBUG
```

### 4. Initialize Database

```bash
# Run migrations
alembic upgrade head
```

### 5. Start Backend

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Backend available at http://localhost:8000

## Frontend Setup

### 1. Install Dependencies

```bash
cd frontend
npm install
```

### 2. Configure API URL (Optional)

For direct backend connection without Docker:

```bash
# Create .env.local
echo "VITE_API_URL=http://localhost:8000" > .env.local
```

### 3. Start Development Server

```bash
npm run dev
```

Frontend available at http://localhost:5173

## Development Workflow

### Running Both Services

Open two terminals:

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

### Code Quality

**Backend:**
```bash
# Format code
black app/

# Type checking
mypy app/

# Linting
ruff check app/
```

**Frontend:**
```bash
# Type checking
npm run typecheck

# Linting
npm run lint

# Format
npx prettier --write src/
```

### Testing

**Backend:**
```bash
cd backend
pytest

# With coverage
pytest --cov=app
```

**Frontend:**
```bash
cd frontend
npm run test

# With UI
npm run test:ui

# With coverage
npm run test:coverage
```

### Database Migrations

Create a new migration:

```bash
cd backend
alembic revision --autogenerate -m "Add new table"
```

Apply migrations:

```bash
alembic upgrade head
```

Rollback:

```bash
alembic downgrade -1
```

## Project Structure

### Backend Key Files

| File | Purpose |
|------|---------|
| `app/main.py` | FastAPI application entry |
| `app/core/config.py` | Configuration loading |
| `app/api/api.py` | API router registration |
| `app/services/game/` | Game logic |
| `app/services/llm/` | LLM providers |

### Frontend Key Files

| File | Purpose |
|------|---------|
| `src/App.tsx` | Application entry |
| `src/pages/` | Page components |
| `src/components/` | Reusable components |
| `src/hooks/` | Custom React hooks |
| `src/lib/` | Utilities |

## Debugging

### Backend Debugging

Using VS Code:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "FastAPI",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["app.main:app", "--reload"],
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

### Frontend Debugging

React DevTools and browser developer tools work out of the box.

For VS Code debugging with Chrome:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "type": "chrome",
      "request": "launch",
      "name": "React",
      "url": "http://localhost:5173",
      "webRoot": "${workspaceFolder}/frontend/src"
    }
  ]
}
```

## Mock Mode

For development without LLM API costs:

```bash
LLM_USE_MOCK=true
```

AI players will respond with predefined messages instead of calling the API.

## Common Issues

### CORS Errors

Ensure backend CORS is configured:

```bash
CORS_ORIGINS=http://localhost:5173
```

### WebSocket Connection Failed

- Check backend is running on correct port
- Verify no proxy is blocking WebSocket

### Database Locked

SQLite may lock on concurrent access. Solutions:
- Restart backend
- Use PostgreSQL for heavy development
