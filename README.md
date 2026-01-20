# Werewolf AI

<p align="center">
  <strong>AI 驱动的在线狼人杀游戏 - 支持人类与 AI 混合对战</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue?style=flat-square" alt="License">
  <img src="https://img.shields.io/badge/docker-ready-blue?style=flat-square" alt="Docker">
  <img src="https://img.shields.io/badge/backend-FastAPI-009688?style=flat-square" alt="FastAPI">
  <img src="https://img.shields.io/badge/frontend-React_18-61DAFB?style=flat-square" alt="React">
  <img src="https://img.shields.io/badge/lang-TypeScript-3178C6?style=flat-square" alt="TypeScript">
</p>

---

## 项目简介

Werewolf AI 是一款创新的在线狼人杀游戏。游戏中的 AI 玩家由大语言模型驱动，能够进行逻辑推理、策略决策和自然语言互动。

**核心特性**：

- **多模型支持** - OpenAI、DeepSeek、Gemini、Anthropic 等 9+ 种 LLM Provider
- **玩家级别 AI** - 不同座位可配置不同的 AI 模型，实现多样化对战
- **实时对战** - 基于 WebSocket 的实时游戏状态同步
- **国际化** - 中文/英文双语界面
- **OAuth 登录** - 支持 linux.do 单点登录
- **Docker 部署** - 一键启动，开箱即用

## 快速开始

### Docker 部署（推荐）

```bash
# 1. 克隆并配置
git clone https://github.com/your-username/werewolf.git
cd werewolf && cp .env.example .env

# 2. 编辑 .env，设置 JWT_SECRET_KEY 和 OPENAI_API_KEY

# 3. 启动
docker-compose up -d
```

启动后访问：
- 前端：http://localhost:8081
- API：http://localhost:8082
- 文档：http://localhost:8082/docs

### 本地开发

详见 [开发指南](docs/development.md)。

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | FastAPI, SQLAlchemy, Alembic, JWT |
| 前端 | React 18, TypeScript, Vite, TailwindCSS, shadcn/ui |
| AI | OpenAI API (兼容多 Provider) |
| 部署 | Docker Compose |

## 文档导航

| 文档 | 说明 |
|------|------|
| [项目概述](docs/overview.md) | 业务定位与核心能力 |
| [系统架构](docs/architecture.md) | 技术架构与数据流 |
| [部署指南](docs/deployment.md) | Docker Compose 部署详解 |
| [开发指南](docs/development.md) | 本地开发环境搭建 |
| [配置详解](docs/configuration.md) | 环境变量完整说明 |
| [LLM Provider](docs/llm-providers.md) | 多 Provider 配置规范 |
| [玩家级别 AI](docs/per-player-ai.md) | 座位级 AI 配置 |
| [认证配置](docs/auth.md) | JWT 与 OAuth 配置 |
| [故障排查](docs/troubleshooting.md) | 常见问题与解决方案 |

## 运行限制

> **重要**：游戏状态存储在内存中，必须以单实例、单 worker 模式运行。
> 扩展部署前需先将游戏状态外置到 Redis 或数据库。

- 单进程部署：`uvicorn app.main:app --workers=1`
- 环境变量修改后需重启服务生效
- Redis 仅用于通知系统，不影响游戏核心功能

## 许可证

[MIT License](LICENSE)

## 贡献

欢迎提交 Issue 和 Pull Request。

---

[English](README.en.md) | [详细文档](docs/index.md)
