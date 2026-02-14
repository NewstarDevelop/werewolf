# Redis 存储迁移设计方案

## 一、现状分析

### 当前架构
```
GameStore (单例)
├── games: dict[str, Game]        ← 主存储（内存）
├── _last_access: dict[str, float] ← TTL 追踪
├── _locks: dict[str, asyncio.Lock] ← 并发锁
└── _persistence: GamePersistence   ← SQLite 快照（崩溃恢复）
```

### GameStore 接口使用统计（7 个消费者文件）
| 方法 | 调用点 |
|------|--------|
| `get_game(id)` | game.py, websocket.py, game_engine.py, room_manager.py |
| `create_game(...)` | game.py, room_manager.py |
| `delete_game(id)` | game.py |
| `get_lock(id)` | game.py (2处) |
| `save_game_state(id)` | game_engine.py (2处) |
| `recover_from_snapshots()` | main.py |
| `_cleanup_old_games()` | main.py |
| `games` (直接访问) | main.py (统计) |
| `_cleanup_hooks` | game_engine.py |

### 关键约束
1. `Game` 是**可变 dataclass**——游戏引擎直接修改内存对象
2. 每个 step/action 触发 1 次 `get_game` + N 次字段修改 + 1 次 `save_game_state`
3. 序列化/反序列化已有实现（`game_persistence.py`）

## 二、迁移策略

### 分层架构设计
```
┌──────────────────────────────────────┐
│         GameStore (门面)              │  ← 保持现有 API 不变
├──────────────────────────────────────┤
│     GameStoreBackend (抽象层)         │  ← 新增
├──────────┬───────────────────────────┤
│ InMemory │  RedisBackend             │  ← 可切换
│ Backend  │  (序列化/反序列化)         │
└──────────┴───────────────────────────┘
```

### 实施阶段

#### Phase 1: 存储抽象层（本次实现）
- 定义 `GameStoreBackend` Protocol
- 提取 `InMemoryBackend`（封装当前行为）
- 重构 `GameStore` 使用抽象接口
- **零行为变更**，所有 250 个后端测试必须通过

#### Phase 2: Redis 后端实现
- 实现 `RedisBackend`（序列化存取 Game 对象）
- 配置环境变量切换：`GAME_STORE_BACKEND=memory|redis`
- Redis 连接池管理

#### Phase 3: 分布式锁
- `asyncio.Lock` → Redis 分布式锁（Redlock）
- 支持多实例部署

#### Phase 4: WebSocket 跨实例广播
- Redis Pub/Sub 替代本地 WebSocket 管理
- 跨实例游戏状态同步

## 三、Phase 1 详细设计

### 3.1 Backend Protocol

```python
# app/storage/backend.py
from typing import Protocol, Optional

class GameStoreBackend(Protocol):
    """Storage backend abstraction for game state."""
    
    def get(self, game_id: str) -> Optional["Game"]:
        """Retrieve a game by ID."""
        ...
    
    def put(self, game_id: str, game: "Game") -> None:
        """Store/update a game."""
        ...
    
    def delete(self, game_id: str) -> bool:
        """Delete a game. Returns True if existed."""
        ...
    
    def exists(self, game_id: str) -> bool:
        """Check if a game exists."""
        ...
    
    def count(self) -> int:
        """Return number of stored games."""
        ...
    
    def all_ids(self) -> list[str]:
        """Return all game IDs."""
        ...
```

### 3.2 InMemoryBackend

```python
# app/storage/memory.py
class InMemoryBackend:
    """In-memory dict storage (current behavior)."""
    
    def __init__(self):
        self._games: dict[str, Game] = {}
    
    def get(self, game_id: str) -> Optional[Game]:
        return self._games.get(game_id)
    
    def put(self, game_id: str, game: Game) -> None:
        self._games[game_id] = game
    
    def delete(self, game_id: str) -> bool:
        return self._games.pop(game_id, None) is not None
    
    def exists(self, game_id: str) -> bool:
        return game_id in self._games
    
    def count(self) -> int:
        return len(self._games)
    
    def all_ids(self) -> list[str]:
        return list(self._games.keys())
```

### 3.3 GameStore 重构

`GameStore` 保持所有现有方法签名不变，内部委托给 backend：

```python
class GameStore:
    def __init__(self, backend: Optional[GameStoreBackend] = None):
        self._backend = backend or InMemoryBackend()
        # ...其余初始化不变
    
    def get_game(self, game_id: str) -> Optional[Game]:
        game = self._backend.get(game_id)
        if game:
            self._last_access[game_id] = time.time()
        return game
    
    def create_game(self, ...) -> Game:
        # ...创建逻辑不变
        self._backend.put(game_id, game)
        # ...
    
    def delete_game(self, game_id: str) -> bool:
        if self._backend.delete(game_id):
            # cleanup...
            return True
        return False
```

### 3.4 文件结构

```
backend/app/
├── storage/
│   ├── __init__.py          # 导出 Backend protocol
│   ├── backend.py           # GameStoreBackend Protocol
│   └── memory.py            # InMemoryBackend
├── models/
│   └── game.py              # GameStore 重构使用 backend
```

## 四、风险控制

| 风险 | 对策 |
|------|------|
| 重构破坏现有功能 | 所有 250 个测试必须通过 |
| Game 对象可变性 | InMemory 后端保持引用语义，Redis 后端需 copy-on-read |
| 性能退化 | InMemory 后端零额外开销 |
| `game_store.games` 直接访问 | 保留为属性，委托到 backend |
