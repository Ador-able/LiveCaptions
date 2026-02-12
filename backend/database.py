from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

# 数据库连接 URL
# 默认使用 SQLite，存储在 user-mounted data volume 中
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////data/tasks.db")

# 创建数据库引擎
# check_same_thread=False 仅用于 SQLite，允许在多线程中使用同一个连接
engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

# 创建会话工厂
# autocommit=False: 禁止自动提交，需要手动 commit，确保事务安全性
# autoflush=False: 禁止自动刷新，需要手动 flush
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 声明式基类，所有模型都继承自此类
Base = declarative_base()

def get_db():
    """
    获取数据库会话生成器。
    用于 FastAPI 的 Dependency Injection (依赖注入)。

    Yields:
        Session: SQLAlchemy 数据库会话

    Usage:
        def my_endpoint(db: Session = Depends(get_db)):
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
