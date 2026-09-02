from backend_db.database.mysql import check_database_connection


def test_database_connection():
    """测试项目是否能够正常连接 MySQL 数据库。"""

    info = check_database_connection()

    assert info["db_name"] == "smart_beam_twin_dev"
    assert info["version"].startswith("8.0.")