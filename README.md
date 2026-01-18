# Werewolf AI - 狼人杀 AI 游戏

<p align="center">
  <strong>一款由 AI 驱动的在线狼人杀游戏</strong>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/FastAPI-0.104+-green.svg" alt="FastAPI">
  <img src="https://img.shields.io/badge/React-18.3+-61DAFB.svg" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-5.0+-3178C6.svg" alt="TypeScript">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

---

## 项目简介

Werewolf AI 是一款创新的在线狼人杀游戏，支持 **人类玩家与 AI 玩家混合对战**。游戏中的 AI 玩家由大语言模型（LLM）驱动，能够进行逻辑推理、策略决策和自然语言互动，提供沉浸式的游戏体验。

### 核心特性

- **AI 驱动的 NPC** - 支持 OpenAI、DeepSeek、Gemini、Anthropic 等多种 LLM Provider
- **实时对战** - 基于 WebSocket 的实时游戏状态同步
- **国际化支持** - 中文/英文双语界面
- **安全认证** - JWT + OAuth2（支持 GitHub、Google 等第三方登录）
- **游戏数据分析** - AI 辅助的对局分析和复盘
- **容器化部署** - 完整的 Docker Compose 配置

## 技术栈

### 后端 (Backend)
| 技术 | 用途 |
|------|------|
| FastAPI 0.104+ | Web 框架 |
| SQLAlchemy 2.0+ | ORM |
| SQLite / PostgreSQL | 数据库 |
| Alembic | 数据库迁移 |
| JWT + OAuth2 | 认证授权 |
| OpenAI API | AI 模型调用 |

### 前端 (Frontend)
| 技术 | 用途 |
|------|------|
| React 18.3+ | UI 框架 |
| TypeScript 5.0+ | 类型安全 |
| Vite 5.0+ | 构建工具 |
| TailwindCSS | 样式系统 |
| shadcn/ui | 组件库 |
| React Query | 状态管理 |
| i18next | 国际化 |

## 快速开始

### 前置要求

- Python 3.10+
- Node.js 18+
- Docker & Docker Compose（可选）

### 方式一：Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone https://github.com/your-username/werewolf.git
cd werewolf

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填写必要的配置（如 OPENAI_API_KEY）

# 3. 启动服务
docker-compose up -d

# 4. 访问应用
# 前端: http://localhost:8081
# 后端 API: http://localhost:8082
# API 文档: http://localhost:8082/docs
```

### 方式二：本地开发

#### 启动后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp ../.env.example ../.env
# 编辑 .env 文件

# 初始化数据库
python -m app.init_db

# 启动服务
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 启动前端

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 项目结构

```
werewolf/
├── backend/                 # 后端服务
│   ├── app/
│   │   ├── api/            # API 路由
│   │   ├── core/           # 核心配置
│   │   ├── models/         # 数据库模型
│   │   ├── schemas/        # Pydantic 模式
│   │   ├── services/       # 业务逻辑
│   │   └── i18n/           # 国际化资源
│   ├── migrations/         # 数据库迁移
│   ├── scripts/            # 工具脚本
│   └── requirements.txt
│
├── frontend/               # 前端应用
│   ├── src/
│   │   ├── components/    # React 组件
│   │   ├── pages/         # 页面组件
│   │   ├── hooks/         # 自定义 Hooks
│   │   └── lib/           # 工具函数
│   └── package.json
│
├── docker-compose.yml      # Docker 编排
└── README.md
```

## 环境配置

### 必需配置

| 变量名 | 说明 | 示例 |
|--------|------|------|
| `OPENAI_API_KEY` | OpenAI API 密钥 | `sk-xxx` |
| `JWT_SECRET_KEY` | JWT 签名密钥 | 随机字符串 |

### 可选配置

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `OPENAI_BASE_URL` | API 基础 URL | OpenAI 官方 |
| `LLM_MODEL` | 使用的模型 | `gpt-4o-mini` |
| `DEBUG` | 调试模式 | `false` |
| `LOG_LEVEL` | 日志级别 | `INFO` |
| `ENV_MANAGEMENT_ENABLED` | 启用环境变量管理功能 | `false` |

### 环境变量管理功能

从设置页面可以直接编辑 `.env` 文件中的环境变量（需要管理员权限）。

**启用方式**:
```bash
# 在 .env 文件中添加
ENV_MANAGEMENT_ENABLED=true
```

**⚠️ 重要限制**:
- 该功能使用进程内锁（`threading.Lock`），**仅支持单进程部署**
- 使用多进程模式（如 `gunicorn --workers=2` 或 Kubernetes 多副本）会导致并发写入冲突和数据丢失
- 修改环境变量后需要重启服务才能生效

**生产环境部署建议**:
1. **单进程部署**: 使用 `uvicorn app.main:app --workers=1` 或 `gunicorn --workers=1`
2. **多进程部署**:
   - 禁用该功能（保持 `ENV_MANAGEMENT_ENABLED=false`）
   - 或实现文件级锁（如 `portalocker` 库）替代进程锁
   - 或使用专业的配置管理服务（AWS Secrets Manager、Kubernetes ConfigMap 等）

详见 `backend/app/services/env_file_manager.py` 模块文档。

### 多 Provider 配置

项目支持多种 LLM Provider，可在 `.env` 中配置：

- **OpenAI** - 默认 Provider
- **DeepSeek** - 国产高性价比选择
- **Gemini** - Google 的 AI 服务
- **Anthropic** - Claude 模型

## 游戏规则

### 角色说明

| 角色 | 阵营 | 技能 |
|------|------|------|
| 狼人 | 狼人阵营 | 每晚可以选择杀害一名玩家 |
| 村民 | 好人阵营 | 无特殊技能，通过投票找出狼人 |
| 预言家 | 好人阵营 | 每晚可以查验一名玩家的身份 |
| 女巫 | 好人阵营 | 拥有一瓶解药和一瓶毒药 |
| 猎人 | 好人阵营 | 死亡时可以开枪带走一名玩家 |

### 游戏流程

1. **分配角色** - 系统随机分配角色给所有玩家
2. **夜晚阶段** - 狼人杀人，特殊角色行动
3. **白天阶段** - 玩家讨论，投票放逐嫌疑人
4. **胜负判定** - 狼人全部出局或好人数量不足时游戏结束

## API 文档

启动后端服务后，访问以下地址查看 API 文档：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## 测试

```bash
# 后端测试
cd backend
pytest

# 前端测试
cd frontend
npm run test
```

## 贡献指南

欢迎参与项目贡献！请遵循以下步骤：

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交更改：`git commit -m 'Add amazing feature'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

## 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

## 联系我们

- Issue: [GitHub Issues](https://github.com/your-username/werewolf/issues)
- Wiki: [项目文档](https://github.com/your-username/werewolf/wiki)

---

<p align="center">
  Made with love by Werewolf AI Team
</p>
