# Werewolf

基于 FastAPI、WebSocket 与 React 的单机狼人杀项目骨架。

## 目录

- `backend/`: Python 后端服务。
- `frontend/`: React 前端应用。
- `tests/`: 后端测试。
- `docs/`: 需求与设计基线文档。

## 启动

后端依赖与测试由 `pyproject.toml` 管理，前端依赖与构建由 `frontend/package.json` 管理。

根目录 `package.json` 仅提供常用脚本转发，避免在仓库根目录堆叠前端依赖。
