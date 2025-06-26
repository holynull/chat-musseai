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
    pool_pre_ping=True,  # 自动检测连接是否有效
    pool_recycle=3600,  # 一小时后回收连接
    pool_size=5,  # 连接池大小
    max_overflow=10,  # 最大溢出连接数
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
