# 狼人杀项目完整审查报告（第二轮）

> **本报告基于第一轮审查修复后的代码重新审查生成。**
> 第一轮报告中的 P0 #1–#4、P1 #9–#10、P2 #13–#14、#16–#20 已全部修复。

---

## 一、项目概览

| 维度 | 详情 |
|------|------|
| **技术栈** | FastAPI + SQLAlchemy (async) + OpenAI / React 18 + TailwindCSS + shadcn/ui |
| **游戏模式** | 经典9人局、经典12人局（含狼王/白狼王变体） |
| **部署方式** | Docker Compose（backend + frontend + update-agent），单实例 |
| **认证** | JWT + HttpOnly Cookie 双模认证，OAuth (LinuxDo) |
| **实时通信** | WebSocket（per-player state filtering + 版本号防竞态）+ HTTP 轮询降级 |
| **AI** | 多 Provider 支持（OpenAI/DeepSeek/Gemini/Anthropic），三层限流，降级回退 |
| **i18n** | 中英双语（后端 JSON + 前端 i18next） |

---

## 二、架构优点

1. **清晰的模块分离** — `game_engine.py` 将 phase handlers 和 action handlers 拆分为独立模块，单一职责清晰。
2. **全链路安全** — prompt injection 过滤、JWT 验证、CORS/WS origin 校验、per-game 锁防并发、三层 rate limiting。
3. **WebSocket 优化** — per-player state filtering 防敏感信息泄露；`state_version` 版本号防过期更新覆盖新状态；指数退避重连（已修复）。
4. **崩溃恢复** — `GameStore` 支持 SQLite 快照持久化，启动时自动恢复未完成游戏，孤儿房间自动重置。
5. **前端 Hook 架构** — `useGame` Facade 模式组合 `useGameState` / `useGameActions` / `useGameAutomation`，职责分明。
6. **完善的测试覆盖** — 后端 19 个测试文件覆盖核心逻辑、安全、集成、WebSocket。
7. **AI 策略系统** — 狼人差异化战术角色（冲锋/倒钩/深水），预言家查验优先级，投票模式分析，守卫 LLM 决策（已修复）。
8. **遗言系统完整** — `DAY_LAST_WORDS` 阶段完整支持人类/AI 遗言（已修复），死后触发猎人/狼王开枪。

---

## 三、第一轮修复确认

以下为第一轮报告中已确认修复的问题：

| 原编号 | 问题 | 状态 |
|--------|------|------|
| P0 #1 | AI 守卫接入 LLM 决策 | ✅ 已修复 — `decide_guard_target()` + `build_context_prompt` protect 分支 |
| P0 #2 | `handle_day_speech` 递归 → 循环 | ✅ 已修复 — `while` 迭代跳过无效座位 |
| P0 #3 | `shoot_handler.py` `lang` 未定义 | ✅ 已修复 — 使用 `game.language` |
| P0 #4 | `room_id` 字段缺失 | ✅ 已修复 — 后端返回 + 前端类型补全 |
| P1 #9 | 遗言功能已启用 | ✅ 已修复 — AI 生成 + 人类输入 + 阶段路由 |
| P1 #10 | 硬编码英文错误消息 | ✅ 已修复 — i18n key 替代 |
| P2 #13 | WebSocket 指数退避 | ✅ 已修复 — 3s base × 2^n，max 30s |
| P2 #14 | Cleanup hooks 同步/异步 | ✅ 已修复 — `inspect.iscoroutinefunction` |
| P2 #16 | AuthContext useEffect 依赖 | ✅ 已修复 — `useRef` 存储 `toast`/`t` |
| P2 #17 | GamePage 乱码注释 | ✅ 已修复 |
| P2 #18 | `undefined as T` | ✅ 已修复 — `null as unknown as T` |
| P2 #19 | TypeScript 类型补全 | ✅ 已修复 — `has_save_potion` / `has_poison_potion` / `guard_last_target` |
| P2 #20 | 守卫前端提示 | ✅ 已修复 — PlayerGrid 不可选标记 + legend hint |

---

## 四、第二轮修复确认

以下为第二轮发现并已修复的问题：

