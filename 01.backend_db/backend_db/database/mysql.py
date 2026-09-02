from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from backend_db.config import settings


# 创建数据库引擎
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    echo=False,
)


# 创建数据库会话工厂
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


def check_database_connection():
    """测试 MySQL 数据库连接是否正常"""

    with engine.connect() as connection:
        result = connection.execute(
            text(
                """
                SELECT
                    DATABASE() AS db_name,
                    VERSION() AS version
                """
            )
        ).mappings().one()

        return {
            "db_name": result["db_name"],
            "version": result["version"],
        }