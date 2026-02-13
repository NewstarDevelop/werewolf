"""Database initialization script."""
import os
import logging
from sqlalchemy import create_engine
from app.models.base import Base
from app.models import room, user, game_history  # Import all models to register with Base
from app.core.config import settings

logger = logging.getLogger(__name__)


def init_database():
    """创建数据库表（如果不存在）"""
    try:
        # 确保数据目录存在
        os.makedirs(settings.DATA_DIR, exist_ok=True)

        # Create a local sync engine for DDL only
        connect_args = {}
        if settings.DATABASE_URL.startswith("sqlite"):
            connect_args["check_same_thread"] = False
        engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)

        # 创建所有表
        Base.metadata.create_all(bind=engine)
        engine.dispose()

        logger.info("✅ Database initialized successfully")
        logger.info(f"   Database file: {settings.DATA_DIR}/werewolf.db")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise


if __name__ == "__main__":
    # 单独运行此脚本时初始化数据库
    logging.basicConfig(level=logging.INFO)
    init_database()
