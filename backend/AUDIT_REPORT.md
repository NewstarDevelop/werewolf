# 项目完整审查报告

> 审查时间: 2025-02-13  
> 审查范围: `backend/` 全部代码 (79 Python 源文件, 19 测试文件)

---

## 一、总体评价

项目整体架构清晰，分层合理（API → Services → Models），安全意识良好（JWT、bcrypt、CSRF、XFF 验证、prompt injection 防护等均已实现）。以下按优先级列出发现的问题。

---

## 二、P0 — 安全漏洞

### 2.1 用户登录端点无速率限制
- **文件**: `app/api/endpoints/auth.py:147` (`/auth/login`)
- **现状**: `user_login_limiter` 已导入但**从未调用**。`/auth/login` 无任何速率限制，可被暴力破解。
- **对比**: `/auth/admin-login` 已正确使用 `admin_login_limiter`。
- **修复**: 在 `login()` 中加入 `user_login_limiter.check_rate_limit()` 和 `record_attempt()`。

### 2.2 通知 WebSocket 硬编码 localhost Origin 白名单
- **文件**: `app/api/endpoints/websocket_notifications.py:88-93`
- **现状**: `_validate_origin()` 无条件允许 `localhost:5173/3000`，**包括生产环境**。攻击者可伪造 Origin 头绕过 CSWSH 保护。
- **对比**: 游戏 WebSocket (`websocket_auth.py:validate_origin`) 正确地仅在 `DEBUG` 模式允许 localhost。
- **修复**: 将 localhost 白名单包裹在 `if settings.DEBUG:` 条件中。

### 2.3 `GamePersistence` SQLite 每次操作新建连接（无并发保护）
- **文件**: `app/services/game_persistence.py:239-254`
- **现状**: `_get_conn()` 每次调用创建新的 `sqlite3.connect()`，无连接池。多线程/多协程并发写入时可能触发 SQLite `database is locked` 错误。
- **修复**: 使用 `threading.Lock` 保护写操作，或改用 `check_same_thread=False` + 单连接复用。

---

## 三、P1 — 功能缺陷

### 3.1 TTL 清理不删除持久化快照
- **文件**: `app/models/game.py:678-703` (`_cleanup_old_games`)
- **现状**: TTL 过期清理删除内存中的 game，但不调用 `_delete_snapshot()`。快照会在 SQLite 中残留直到下次启动时被 `load_all_active` 的 cutoff 清理。
- **影响**: 如果服务在清理后 2 小时内重启，过期游戏会被错误恢复。
- **修复**: 在 `_cleanup_old_games` 循环中加入 `self._delete_snapshot(game_id)`。

### 3.2 `body.dict()` 使用已弃用的 Pydantic v1 API
- **文件**: `app/api/endpoints/users.py:180`
- **现状**: `body.dict()` 在 Pydantic v2 中已弃用，应使用 `body.model_dump()`。
- **影响**: 运行时会产生 deprecation warning，未来版本可能移除。

### 3.3 OAuthState / RefreshToken 无过期清理
- **文件**: `app/models/user.py` (OAuthState, RefreshToken 表)
- **现状**: `oauth_states` 有 `expires_at` 字段但无后台任务清理过期记录。`refresh_tokens` 同理。长期运行后这两张表会无限增长。
- **修复**: 添加定期清理任务（类似 `_periodic_rate_limiter_cleanup`）。

### 3.4 `/auth/reset-password` 端点无实际功能
- **文件**: `app/api/endpoints/auth.py:326-334`
- **现状**: 端点存在但只返回固定消息，不发送邮件也不生成重置令牌。`PasswordResetToken` 模型已定义但未使用。
- **影响**: 用户无法实际重置密码。若暂不实现应文档标注。

### 3.5 `from_orm` 应改为 `model_validate`
- **文件**: `app/api/endpoints/users.py:36,81`
- **现状**: `UserResponse.from_orm(user)` 是 Pydantic v1 写法。虽然 `from_attributes=True` 在 Config 中已设置使其仍然工作，但规范写法应为 `UserResponse.model_validate(user)`（与 `auth.py:129` 一致）。

---

## 四、P2 — 代码质量 / 可维护性

### 4.1 通知 WebSocket 重复实现 Origin 验证
- **文件**: `app/api/endpoints/websocket_notifications.py:51-95`
- **现状**: `_validate_origin()` 是 `websocket_auth.py:validate_origin()` 的重复实现，逻辑不同且安全级别更低（见 2.2）。
- **修复**: 统一使用 `websocket_auth.validate_origin()`。

### 4.2 通知 WebSocket 重复实现 Token 提取
- **文件**: `app/api/endpoints/websocket_notifications.py:40-48,98-104`
- **现状**: `_extract_token_from_subprotocols()` 和 `_extract_token_from_cookies()` 是 `websocket_auth.py:extract_token()` 的部分重复。
- **修复**: 统一使用 `websocket_auth.authenticate_websocket()`。

### 4.3 LLM 伪造浏览器 User-Agent
- **文件**: `app/services/llm.py:40-44`
- **现状**: 使用伪造的 Chrome User-Agent 字符串访问 LLM API。这可能违反某些 API 提供商的 ToS，且 Chrome 120 版本已过时。
- **建议**: 使用标识性 User-Agent（如 `WerewolfAI/1.0`）或使用 OpenAI SDK 默认值。

