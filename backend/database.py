"""
数据库连接配置

从 config 模块获取数据库配置，确保所有模块使用相同的数据库连接。
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from pathlib import Path

from .config import DATABASE_URL, BASE_DIR

# 通用的 SQLite 路径处理逻辑
if DATABASE_URL.startswith("sqlite://"):
    # 提取路径部分
    if DATABASE_URL.startswith("sqlite:///"):
        db_path_str = DATABASE_URL[len("sqlite:///"):]
    else:
        db_path_str = DATABASE_URL[len("sqlite://"):]
    
    db_path = Path(db_path_str)
    
    # 如果是相对路径，相对于 BASE_DIR 解析
    if not db_path.is_absolute():
        db_path = (BASE_DIR / db_path).resolve()
    
    # 确保目录存在
    if not db_path.parent.exists():
        db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 更新 DATABASE_URL 为绝对路径
    DATABASE_URL = f"sqlite:///{db_path}"
else:
    # 对于其他数据库类型，确保默认目录存在
    default_db_path = BASE_DIR / "data" / "tasks.db"
    if not default_db_path.parent.exists():
        default_db_path.parent.mkdir(parents=True, exist_ok=True)

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
