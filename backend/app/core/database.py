"""Database connection and session management."""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
import os
import logging

logger = logging.getLogger(__name__)

# SQLite数据库路径（生产环境可切换为PostgreSQL）
DATA_DIR = os.getenv("DATA_DIR", "data")

# Create data directory with error handling
try:
    os.makedirs(DATA_DIR, exist_ok=True)
    logger.info(f"Data directory ensured: {DATA_DIR}")
except PermissionError as e:
    logger.warning(f"Cannot create data directory {DATA_DIR}: {e}. Using current directory.")
    DATA_DIR = "."
except Exception as e:
    logger.error(f"Unexpected error creating data directory: {e}")
    DATA_DIR = "."

DATABASE_URL = f"sqlite:///{DATA_DIR}/werewolf.db"

# 创建数据库引擎
# P1-STAB-002 Fix: Use IMMEDIATE isolation level for SQLite to prevent
# write conflicts in concurrent transactions
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # SQLite特有配置
    echo=False  # 设为True可查看SQL日志
)


# P1-STAB-002: Set SQLite to use IMMEDIATE transaction mode
# This acquires a write lock at the start of the transaction, preventing
# "database is locked" errors during concurrent writes
@event.listens_for(engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Configure SQLite connection for better concurrency handling."""
    cursor = dbapi_connection.cursor()
    # Enable WAL mode for better concurrent read/write performance
    cursor.execute("PRAGMA journal_mode=WAL")
    # Set busy timeout to wait for locks instead of failing immediately
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


# 创建Session工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """
    依赖注入：获取数据库会话
    用法：
        @router.get("/api/rooms")
        def get_rooms(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
