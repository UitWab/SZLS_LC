from backend_db.config import settings
from backend_db.database.mysql import check_database_connection


def test_database_connection():
    """测试项目是否能够正常连接 MySQL 数据库。"""

    info = check_database_connection()

    assert settings.DB_NAME.endswith("_test")
    assert info["db_name"] == settings.DB_NAME
    assert info["version"].startswith("8.0.")
