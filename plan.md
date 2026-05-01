# 工作模式计划

## 1. 开发依据

- 主依据 CSV：`docs/werewolf_project.csv`
- 辅助参考文档：`docs/需求.md`、`docs/技术.md`、`docs/状态机架构.md`、`docs/补充.md`
- 本计划按 **一行 CSV = 一条最小工作项** 编制，开发、验收、提交范围均以该 CSV 为主。

## 2. CSV 参照标准

- `模块`：用于划分开发域、目录边界、任务归属。
- `任务ID`：唯一追踪编号，用于提交说明、测试用例、验收记录关联。
- `功能模块/任务名称`：当前工作项名称，按此定义最小交付单元。
- `需求与业务逻辑说明`：业务基线，属于强约束，验收以此为准。
- `技术实现建议/细节`：默认实现参考，属于弱约束；若实现时调整，不能违背业务基线，且需在变更说明中记录原因。
- `优先级`：排期依据，先完成 `P0`，再处理 `P1`。
- CSV 未列出的功能不纳入本轮，遵循 `KISS / YAGNI / DRY / SOLID`。

## 3. 全局规则

### 3.1 进度状态

- `未开始`
- `进行中`
- `已完成`
- `阻塞`

### 3.2 MCP 工具集

- `FC`：`mcp__fast_context__fast_context_search`
- `ACE`：`mcp__ace_tool__codebase_retrieval`
- `Shell`：`shell_command`
- `C7`：`Context7` 文档查询
- `PW`：`Playwright` 前端交互验收

### 3.3 验收 Skill

- 默认：无强制 Skill
- `openai-docs`：仅在接入 OpenAI 模型时使用
- `codex-autoresearch`：仅在长时间自动回归时使用

### 3.4 默认排除文件

- 不改不提：`docs/werewolf_project.csv`、`docs/需求.md`、`docs/技术.md`、`docs/状态机架构.md`、`docs/补充.md`
- 不提交：`.env*`、`.venv/`、`node_modules/`、`dist/`、`coverage/`、`__pycache__/`、`.pytest_cache/`、日志文件、IDE 临时文件

### 3.5 默认提交文件

- 必提：`plan.md`
- 按实际产出提交：`backend/**`、`frontend/**`、`tests/**`、必要配置文件

## 4. 任务清单

### 4.1 基础环境

| 优先级 | 任务ID | 内容 | 进度 |
| --- | --- | --- | --- |
| P0 | INF-01 | 前后端项目初始化 | 已完成 |
| P0 | INF-02 | WebSocket 通信网关搭建 | 已完成 |

### 4.2 核心数据结构

| 优先级 | 任务ID | 内容 | 进度 |
| --- | --- | --- | --- |
| P0 | DAT-01 | 玩家实体类定义 (Player) | 已完成 |
| P0 | DAT-02 | 游戏上下文设计 (GameContext) | 已完成 |

### 4.3 通信协议

| 优先级 | 任务ID | 内容 | 进度 |
| --- | --- | --- | --- |
| P0 | WS-01 | 服务端推送协议 (S2C) | 已完成 |
| P0 | WS-02 | 客户端提交协议 (C2S) | 已完成 |

### 4.4 游戏引擎-主流程

| 优先级 | 任务ID | 内容 | 进度 |
| --- | --- | --- | --- |
| P0 | ENG-01 | 状态机框架搭建 | 已完成 |
| P0 | ENG-02 | 游戏大厅与初始化 (INIT) | 已完成 |
| P0 | ENG-03 | 胜负实时校验 (CHECK_WIN) | 已完成 |

### 4.5 游戏引擎-夜晚

| 优先级 | 任务ID | 内容 | 进度 |
| --- | --- | --- | --- |
| P0 | ENG-N-01 | 狼人行动 (WOLF_ACTION) | 已完成 |
| P0 | ENG-N-02 | 预言家行动 (SEER_ACTION) | 已完成 |
| P0 | ENG-N-03 | 女巫行动 (WITCH_ACTION) | 已完成 |
| P1 | ENG-N-04 | 猎人开枪拦截 (HUNTER_SHOOTING) | 已完成 |

### 4.6 游戏引擎-白天

| 优先级 | 任务ID | 内容 | 进度 |
| --- | --- | --- | --- |
| P0 | ENG-D-01 | 宣布死讯与遗言 | 已完成 |
| P0 | ENG-D-02 | 依次发言机制 (DAY_SPEAKING) | 已完成 |
| P0 | ENG-D-03 | 投票放逐 (VOTING) | 已完成 |

### 4.7 AI 大模型

| 优先级 | 任务ID | 内容 | 进度 |
| --- | --- | --- | --- |
| P0 | LLM-01 | System Prompt 组装与调优 | 已完成 |
| P0 | LLM-02 | 结构化输出约束 (JSON Mode) | 已完成 |
| P0 | LLM-03 | 容错与兜底机制 (Fallback) | 已完成 |

### 4.8 前端 UI / UX

| 优先级 | 任务ID | 内容 | 进度 |
| --- | --- | --- | --- |
| P0 | UI-01 | 玩家列表状态区 (Player List) | 已完成 |
| P0 | UI-02 | 全局日志区 (Chat History) | 已完成 |
| P0 | UI-03 | 动态操作面板 (Action Panel) | 已完成 |

## 5. 执行顺序

全部 22 个任务已完成。后续任务：
- 前端布局重塑：Dashboard 3栏 → 单焦点桌面中心 + 环形座位（2026-05-01 已完成）
- 代码质量：降级回退随机化、CSS token 化、WS 消息校验、ErrorBoundary
- 安全加固：CORS 中间件、LLM Base URL 校验
- 文档：DESIGN.md 补全（进行中）

## 6. 最终说明

- 本计划明确以 `docs/werewolf_project.csv` 为开发主基线。
- 若实现与辅助文档冲突，以 CSV 的任务边界、业务描述、优先级为最高参照。
