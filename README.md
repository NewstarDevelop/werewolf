# Werewolf

基于 FastAPI、WebSocket 与 React 的单机狼人杀项目。

当前仓库已经包含：

- 后端状态机、WebSocket 网关与人类输入等待逻辑
- 前端单页对局 UI，包括状态栏、玩家面板、日志流和操作面板
- 本地规则型 AI provider
- 可切换的 OpenAI 兼容真实模型 provider

## 目录

- `backend/`: Python 后端服务
- `frontend/`: React 前端应用
- `tests/`: 后端测试
- `docs/`: 需求与设计基线文档

## 环境要求

- Python `>= 3.11`
- Node.js `>= 18`

## 后端启动

安装依赖：

```powershell
python -m pip install -e .[dev]
```

启动服务：

```powershell
python -m uvicorn app.main:app --app-dir backend --reload
```

可用接口：

- 健康检查：`GET /health`
- 游戏 WebSocket：`GET /ws/game`

## 前端启动

安装依赖：

```powershell
npm install --prefix frontend
```

开发模式：

```powershell
npm run dev --prefix frontend
```

构建：

```powershell
npm run build --prefix frontend
```

## 真实模型接入

后端默认使用本地规则型 provider。只有在环境变量配置完整时，才会自动切换到 OpenAI 兼容接口。

必填变量：

- `OPENAI_API_KEY`: 模型平台密钥
- `OPENAI_MODEL`: 模型名

可选变量：

- `OPENAI_BASE_URL`: 默认 `https://api.openai.com/v1`
- `OPENAI_TIMEOUT_SECONDS`: 默认 `30`

PowerShell 示例：

```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:OPENAI_MODEL = "gpt-4.1-mini"
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
$env:OPENAI_TIMEOUT_SECONDS = "30"
python -m uvicorn app.main:app --app-dir backend --reload
```

说明：

- 未配置上述变量时，项目继续使用本地规则 provider
- 只配置一部分变量时，后端会直接报配置错误，不会静默切回本地 provider
- 真实模型接入层目前走 OpenAI 兼容 `chat/completions` 接口

## 测试

后端测试：

```powershell
python -m pytest -q
```

前端测试：

```powershell
npm run test --prefix frontend
```

## 根目录脚本

根目录 `package.json` 仅提供前端脚本转发，避免在仓库根目录重复维护前端依赖：

```powershell
npm run dev
npm run build
npm run test
```
