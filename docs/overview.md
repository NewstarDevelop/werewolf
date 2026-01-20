# Project Overview

## What is Werewolf AI?

Werewolf AI is an online Werewolf (Mafia) game that supports mixed gameplay between human players and AI players. The AI players are powered by Large Language Models (LLMs), enabling them to:

- Engage in natural language conversations
- Perform logical reasoning and deduction
- Make strategic decisions
- Adapt to different game situations

## Core Features

### Multi-Model Support

The project supports 9+ LLM providers:

| Provider | Models |
|----------|--------|
| OpenAI | GPT-4, GPT-4o, GPT-4o-mini |
| DeepSeek | deepseek-chat |
| Anthropic | Claude 3 Haiku/Sonnet/Opus |
| Moonshot | moonshot-v1-8k/32k |
| Qwen | qwen-turbo/plus/max |
| GLM | glm-4-flash/air/plus |
| Doubao | doubao-pro-4k/32k |
| MiniMax | abab6.5s-chat |
| Custom | Any OpenAI-compatible API |

### Per-Player AI Configuration

A unique feature that allows configuring different AI models for different game seats:

- Seat 2 uses GPT-4o for advanced reasoning
- Seat 3 uses DeepSeek for cost-effective play
- Seat 4 uses Claude for creative responses

This creates diverse and unpredictable gameplay dynamics.

### Real-time Gameplay

- WebSocket-based state synchronization
- Instant message delivery
- Live game status updates
- Responsive UI with React Query

### Internationalization

- Chinese and English interface
- i18next-based translation system
- Language auto-detection

### Game Analysis

Post-game AI analysis provides:

- Player performance evaluation
- Strategy assessment
- Key moment analysis
- Improvement suggestions

## Game Roles

| Role | Team | Ability |
|------|------|---------|
| Werewolf | Evil | Can kill one player each night |
| Villager | Good | No special ability, votes to find werewolves |
| Seer | Good | Can check one player's identity each night |
| Witch | Good | Has one healing potion and one poison |
| Hunter | Good | Can shoot one player upon death |

## Game Flow

1. **Role Assignment** - System randomly assigns roles
2. **Night Phase** - Werewolves kill, special roles act
3. **Day Phase** - Discussion and voting
4. **Victory Check** - Game ends when one team wins

## Architecture Summary

```
Frontend (React)     <-->    Backend (FastAPI)
     |                              |
     +-- WebSocket -----------------+
     |                              |
     +-- REST API ------------------+
                                    |
                              LLM Providers
```

See [Architecture](architecture.md) for detailed system design.
