import os


DEFAULT_TEST_DB_NAME = "smart_beam_twin_test"


def _configure_test_database() -> None:
    """强制测试连接独立测试库，防止误写开发库或生产库。"""

    database_name = os.getenv(
        "TEST_DB_NAME",
        DEFAULT_TEST_DB_NAME,
    ).strip()

    if not database_name.endswith("_test"):
        raise RuntimeError(
            "TEST_DB_NAME 必须以 '_test' 结尾，已拒绝启动测试。"
        )

    os.environ["DB_NAME"] = database_name


_configure_test_database()
