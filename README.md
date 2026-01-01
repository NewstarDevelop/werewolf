# 狼人杀

[English](./README.en.md) | [简体中文](./README.md)

一个基于 AI 的在线狼人杀游戏，支持人类玩家与多个 AI 玩家共同游戏。采用 FastAPI + React + Docker 架构，提供流畅的游戏体验和智能的 AI 对手。

在线预览：https://werewolf.newstardev.de

（已开启mock模式，未配置真实密钥）

![Game Screenshot](https://img.shields.io/badge/Game-Werewolf-red)
![Python](https://img.shields.io/badge/Python-3.13-blue)
![React](https://img.shields.io/badge/React-18.3-61dafb)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ed)

## 特性

- **完整游戏流程**：支持狼人、预言家、女巫、猎人等经典角色
- **AI 玩家**：基于 OpenAI GPT 的智能 AI 玩家，支持 Mock 模式测试
- **多房间系统**：支持多个房间同时进行游戏，玩家可自由创建和加入房间
- **混合对战**：支持纯真人、纯 AI、真人 + AI 混合等多种游戏模式
- **实时聊天**：游戏内实时聊天系统，记录所有玩家发言
- **现代化 UI**：基于 shadcn/ui 的精美界面设计，纯黑主题
- **Docker 部署**：一键启动，开箱即用
- **响应式设计**：支持桌面和移动端访问
- **数据持久化**：SQLite 数据库存储房间信息
- **国际化支持**：支持中英文切换
- **AI 对局分析**：游戏结束后可查看 AI 生成的对局分析报告

## 游戏角色

| 角色 | 阵营 | 能力 |
|------|------|------|
| 狼人 | 狼人阵营 | 每晚可以杀死一名玩家 |
| 预言家 | 好人阵营 | 每晚可以查验一名玩家的身份 |
| 女巫 | 好人阵营 | 拥有解药和毒药各一瓶，同一晚使用解药后无法使用毒药 |
| 猎人 | 好人阵营 | 被淘汰时可以开枪带走一名玩家 |
| 村民 | 好人阵营 | 普通村民，无特殊能力 |

## 快速开始

### 前置要求

- Docker 和 Docker Compose
- （可选）OpenAI API Key（用于真实 AI 对手）

### 使用 Docker 启动

```bash
git clone https://github.com/NewstarDevelop/Werewolf.git
cd Werewolf
cp .env.example .env
nano .env
```
**填入真实模型商、密钥、模型之后**

```bash
docker compose up
```

 **访问游戏**
- 前端页面：http://localhost:8081
- 后端 API：http://localhost:8082
- API 文档：http://localhost:8082/docs

### 本地开发

#### 后端开发

```bash
cd backend

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 前端开发

```bash
cd frontend

# 安装依赖
npm install

# 运行开发服务器
npm run dev
```

## 项目结构

```
Werewolf/
├── backend/                 # FastAPI 后端
│   ├── app/
│   │   ├── api/            # API 路由
│   │   │   └── endpoints/
│   │   │       ├── game.py      # 游戏API
│   │   │       └── room.py      # 房间API
│   │   ├── core/           # 核心配置
│   │   │   └── database.py      # 数据库配置
│   │   ├── models/         # 数据模型
│   │   │   ├── game.py          # 游戏模型
│   │   │   └── room.py          # 房间模型
│   │   ├── schemas/        # Pydantic 模式
│   │   └── services/       # 业务逻辑
│   │       ├── game_engine.py   # 游戏引擎
│   │       ├── room_manager.py  # 房间管理
│   │       ├── llm.py           # AI 服务
│   │       └── prompts.py       # AI 提示词
│   ├── data/               # 数据存储
│   │   └── werewolf.db          # SQLite 数据库
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/               # React 前端
│   ├── src/
│   │   ├── components/     # React 组件
│   │   │   ├── game/      # 游戏相关组件
│   │   │   └── ui/        # UI 基础组件
│   │   ├── hooks/         # 自定义 Hooks
│   │   ├── services/      # API 服务
│   │   │   ├── api.ts          # 游戏API
│   │   │   └── roomApi.ts      # 房间API
│   │   ├── pages/         # 页面组件
│   │   │   ├── RoomLobby.tsx   # 房间大厅
│   │   │   ├── RoomWaiting.tsx # 房间等待室
│   │   │   └── GamePage.tsx    # 游戏页面
│   │   └── utils/         # 工具函数
│   │       └── player.ts       # 玩家标识管理
│   ├── Dockerfile
│   ├── nginx.conf
│   └── package.json
├── docker-compose.yml
├── PROGRESS.md             # 开发进度与问题清单
└── README.md
```

## 游戏玩法

### 游戏模式

#### 混合模式（真人 + AI）
1. 创建房间，等待部分玩家加入
2. 房主点击"填充AI并开始"
3. 系统自动填充剩余座位为AI
4. 例如：3个真人 + 6个AI

### 游戏流程

1. **游戏开始**：通过房间系统创建或加入游戏
2. **角色分配**：系统自动分配角色（3 狼人、3 村民、预言家、女巫、猎人）
3. **夜晚阶段**：
   - 狼人选择击杀目标
   - 预言家查验玩家身份
   - 女巫先决策是否使用解药，再决策是否使用毒药（同一晚使用解药后无法使用毒药）
4. **白天阶段**：
   - 所有玩家依次发言
   - 投票淘汰可疑玩家
5. **胜利条件**：
   - 好人阵营：淘汰所有狼人
   - 狼人阵营：狼人数量 >= 好人数量，或所有村民死亡（屠民），或所有神职死亡（屠神）

### 操作指南

- **发言**：在白天阶段，在输入框中输入发言内容，点击"确认"
- **投票**：在投票阶段，点击玩家头像选择投票目标
- **使用技能**：在夜晚阶段，点击"技能"按钮使用角色技能

## 技术栈

### 后端
- **FastAPI**：现代化的 Python Web 框架
- **Pydantic**：数据验证和序列化
- **OpenAI API**：AI 玩家决策引擎
- **Uvicorn**：ASGI 服务器

### 前端
- **React 18**：用户界面框架
- **TypeScript**：类型安全
- **Vite**：构建工具
- **TanStack Query**：数据获取和状态管理
- **shadcn/ui**：UI 组件库
- **Tailwind CSS**：样式框架
- **React Router**：路由管理
- **i18next**：国际化

### 基础设施
- **Docker & Docker Compose**：容器化部署
- **Nginx**：前端静态文件服务

## 配置说明

### AI调试面板（心理活动）

只有在.env中配置 DEBUG_MODE=true 时，才能正常显示内容

### 环境变量

在项目根目录创建 `.env` 文件进行配置：

```env
# OpenAI API 配置
OPENAI_API_KEY=your_api_key_here
OPENAI_MODEL=gpt-4o-mini

# 应用配置
DEBUG=false
CORS_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
```

### 玩家级别的 LLM 配置

你可以为每个 AI 玩家（座位 2-9）配置独立的 LLM 提供商和参数。在 `.env` 文件中添加：

```env
# 为玩家 2 配置专属 LLM
AI_PLAYER_2_NAME=player2
AI_PLAYER_2_API_KEY=your_api_key
AI_PLAYER_2_BASE_URL=https://api.openai.com/v1
AI_PLAYER_2_MODEL=gpt-4o-mini
AI_PLAYER_2_TEMPERATURE=0.7
AI_PLAYER_2_MAX_TOKENS=500

# 为玩家 3 配置不同的模型
AI_PLAYER_3_NAME=player3
AI_PLAYER_3_API_KEY=your_api_key
AI_PLAYER_3_MODEL=gpt-4o
# ... 其他配置
```

**支持的配置项**：
- `AI_PLAYER_X_NAME`：玩家名称（可选）
- `AI_PLAYER_X_API_KEY`：API 密钥
- `AI_PLAYER_X_BASE_URL`：API 基础 URL（可选，默认使用 OpenAI）
- `AI_PLAYER_X_MODEL`：模型名称（默认：gpt-4o-mini）
- `AI_PLAYER_X_TEMPERATURE`：温度参数（默认：0.7）
- `AI_PLAYER_X_MAX_TOKENS`：最大 token 数（默认：500）
- `AI_PLAYER_X_MAX_RETRIES`：最大重试次数（默认：2）

其中 `X` 为玩家座位号（2-9，座位 1 为人类玩家）。

### Mock 模式

如果不配置 `OPENAI_API_KEY`，系统会自动进入 Mock 模式，AI 玩家将使用预设的随机策略进行游戏。

### AI 对局分析配置

游戏结束后可以查看AI生成的对局分析报告。配置示例：

```env
# AI分析配置（可选，未配置则使用默认OpenAI配置）
ANALYSIS_PROVIDER=openai          # 分析专用provider（可选）
ANALYSIS_MODEL=gpt-4o             # 推荐使用高级模型以获得更好的分析质量
ANALYSIS_MODE=comprehensive       # 分析模式：comprehensive/quick/custom
ANALYSIS_LANGUAGE=auto            # 分析语言：auto/zh/en
ANALYSIS_CACHE_ENABLED=true       # 是否启用缓存
ANALYSIS_MAX_TOKENS=4000          # 最大token数
ANALYSIS_TEMPERATURE=0.7          # 温度参数
```

**配置说明**：
- 如果不单独配置 `ANALYSIS_PROVIDER`，将使用默认的 `OPENAI_API_KEY` 进行分析
- 推荐使用 `gpt-4o` 或更高级的模型以获得更详细准确的分析
- `comprehensive` 模式提供详细分析（3-5分钟），`quick` 模式提供快速总结（1-2分钟）
- 分析结果会被缓存，避免重复计算

## API 文档

启动服务后访问 http://localhost:8082/docs 查看完整的 API 文档（Swagger UI）。

### 主要 API 端点

#### 房间管理
- `POST /api/rooms` - 创建房间
- `GET /api/rooms` - 获取房间列表（可按状态筛选）
- `GET /api/rooms/{room_id}` - 获取房间详情
- `POST /api/rooms/{room_id}/join` - 加入房间
- `POST /api/rooms/{room_id}/ready` - 切换准备状态
- `POST /api/rooms/{room_id}/start` - 开始游戏（支持AI填充）
- `DELETE /api/rooms/{room_id}` - 删除房间（房主专用）

#### 游戏进行
- `POST /api/game/start` - 开始新游戏（已集成到房间系统）
- `GET /api/game/{game_id}/state` - 获取游戏状态
- `POST /api/game/{game_id}/action` - 玩家行动
- `POST /api/game/{game_id}/step` - 推进游戏进程

## 故障排除

### Docker 相关问题

**问题：容器启动失败**
```bash
# 查看日志
docker-compose logs -f

# 重启服务
docker-compose restart
```

**问题：端口被占用**
```bash
# 修改 docker-compose.yml 中的端口映射
# 例如：将 8081:80 改为 8082:80
```

### 前端开发问题

**问题：npm install 失败**
```bash
# 清除缓存后重试
npm cache clean --force
npm install
```

## 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

## 开发计划

### 最新版本 (v1.3 - 2024-12-30)

#### 安全与稳定性
- JWT 认证体系 - 完整的 Token 认证
- 异步 LLM 调用 - 非阻塞 AI 操作
- 游戏状态锁 - 防止并发竞态
- 内存管理 - 游戏上限与自动清理
- 输入净化 - 防止 Prompt 注入

#### 游戏功能
- 狼人自刀策略 - 允许狼人击杀自己
- 胜负判定修复 - 正确的狼人胜利条件
- 动作校验增强 - 全面的目标合法性验证

### 已完成功能
| 版本 | 日期 | 主要功能 |
|------|------|----------|
| v1.3 | 2024-12-30 | 安全修复、稳定性增强、狼人自刀 |
| v1.2 | 2024-12-30 | 多房间系统、AI填充、混合对战 |
| v1.1 | 2024-12-28 | AI对局分析、分析缓存 |
| v1.0 | 2024-12-27 | 初始版本、国际化支持 |

### 计划中功能
- [ ] 添加更多游戏角色（守卫、猎魔人等）
- [ ] 添加游戏回放功能
- [ ] 优化 AI 策略
- [ ] WebSocket 实时通信
- [ ] 用户账户系统

> 详细文档请查看 [docs/](./docs/) 目录：
> - [变更日志](./docs/changelog.md) - 完整版本历史
> - [架构说明](./docs/architecture.md) - 系统设计
> - [安全审查](./docs/security-audit.md) - 安全修复详情

## 许可证

本项目采用 MIT 许可证。

---

如果这个项目对你有帮助，请给一个 Star！