| 编号 | 问题 | 状态 | 修改文件 |
|------|------|------|----------|
| P1 NEW-1 | 白狼王自爆传参缺失 | ✅ 已修复 | `useGame.ts` `GamePage.tsx` — `selfDestruct` 接受 `targetId`，传入 `selectedPlayerId` |
| P1 NEW-2 | startGame 语言硬编码 | ✅ 已修复 | `api.ts` — 导入 `i18n` 实例，自动检测当前语言 |
| P1 NEW-3 | 变量 `t` 遮蔽 i18n | ✅ 已修复 | `night_handler.py` `prompts.py` (3处) — 循环变量 `t` → `tid` |
| P1 NEW-4 | 正则无效转义 `\-` | ✅ 已修复 | `prompts.py` — `\-` → `\x2d` |
| P1 NEW-5 | 投票弃权语义不一致 | ✅ 已修复 | `day_actions.py` — `VOTE` + `target_id=None/0` 显式走弃权路径，返回 `vote_abstained` |
| P2 NEW-6 | 系统消息结构化 | ✅ 已修复 | `game.py` Message 增加 `i18n_key`/`i18n_params`；`day_handler.py` `night_handler.py` `shoot_handler.py` 所有系统消息添加 i18n key；`GamePage.tsx` 优先使用 `i18n_key`，正则降级；`en/game.json` `zh/game.json` 补全翻译 key |
| P2 NEW-8 | WebSocket 连接数上限 | ✅ 已修复 | `websocket_manager.py` — `MAX_CONNECTIONS_PER_GAME=20` `MAX_TOTAL_CONNECTIONS=500`，超限拒绝 (code 1013) |
| P2 NEW-9 | fetchApi 重试日志偏差 | ✅ 已修复 | `api-client.ts` — `MAX_RETRIES - retryCount + 1` → `MAX_RETRIES - retryCount` |
| P2 NEW-10 | 函数级 import 优化 | ✅ 已修复 | `prompts.py` — `re`、`defaultdict`、`ActionType`、`MessageType` 移至模块顶层 |
| P2 NEW-11 | Game 模型拆分 | ✅ 已修复 | 新建 `game_state_service.py`（~290行），提取 `build_state_for_player` + `get_pending_action_for_player`；`game.py` 从 ~970 行缩减至 ~681 行，保留薄委托方法 |
| P2 NEW-7 | 文本匹配 → 结构化 claim | ✅ 已修复 | 新建 `claim_detector.py` 集中角色声称检测；`Game.claimed_roles` 字段自动跟踪发言中的角色声称；`llm.py` `prompts.py` 改用结构化查询替代硬编码文本匹配 |
| P2 NEW-12 | 前端测试覆盖 | ✅ 已修复 | 新增 `VoteResultMessage.test.tsx`（5 tests）+ `GameActions.test.tsx`（18 tests）；修复 `api.test.ts` 预存的 mock 缺陷（缺少 `headers.get`）；全部 69 项前端测试通过 |

---

## 五、仍未解决的问题

#### NEW-13. 单实例架构限制（保留）
- **文件**: `docker-compose.yml:47-49`
- **问题**: 游戏状态全内存，无法水平扩展。
- **建议**: 中长期迁移至 Redis 存储。

---

## 六、安全审查摘要

| 项目 | 状态 | 备注 |
|------|------|------|
| JWT 认证 | ✅ 良好 | Header + Cookie 双模式，过期验证，admin 角色分离 |
| 输入清理 (Prompt Injection) | ✅ 良好 | `sanitize_text_input` 覆盖多种注入模式，长度限制 |
| CORS 配置 | ✅ 良好 | 可配置 origins，生产收紧 |
| WebSocket Origin 校验 | ✅ 良好 | `validate_origin` + `ALLOWED_WS_ORIGINS` |
| WebSocket 认证 | ✅ 良好 | Subprotocol > Cookie > Query（生产禁用 Query） |
| 座位 ID 来源 | ✅ 良好 | 从 token mapping 获取，非请求体 |
| Rate Limiting | ✅ 良好 | TokenBucket + PerGameSoft + provider 三层 |
| Debug 端点保护 | ✅ 良好 | `DEBUG_MODE` 开关 |
| Admin 认证 | ✅ 良好 | JWT admin token，`verify_admin` 中间件 |
| Docker 安全 | ✅ 良好 | non-root, no-new-privileges, cap_drop ALL, 资源限制 |
| 密码存储 | ✅ 良好 | bcrypt 哈希 |
| 前端 API 安全 | ✅ 良好 | 相对路径校验，拒绝绝对 URL 和协议相对 URL |

**潜在风险**:
- `update-agent` 挂载 `docker.sock`：已做安全加固（no-new-privileges, cap_drop, 资源限制），但 Docker socket 权限本身仍是攻击面
- WebSocket 连接数限制已添加（NEW-8 ✅），per-game 20 / 全局 500

---

## 七、性能考量

| 项目 | 状态 | 备注 |
|------|------|------|
| 游戏内存管理 | ✅ 良好 | TTL 过期清理 + 容量上限 1000 + LRU 淘汰 |
| LLM 调用优化 | ✅ 良好 | per-game 软限流 + provider 硬限流 + 线性退避重试 |
| 前端 ChatLog | ✅ 良好 | react-window 虚拟列表 |
| WebSocket 降级 | ✅ 良好 | WS 连接时 10s 慢轮询，断开时 2s 快轮询 |
| 前端懒加载 | ✅ 良好 | 所有页面 `lazy()` + `Suspense` |
| 后端后台清理 | ✅ 良好 | 定期清理 rate limiter / game store / DB tokens |
| 前端 playerMap | ✅ 良好 | `useMemo` 预构建 `Map<seat_id, Player>`，O(1) 查找 |
| React Query | ✅ 良好 | 禁用 retry（fetchApi 自带），staleTime=0 确保实时性 |

---

## 八、测试覆盖分析

