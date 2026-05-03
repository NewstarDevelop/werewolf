# Werewolf

单机 9 人局 AI 狼人杀项目：1 名真人玩家与 8 名 AI 玩家同桌，通过 FastAPI WebSocket 驱动局内流程，并由 React 前端展示对局状态、日志和操作入口。

后端默认使用本地规则型 AI provider，开箱即可跑通完整流程；配置完整的 OpenAI 兼容环境变量后，会切换到真实模型 provider。

## 功能概览

- 固定 9 人板子：3 狼人、3 平民、预言家、女巫、猎人
- 后端状态机覆盖夜晚行动、白天发言、投票放逐、猎人开枪和胜负判定
- 真人玩家输入等待：发言、投票、狼人刀人、预言家验人、女巫用药、猎人开枪
- 前端单页对局 UI：连接状态、玩家面板、局内日志、动态操作面板和明暗主题
- 本地规则型 AI provider 与 OpenAI 兼容 `chat/completions` provider

## 技术栈

- 后端：Python `>= 3.11`、FastAPI、WebSocket、Pydantic、httpx
- 前端：Node.js `>= 18`、React 18、TypeScript、Vite、Vitest
- 测试：pytest、Testing Library、Vitest

## 目录结构

```text
backend/   Python 后端服务、领域模型、状态机、WebSocket 网关、LLM provider
frontend/  React 前端应用
tests/     后端测试
docs/      需求、技术方案和状态机设计基线
```

## 快速开始

安装后端依赖：

```powershell
python -m pip install -e .[dev]
```

可选：接入自定义 OpenAI 兼容模型。跳过这一步时，后端会使用本地规则型 AI provider。

```powershell
$env:OPENAI_API_KEY = "your-api-key"
$env:OPENAI_MODEL = "your-model-name"
$env:OPENAI_BASE_URL = "https://your-provider.example/v1"
$env:OPENAI_TIMEOUT_SECONDS = "30"
```

自定义服务需要提供 OpenAI 兼容的 `chat/completions` 接口；`OPENAI_BASE_URL` 可以填写 API 根地址，也可以直接填写以 `/chat/completions` 结尾的完整地址。当前安全校验会拒绝 `localhost`、`127.0.0.1` 和私有网段地址。

启动后端服务：

```powershell
python -m uvicorn app.main:app --app-dir backend --reload
```

后端默认监听 `http://localhost:8000`，可用接口：

- 健康检查：`GET /health`
- 游戏 WebSocket：`GET /ws/game`

安装前端依赖：

```powershell
npm install --prefix frontend
```

启动前端开发服务：

```powershell
npm run dev --prefix frontend
```

打开 `http://localhost:5173` 开始对局。前端会根据当前页面的 hostname 连接 `ws://<hostname>:8000/ws/game`，因此开发时后端需要运行在 `8000` 端口。

## 真实模型接入

不配置模型变量时，项目使用本地规则型 provider。只要配置了任意模型相关变量，后端就会校验必填项；若缺少密钥或模型名，会直接报错，避免静默切回本地 provider。

必填变量：

- `OPENAI_API_KEY` 或 `STITCH_API_KEY`：模型平台密钥
- `OPENAI_MODEL` 或 `STITCH_MODEL`：模型名

可选变量：

- `OPENAI_BASE_URL` 或 `STITCH_BASE_URL`：默认 `https://api.openai.com/v1`
- `OPENAI_TIMEOUT_SECONDS` 或 `STITCH_TIMEOUT_SECONDS`：默认 `30`

PowerShell 示例：

```powershell
$env:OPENAI_API_KEY = "sk-..."
$env:OPENAI_MODEL = "gpt-4.1-mini"
$env:OPENAI_BASE_URL = "https://api.openai.com/v1"
$env:OPENAI_TIMEOUT_SECONDS = "30"
python -m uvicorn app.main:app --app-dir backend --reload
```

说明：

- `OPENAI_BASE_URL` 可以是 OpenAI 兼容服务的 base URL，也可以直接以 `/chat/completions` 结尾
- 出于安全考虑，模型 base URL 不能指向 localhost 或私有网段
- provider 会优先请求 JSON mode；兼容服务不支持时，会按实现中的兼容路径重试

## 常用命令

| 场景 | 命令 |
| --- | --- |
| 后端测试 | `python -m pytest -q` |
| 前端测试 | `npm run test --prefix frontend` |
| 前端构建 | `npm run build --prefix frontend` |
| 根目录启动前端 | `npm run dev` |
| 根目录前端测试 | `npm run test` |
| 根目录前端构建 | `npm run build` |

根目录 `package.json` 只转发前端脚本；后端服务仍使用 `python -m uvicorn app.main:app --app-dir backend --reload` 启动。

## 参考文档

- `docs/需求.md`：产品需求与规则基线
- `docs/技术.md`：技术方案草案
- `docs/状态机架构.md`：核心状态机设计
- `docs/werewolf_project.csv`：任务拆解表
