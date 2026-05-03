# Exa 调研备忘

调研日期：2026-05-03

本备忘把 Exa 搜索和网页读取结果落到当前项目：单机 9 人局 AI 狼人杀，FastAPI WebSocket 后端，React 前端。

## 1. 规则基线

当前项目采用固定 9 人板子：3 狼人、3 平民、预言家、女巫、猎人；胜负为屠边；女巫不可自救；同夜只能用一瓶药；猎人被毒不能开枪；平票无人出局。

Exa 查到的公开资料显示，9 人或近似 9 人配置的口径并不完全统一：

- 九游《狼人杀》规则页的 3 狼、3 神、3 民配置与项目板子一致，并明确女巫不可自救、每晚最多用一瓶药、猎人被女巫毒杀不可开枪、狼人屠边、好人灭狼胜利。
- 部分攻略把 9 人局写成“女巫首夜可自救”或“刀中女巫可以自救”，与项目规则不同。

项目落点：

- README 和 `docs/需求.md` 应继续把规则写成“本项目自定义固定基线”，避免被不同平台规则带偏。
- 后续如果加入“规则设置”，最值得参数化的是女巫是否首夜自救、死亡是否翻牌、是否有警长、平票处理。

来源：

- [九游《狼人杀》规则介绍](https://a.9game.cn/langrensha/1977194.html)
- [九游《饭局狼人杀》欢乐九人局进阶攻略](https://www.9game.cn/fjlrs/3218378.html)
- [87G 狼人杀 9 人局配置](https://www.87g.com/lrs/61275.html)

## 2. AI 玩家策略

当前 `backend/app/llm/builders.py` 已经做了视野隔离，通过 `build_player_view` 构造每个座位自己的公开历史、私有记忆和玩家视图。这是对的，也是狼人杀 AI 最重要的安全边界。

Exa 查到的 LLM 狼人杀研究给了两个可转化方向：

- Werewolf Arena 强调狼人杀是欺骗、推理、说服的复合评测场，还引入动态发言意愿。项目目前是固定座位顺序发言，短期不需要改流程，但可以给 AI 发言加“本轮发言目标”，例如保守观察、强踩、对跳、归票、解释票型。
- Language Agents with Reinforcement Learning for Strategic Play in the Werewolf Game 提到先让模型生成多样策略候选，再选择行动。项目不必上 RL，也可以轻量实现“战术标签 -> 提示词”的选择层，让规则型或 LLM provider 先选一个 tactic，再生成发言/投票/夜间行动。

项目落点：

- 在 `AIPlayer` 或私有记忆里维护简单 suspicion map，例如 `{seat_id: score}`，发言、查验、投票后更新。
- 在 `build_speech_prompt` 中加入“本轮战术目标”，而不是只给身份目标。狼人可选悍跳、倒钩、冲锋、深水；好人可选报验人、盘狼坑、保留身份、归票。
- 对投票和夜间行动使用结构化输出并保留兜底，减少模型输出不可解析导致流程卡住。

来源：

- [Werewolf Arena: A Case Study in LLM Evaluation via Social Deduction](https://arxiv.org/abs/2407.13943)
- [Language Agents with Reinforcement Learning for Strategic Play in the Werewolf Game](https://arxiv.org/abs/2310.18940v2)

## 3. WebSocket 可靠性

FastAPI 官方文档强调 WebSocket 连接关闭时会抛出 `WebSocketDisconnect`，多连接管理示例也会在断线时清理连接。Starlette 的 WebSocket `send` 底层在发送阶段遇到 `OSError` 时会把状态置为断开并抛出 `WebSocketDisconnect(code=1006)`。

项目现状：

- `backend/app/ws/routes.py` 已经在主接收循环捕获 `WebSocketDisconnect`，并在 `finally` 中断开 manager 和取消游戏任务。
- `backend/app/ws/manager.py` 原先只在 `send_json` 中吞掉 `RuntimeError`，没有在发送失败时主动清理连接。

已落地改动：

- `ConnectionManager.send_json` 现在会在非连接态或发送失败时调用 `disconnect`。
- 发送失败捕获范围补充了 `WebSocketDisconnect` 和 `OSError`。
- 新增 `tests/test_ws_manager.py` 覆盖非连接态和发送时断线。

来源：

- [FastAPI WebSockets 进阶文档](https://fastapi.tiangolo.com/advanced/websockets/)
- [FastAPI WebSocket 参考文档](https://fastapi.tiangolo.com/reference/websockets/)

## 4. 下一批 Exa 可继续推进的点

- 搜索“狼人杀 AI 发言语料/术语”，整理一份中文局内话术库，用于规则型 provider 和 prompt few-shot。
- 搜索公开狼人杀 UX/移动端布局参考，改进玩家面板、日志密度和行动按钮状态。
- 搜索 OpenAI 兼容接口的结构化输出差异，确认 `response_format` 在目标供应商上的兼容性，再决定是否把 JSON 模式做成默认配置。
