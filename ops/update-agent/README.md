# Werewolf Update Agent（方案 B：Runner 容器）

这是一个最小更新代理服务，供后端 Admin Update API 调用。

本方案采用 "Runner 容器" 执行更新：
- Update Agent 只负责鉴权、启动 Runner、查询 Runner 状态/日志
- Runner 在后台执行固定白名单序列：`git pull --ff-only` + `docker compose up -d --build`
- 即使 `docker compose up` 重启了 update-agent 容器，Runner 仍能继续执行；重启后的 update-agent 通过 `docker inspect`/`docker logs` 恢复状态

## 功能

- 检查仓库是否有更新（`git fetch` + 比较 HEAD）
- 触发更新任务（启动 Runner 容器执行 `git pull --ff-only` + `docker compose up -d --build`）
- 提供状态查询和日志输出

## 安全特性

- 强制 Bearer Token 鉴权
- 只执行白名单命令序列（不接受任意命令输入）
- 跨进程锁防止并发更新

> ⚠️ 重要：容器化部署需要挂载 `/var/run/docker.sock`，这等价于授予容器控制宿主机 Docker 的高权限。
> 必须确保：update-agent 不对公网暴露、使用强随机 Token、后端更新接口仅管理员可访问。

## 前置条件

宿主机需要安装：
- Docker Engine（包含 `docker compose` 插件）
- git（若 Runner 需要拉取私有仓库，还需配置凭据/SSH key）

## Docker Compose 集成（推荐）

目标：用户执行 `docker compose up -d` 时自动启动 Update Agent，后端通过 Docker 内部网络访问：`http://update-agent:9999`。

### 1) docker-compose.yml

项目根目录的 `docker-compose.yml` 已包含 `update-agent` 服务。

### 2) .env 配置

在项目根目录 `.env` 中配置（示例见 `.env.example`）：

```dotenv
# 固定 Compose 项目名：Runner 必须使用同一个 project name，避免拉起第二套栈
COMPOSE_PROJECT_NAME=werewolf

# 仓库根目录（宿主机绝对路径，且容器内需映射为同一路径）
WEREWOLF_ROOT=/path/to/werewolf

# 启用更新功能
UPDATE_AGENT_ENABLED=true

# 容器内访问 update-agent（Docker 内部 DNS）
UPDATE_AGENT_URL=http://update-agent:9999

# Bearer Token（与 update-agent 一致）
UPDATE_AGENT_TOKEN=your-strong-random-token
```

### 3) 启动

```bash
docker compose up -d
```

## 非容器化运行（可选）

```bash
# 设置环境变量
export UPDATE_AGENT_TOKEN='your-strong-random-token'
export UPDATE_AGENT_REPO_PATH='/path/to/Werewolf'
export UPDATE_AGENT_BRANCH='main'
export UPDATE_AGENT_REMOTE='origin'
export UPDATE_AGENT_BIND_HOST='127.0.0.1'
export UPDATE_AGENT_BIND_PORT='9999'

# 运行代理
python3 update_agent.py
```

### 使用 systemd 管理

创建 `/etc/systemd/system/werewolf-update-agent.service`：

```ini
[Unit]
Description=Werewolf Update Agent
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=/path/to/Werewolf/ops/update-agent
Environment=UPDATE_AGENT_TOKEN=your-strong-token
Environment=UPDATE_AGENT_REPO_PATH=/path/to/Werewolf
Environment=UPDATE_AGENT_BRANCH=main
ExecStart=/usr/bin/python3 update_agent.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable werewolf-update-agent
sudo systemctl start werewolf-update-agent
```

## 后端配置

在 `.env` 中配置：

```dotenv
# 启用更新功能
UPDATE_AGENT_ENABLED=true

# 更新代理地址
UPDATE_AGENT_URL=http://update-agent:9999

# 认证 Token（与代理端一致）
UPDATE_AGENT_TOKEN=your-strong-random-token

# HTTP 超时（秒）
UPDATE_AGENT_TIMEOUT_SECONDS=3

# 阻断条件
UPDATE_BLOCK_IF_PLAYING_ROOMS=true
UPDATE_BLOCK_IF_ACTIVE_GAME_WS=true

# 强制更新确认短语
UPDATE_FORCE_CONFIRM_PHRASE=UPDATE
```

## API 文档

所有接口需要 `Authorization: Bearer <TOKEN>` 头。

### GET /v1/check

检查是否有更新可用。

**响应**：
```json
{
  "update_available": true,
  "current_revision": "abc1234",
  "remote_revision": "def5678"
}
```

### POST /v1/run

触发更新任务（启动 Runner 容器）。

**请求**：
```json
{
  "force": false
}
```

**响应**（202）：
```json
{
  "job_id": "uuid"
}
```

### GET /v1/status

查询任务状态（通过 docker inspect 查询 Runner 容器状态）。

**响应**：
```json
{
  "job_id": "uuid",
  "state": "running",
  "message": "runner=werewolf-update-runner-xxx",
  "started_at": "2026-01-21T12:00:00Z",
  "finished_at": null,
  "current_revision": "abc1234",
  "remote_revision": "def5678",
  "last_log_lines": ["[git] pull --ff-only", "[docker] Building..."]
}
```

## 配置项

| 环境变量 | 默认值 | 说明 |
|---------|-------|------|
| `UPDATE_AGENT_TOKEN` | （必填） | 认证 Token |
| `UPDATE_AGENT_REPO_PATH` | （必填） | 仓库根目录路径 |
| `UPDATE_AGENT_REMOTE` | `origin` | Git 远程名称 |
| `UPDATE_AGENT_BRANCH` | `main` | Git 分支名称 |
| `UPDATE_AGENT_BIND_HOST` | `127.0.0.1` | 监听地址（容器化时使用 `0.0.0.0`） |
| `UPDATE_AGENT_BIND_PORT` | `9999` | 监听端口 |
| `UPDATE_AGENT_ALLOW_REMOTE_BINDING` | `false` | 是否允许非 localhost 绑定（docker.sock 安全检查） |
| `UPDATE_AGENT_KEEP_LOG_LINES` | `200` | 保留日志行数 |
| `UPDATE_AGENT_RUNNER_IMAGE` | `werewolf-update-agent` | Runner 容器使用的镜像 |
| `UPDATE_AGENT_RUNNER_CONTAINER_PREFIX` | `werewolf-update-runner` | Runner 容器名称前缀 |
| `UPDATE_AGENT_COMPOSE_PROJECT_NAME` | `werewolf` | Runner 执行 `docker compose -p` 的项目名 |
| `UPDATE_AGENT_COMPOSE_FILE` | `${REPO_PATH}/docker-compose.yml` | Runner 执行 `docker compose -f` 的文件路径 |
| `UPDATE_AGENT_GIT_SET_SAFE_DIRECTORY` | `true` | 自动设置 git safe.directory（解决容器内 UID 不匹配问题） |

## Runner 容器清理

Runner 容器执行完成后会保留（状态为 exited），可手动清理：

```bash
# 查看所有 Runner 容器
docker ps -a --filter "label=werewolf.update.runner=true"

# 清理已完成的 Runner 容器
docker container prune --filter "label=werewolf.update.runner=true"
```
