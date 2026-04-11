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
  - 优先用于代码上下文和探索性定位。
  - 若环境不可用，则回退 `ACE + Shell`。
- `ACE`：`mcp__ace_tool__codebase_retrieval`
- `Shell`：`shell_command`
- `C7`：`Context7` 文档查询
- `PW`：`Playwright` 前端交互验收

### 3.3 验收 Skill

- 默认：无强制 Skill
- `openai-docs`
  - 仅在接入 OpenAI 模型、参数、响应格式时使用
- `codex-autoresearch`
  - 仅在需要长时间自动回归、稳定性巡检时使用

### 3.4 默认排除文件

- 不改不提：`docs/werewolf_project.csv`、`docs/需求.md`、`docs/技术.md`、`docs/状态机架构.md`、`docs/补充.md`
- 不提交：`.env*`、`.venv/`、`node_modules/`、`dist/`、`coverage/`、`__pycache__/`、`.pytest_cache/`、日志文件、IDE 临时文件
- 不做：CSV 未定义的扩展玩法、非必须美化、非必要抽象层

### 3.5 默认提交文件

- 必提：`plan.md`
- 按实际产出提交：`backend/**`、`frontend/**`、`shared/**`、`tests/**`、必要配置文件、必要说明文档
- 提交应最小化，按任务边界提交，不混入无关改动

## 4. 任务清单

### 4.1 基础环境

| 优先级 | 任务ID | 内容 | 进度 | 结束验收标准 | 交付标准 | MCP / Skill | 建议提交文件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | INF-01 | 前后端项目初始化 | 未开始 | 前后端目录、依赖、启动脚本可用，能本地启动空壳应用 | 形成最小可运行骨架与基础配置 | FC, ACE, Shell, C7 / 默认 | `backend/**` `frontend/**` `pyproject.toml` `package.json` `.gitignore` |
| P0 | INF-02 | WebSocket 通信网关搭建 | 未开始 | 前后端可建立连接、断开重连、服务端可主动推送消息 | 完成 WebSocket 路由、连接管理、基础消息收发 | FC, ACE, Shell, C7 / 默认 | `backend/app/ws/**` `frontend/src/ws/**` `tests/ws/**` |

### 4.2 核心数据结构

| 优先级 | 任务ID | 内容 | 进度 | 结束验收标准 | 交付标准 | MCP / Skill | 建议提交文件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | DAT-01 | 玩家实体类定义 (Player) | 未开始 | 存在 `Player / HumanPlayer / AIPlayer`，核心属性与职责边界清晰 | 完成实体类、枚举、基础测试 | FC, ACE, Shell / 默认 | `backend/app/domain/player.py` `backend/app/domain/enums.py` `tests/domain/test_player.py` |
| P0 | DAT-02 | 游戏上下文设计 (GameContext) | 未开始 | 上下文可记录阶段、玩家、聊天、夜间死亡，并可做视野隔离 | 完成 `GameContext` 与 `Viewpoint Masking` 能力 | FC, ACE, Shell / 默认 | `backend/app/domain/game_context.py` `backend/app/domain/view_mask.py` `tests/domain/test_game_context.py` |

### 4.3 通信协议

| 优先级 | 任务ID | 内容 | 进度 | 结束验收标准 | 交付标准 | MCP / Skill | 建议提交文件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | WS-01 | 服务端推送协议 (S2C) | 未开始 | `SYSTEM_MSG / CHAT_UPDATE / AI_THINKING / REQUIRE_INPUT / GAME_OVER` 均有稳定结构 | 完成消息协议定义、序列化、推送测试 | FC, ACE, Shell, C7 / 默认 | `backend/app/protocols/s2c.py` `backend/app/ws/**` `frontend/src/types/ws.ts` `tests/protocols/test_s2c.py` |
| P0 | WS-02 | 客户端提交协议 (C2S) | 未开始 | `SUBMIT_ACTION` 可被校验、解析并解锁人类输入等待 | 完成 C2S 协议定义、参数校验、后端接入 | FC, ACE, Shell, C7 / 默认 | `backend/app/protocols/c2s.py` `backend/app/ws/**` `frontend/src/types/ws.ts` `tests/protocols/test_c2s.py` |