### 4.4 `GamePersistence` 同步 I/O 在 async 上下文中
- **文件**: `app/services/game_persistence.py` (所有方法)
- **现状**: `save_snapshot`/`delete_snapshot` 使用同步 `sqlite3`，在 `GameEngine.step()`（async）调用链中执行，会阻塞事件循环。
- **影响**: 高并发时可能造成延迟。对 SQLite 小数据量影响较小，但不规范。
- **建议**: 使用 `asyncio.to_thread()` 包装或迁移到 `aiosqlite`。

### 4.5 `_cleanup_old_games` 遍历时修改字典
- **文件**: `app/models/game.py:689-702`
- **现状**: 先收集 `to_remove` 再删除，逻辑正确。但缺少对 `_delete_snapshot` 的调用（见 3.1）。

### 4.6 `emit_batch` 逐条 refresh 效率较低
- **文件**: `app/services/notification_service.py:324-325`
- **现状**: `for notification in notifications: await db.refresh(notification)` 对大批量广播会产生 N 次 DB 查询。
- **建议**: 大多数场景 flush 后 ID 已可用，可跳过 refresh。

---

## 五、架构 / 设计建议

### 5.1 已做得好的方面 ✅
- **安全**: bcrypt 12 轮、JWT HS256、CSRF state、constant-time 比较、XFF 信任链验证、prompt injection 防护
- **密码学随机**: 全部使用 `secrets.SystemRandom`，无 `random` 模块残留
- **async 一致性**: 所有 API 端点均为 `async def`，数据库操作使用 `AsyncSession`
- **同步 DB 完全移除**: 无 `get_db` / `Session` 残留依赖
- **CORS**: 生产环境 fail-fast 校验，拒绝 `*`
- **错误处理**: 统一 `AppException` 体系 + 全局 exception handler，不泄漏堆栈
- **容量保护**: `GameStore` MAX_GAMES=1000 + TTL + per-game locks
- **CSV 注入防护**: Admin CSV 导出有 sanitize
- **WebSocket**: 统一认证模块、Origin 校验、subprotocol 支持
- **通知系统**: Outbox 模式、Redis PubSub、batch emit、幂等键
- **游戏持久化**: 快照恢复 + orphaned room 修复已正确处理

### 5.2 潜在改进方向
- **日志审计**: 关键管理操作（封禁用户、重启等）缺少结构化审计日志（有 logger.warning 但无持久审计表）
- **健康检查深度**: `/health` 只返回 `{"status": "healthy"}`，不检查 DB 连接或 Redis 状态
- **Alembic 迁移**: `alembic/` 目录存在但未检查迁移是否与当前模型同步
- **配置加密**: `TOKEN_ENCRYPTION_KEY` 为空时 `EncryptedString` 类型的行为需确认是否 fallback 到明文

---

## 六、测试覆盖评估

| 测试文件 | 覆盖范围 | 评价 |
|---------|---------|------|
| `test_game_core.py` (44 tests) | 游戏核心逻辑 | ✅ 充分 |
| `test_game_persistence.py` (16 tests) | 序列化/反序列化/快照 | ✅ 充分 |
| `test_integration_auth.py` | 注册/登录/登出 | ✅ 基本覆盖 |
| `test_integration_room.py` | 房间 CRUD | ✅ 基本覆盖 |
| `test_integration_game.py` | 游戏启动/状态 | ⚠️ 较薄 |
| `test_integration_admin.py` | 管理员端点 | ✅ 基本覆盖 |
| `test_websocket_security.py` | WS 安全 | ✅ 充分 |
| `test_rate_limiter_fixes.py` | 速率限制 | ✅ 充分 |
| — | WebSocket 通知 | ❌ 无覆盖 |
| — | OAuth 流程 | ❌ 无覆盖 |
| — | 多人房间游戏全流程 | ❌ 无覆盖 |
| — | 广播管理 CRUD | ❌ 无覆盖 |

---

## 七、修复优先级汇总

| # | 优先级 | 问题 | 复杂度 |
|---|--------|------|--------|
| 2.1 | **P0** | 用户登录无速率限制 | 低 |
| 2.2 | **P0** | 通知 WS 生产环境 localhost 白名单 | 低 |
| 2.3 | **P0** | GamePersistence 无并发保护 | 中 |
| 3.1 | **P1** | TTL 清理不删除快照 | 低 |
| 3.2 | **P1** | Pydantic `dict()` 弃用 | 低 |
| 3.3 | **P1** | OAuthState/RefreshToken 无清理 | 中 |
| 3.4 | **P1** | 密码重置未实现 | 高（需邮件服务） |
| 3.5 | **P1** | `from_orm` → `model_validate` | 低 |
| 4.1-4.2 | **P2** | 通知 WS 重复代码 | 中 |
| 4.3 | **P2** | 伪造 User-Agent | 低 |
| 4.4 | **P2** | 同步 SQLite 阻塞事件循环 | 中 |
| 4.6 | **P2** | emit_batch 逐条 refresh | 低 |