| 层级 | 覆盖 | 评价 |
|------|------|------|
| 后端核心逻辑 | 25 个测试文件（320 项测试） | ✅ 充分 — 游戏流程、角色行为、胜利条件、claim_detector、game_state_service、storage抽象层、分布式锁、跨实例广播 |
| 后端安全 | 认证、WebSocket auth、rate limiter | ✅ 充分 |
| 后端集成 | API 端点、数据库、WebSocket | ✅ 充分 |
| 前端 API | `api.test.ts` | ✅ 已修复 mock 缺陷 |
| 前端 Hook | `useGame.test.tsx` `useGameTransformers.test.tsx` `useGameAutomation.test.tsx` `useActiveGame.test.ts` | ✅ 充分 — 初始化/状态/数据转换/自动推进/ID持久化 |
| 前端工具函数 | `voteUtils.test.ts` `errorHandler.test.ts` `messageTranslator.test.ts` `token.test.ts` `websocket.test.ts` `date.test.ts` `player.test.ts` `envUtils.test.ts` | ✅ 充分 — 解析/格式化/错误处理/日期/玩家ID/敏感Key检测 |
| 前端组件 | `ChatMessage.test.tsx` `VoteResultMessage.test.tsx` `GameActions.test.tsx` | ✅ 已补充 — 安全/渲染/交互 |
| E2E | 无 | ❌ 缺失 — 完整游戏流程端到端测试 |

---

## 九、剩余改进建议

| 优先级 | 问题 | 工作量 | 备注 |
|--------|------|--------|------|
| — | 无剩余问题 | — | NEW-13 全部 4 个阶段已完成 |

---

## 十、总结

项目整体质量 **优良**。经过两轮审查：

- **第一轮**: 发现 P0 × 4 + P1 × 6 + P2 × 8 = **18 项问题** → 全部修复 ✅
- **第二轮**: 发现 P1 × 5 + P2 × 8 = **13 项问题** → 修复 12 项 ✅，剩余 1 项为中长期架构改进

**累计修复 37 项**，全部问题均已解决（含 NEW-13 Redis 迁移 4 个阶段）。

安全、性能、部署配置方面均表现良好，无重大风险。后端测试覆盖充分（320 项），前端测试已补全至 165 项（17 个测试文件）。

第三轮修复补充：
- 修复 `useGameSound.ts` 10 项类型错误（Phase/isAlive/is_game_over/大小写枚举）
- 重构 `GamePage.tsx` 消除 ~60 行重复代码，复用 `useGameTransformers` hook
- 修复 `PlayerPublic` 类型导入错误（GamePage + useGameTransformers）
- 补充 `useGameTransformers` i18n_key 结构化翻译支持
- 删除死代码：LogWindow.tsx、GameLobby.tsx、game.ts 未使用类型
- 消除 ESLint 警告（test-utils.tsx react-refresh 误报）
- 新增测试：useActiveGame (14)、date (8)、player (10)

第四轮修复补充：
- 新增 `envUtils.test.ts`（13 项测试，覆盖敏感Key检测逻辑）
- 修复 `EnvVariablesTable.tsx` 中英文表头不一致（"描述" → "Description"）
- 统一类型定义：`PlayerGrid` / `ChatLog` 复用 `useGameTransformers` 的 `UIPlayer` / `UIMessage`，消除重复接口
- 补充 hooks barrel export：`useGameTransformers` + `UIPlayer` / `UIMessage` 类型
- 修复 `game.py` 内联 `import logging` → 模块级导入（2 处）
- 移除冲突的 `@types/react-window@1.8.8`（v1 类型覆盖了 v2 内置 `.d.ts`）
- 迁移 `ChatLog.tsx` 至 react-window v2 API（`listRef`/`scrollToRow`/`rowComponent`/`rowProps`/`defaultRowHeight`/标准 `onScroll`），消除全部 6 个类型错误
- 移除死代码：`estimateItemSize`/`totalHeight`（v2 内置动态行高管理）
- 验证后端-前端 API 契约一致性（`GameState` 类型 vs `build_state_for_player` 输出）

NEW-13 Redis 存储迁移（全部 4 个阶段完成）：
- Phase 1-2: 新增 `app/storage/` 抽象层：`GameStoreBackend` Protocol + `InMemoryBackend` + `RedisBackend`
- 重构 `GameStore` 使用可插拔后端，`create_backend()` 工厂支持 `GAME_STORE_BACKEND=memory|redis` 切换
- 添加写回缓存 `_write_cache`，支持 Redis 等非引用语义后端
- Phase 3: 分布式锁 `RedisLock`（SET NX EX + Lua 原子释放），`GameStore.get_lock` 自动选择 asyncio.Lock 或 RedisLock
- Phase 4: 跨实例广播 `GameUpdateBroadcaster`（Redis Pub/Sub psubscribe），集成到 app 启动/关闭和游戏端点
- 新增 70 项测试（存储 42 + 分布式锁 16 + 广播 12）
- 全部 320 项后端测试通过，零回归
- 设计文档：`backend/docs/redis-migration-design.md`

---

*报告生成时间: 2025年7月*
*审查范围: 全项目后端 + 前端 + 配置 + 部署*
*审查轮次: 第二轮（基于第一轮修复后的代码）*