### 4.4 游戏引擎-主流程

| 优先级 | 任务ID | 内容 | 进度 | 结束验收标准 | 交付标准 | MCP / Skill | 建议提交文件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | ENG-01 | 状态机框架搭建 | 未开始 | 状态机可从初始化进入夜晚、白天、投票并正常结束 | 完成 `run_loop()`、状态流转、基础回归测试 | FC, ACE, Shell / 默认 | `backend/app/engine/game_engine.py` `backend/app/engine/states/**` `tests/engine/test_run_loop.py` |
| P0 | ENG-02 | 游戏大厅与初始化 (INIT) | 未开始 | 开局可随机分配座位与身份，并向真人下发正确信息 | 完成开局初始化、角色分配、AI 初始人设 | FC, ACE, Shell / 默认 | `backend/app/engine/init.py` `backend/app/services/setup_game.py` `tests/engine/test_init.py` |
| P0 | ENG-03 | 胜负实时校验 (CHECK_WIN) | 未开始 | 任意死亡结算后都能立即判定胜负且不中断主流程 | 完成独立胜负判定函数与覆盖测试 | FC, ACE, Shell / 默认 | `backend/app/engine/check_win.py` `tests/engine/test_check_win.py` |

### 4.5 游戏引擎-夜晚

| 优先级 | 任务ID | 内容 | 进度 | 结束验收标准 | 交付标准 | MCP / Skill | 建议提交文件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | ENG-N-01 | 狼人行动 (WOLF_ACTION) | 未开始 | 合法目标选择、真人优先、全 AI 时 Alpha 狼决策均成立 | 完成狼人夜行动作与死亡名单更新 | FC, ACE, Shell / 默认 | `backend/app/engine/night/wolf_action.py` `tests/engine/test_wolf_action.py` |
| P0 | ENG-N-02 | 预言家行动 (SEER_ACTION) | 未开始 | 只能查验非自己且存活目标，结果仅写入私有记忆 | 完成查验逻辑、目标校验、私有视野写入 | FC, ACE, Shell / 默认 | `backend/app/engine/night/seer_action.py` `tests/engine/test_seer_action.py` |
| P0 | ENG-N-03 | 女巫行动 (WITCH_ACTION) | 未开始 | 满足不可自救、每晚一瓶药、救人与毒人规则 | 完成女巫状态与 `killed_tonight` 结算 | FC, ACE, Shell / 默认 | `backend/app/engine/night/witch_action.py` `tests/engine/test_witch_action.py` |
| P1 | ENG-N-04 | 猎人开枪拦截 (HUNTER_SHOOTING) | 未开始 | 猎人非毒死时可开枪，结算后立即触发胜负校验 | 完成独立状态节点与结算测试 | FC, ACE, Shell / 默认 | `backend/app/engine/night/hunter_shooting.py` `tests/engine/test_hunter_shooting.py` |

### 4.6 游戏引擎-白天

| 优先级 | 任务ID | 内容 | 进度 | 结束验收标准 | 交付标准 | MCP / Skill | 建议提交文件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | ENG-D-01 | 宣布死讯与遗言 | 未开始 | 白天可正确公布死亡名单，仅首夜死者和放逐者有遗言 | 完成死讯播报、遗言状态流转与测试 | FC, ACE, Shell / 默认 | `backend/app/engine/day/dead_last_words.py` `tests/engine/test_dead_last_words.py` |
| P0 | ENG-D-02 | 依次发言机制 (DAY_SPEAKING) | 未开始 | 发言顺序正确，人类 60 秒超时兜底，AI 有思考提示 | 完成白天发言状态、等待机制、前后端联动 | FC, ACE, Shell, PW / 默认 | `backend/app/engine/day/day_speaking.py` `frontend/src/components/ChatHistory.tsx` `tests/engine/test_day_speaking.py` |
| P0 | ENG-D-03 | 投票放逐 (VOTING) | 未开始 | 存活玩家均可投票或弃票，同票判定无人出局 | 完成投票状态、计票、平票处理与测试 | FC, ACE, Shell, PW / 默认 | `backend/app/engine/day/voting.py` `frontend/src/components/ActionPanel.tsx` `tests/engine/test_voting.py` |

