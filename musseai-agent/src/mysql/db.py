from sqlalchemy import (
    create_engine,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.mysql import LONGTEXT
from contextlib import contextmanager
import os

# 数据库连接配置
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://asset_agent:asset_agent_123456@localhost:3307/crypto_portfolio",
)

# 创建数据库引擎
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=3600,
    pool_size=20,  # 增加到2wa
    max_overflow=30,  # 增加到30
    pool_timeout=30,  # 添加连接超时
    pool_reset_on_return="commit",  # 连接返回时重置
)

# 创建会话工厂
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 创建Base类
Base = declarative_base()


# 上下文管理器，用于获取数据库会话
@contextmanager
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
