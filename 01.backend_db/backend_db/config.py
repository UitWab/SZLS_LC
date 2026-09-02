import os
from pathlib import Path
from urllib.parse import quote_plus

from dotenv import load_dotenv


# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# 加载项目根目录下的 .env
load_dotenv(BASE_DIR / ".env")


class Settings:
    """数据库基础配置"""

    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_USER = os.getenv("DB_USER")
    DB_PASSWORD = os.getenv("DB_PASSWORD")
    DB_NAME = os.getenv("DB_NAME")

    @property
    def database_url(self) -> str:
        """
        生成 SQLAlchemy 使用的 MySQL 连接地址。
        quote_plus 用于避免密码中存在 @、# 等特殊字符时连接失败。
        """
        password = quote_plus(self.DB_PASSWORD or "")

        return (
            f"mysql+pymysql://"
            f"{self.DB_USER}:{password}"
            f"@{self.DB_HOST}:{self.DB_PORT}"
            f"/{self.DB_NAME}"
            f"?charset=utf8mb4"
        )


settings = Settings()