### 4.7 AI 大模型

| 优先级 | 任务ID | 内容 | 进度 | 结束验收标准 | 交付标准 | MCP / Skill | 建议提交文件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | LLM-01 | System Prompt 组装与调优 | 未开始 | Prompt 含座位、身份、性格、局势、历史与私有记忆，且限制字数与第四面墙 | 完成 Prompt Builder 与示例测试 | FC, ACE, Shell, C7 / `openai-docs`(仅 OpenAI) | `backend/app/llm/prompts.py` `backend/app/llm/builders.py` `tests/llm/test_prompts.py` |
| P0 | LLM-02 | 结构化输出约束 (JSON Mode) | 未开始 | AI 输出严格满足 JSON 结构，字段可被程序稳定消费 | 完成响应 schema、解析校验、接口适配 | FC, ACE, Shell, C7 / `openai-docs`(仅 OpenAI) | `backend/app/llm/schemas.py` `backend/app/llm/client.py` `tests/llm/test_json_mode.py` |
| P0 | LLM-03 | 容错与兜底机制 (Fallback) | 未开始 | 超时、坏 JSON、非法目标均能重试或回退默认动作 | 完成重试、回退、目标合法性校验与测试 | FC, ACE, Shell, C7 / `openai-docs`(仅 OpenAI) | `backend/app/llm/fallback.py` `backend/app/llm/client.py` `tests/llm/test_fallback.py` |

### 4.8 前端 UI / UX

| 优先级 | 任务ID | 内容 | 进度 | 结束验收标准 | 交付标准 | MCP / Skill | 建议提交文件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P0 | UI-01 | 玩家列表状态区 (Player List) | 未开始 | 可展示 1-9 号、存活状态、真人身份标识、AI 思考态 | 完成玩家列表组件与状态联动 | FC, ACE, Shell, PW / 默认 | `frontend/src/components/PlayerList.tsx` `frontend/src/styles/**` `frontend/tests/player-list.*` |
| P0 | UI-02 | 全局日志区 (Chat History) | 未开始 | 可按类型展示系统、私信、发言消息，并保持滚动体验 | 完成日志组件、消息样式、基础交互测试 | FC, ACE, Shell, PW / 默认 | `frontend/src/components/ChatHistory.tsx` `frontend/tests/chat-history.*` |
| P0 | UI-03 | 动态操作面板 (Action Panel) | 未开始 | 收到 `REQUIRE_INPUT` 时解锁正确面板，提交后立即回锁 | 完成操作面板组件、状态切换、交互测试 | FC, ACE, Shell, PW / 默认 | `frontend/src/components/ActionPanel.tsx` `frontend/src/state/**` `frontend/tests/action-panel.*` |

## 5. 执行顺序

1. 先做 `INF -> DAT -> WS -> ENG-01/02/03`
2. 再做 `ENG-N -> ENG-D`
3. 然后做 `LLM`
4. 最后做 `UI`
5. `ENG-N-04` 作为主流程闭环后的补充项

## 6. 最终说明

- 本计划明确以 `docs/werewolf_project.csv` 为开发主基线。
- 若实现与辅助文档冲突，以 CSV 的任务边界、业务描述、优先级为最高参照。
- 若实现与 CSV 的技术建议冲突，可调整实现方式，但不得改变 CSV 定义的业务结果与验收结果。
