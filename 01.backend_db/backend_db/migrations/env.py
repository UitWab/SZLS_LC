from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend_db.config import settings
from backend_db.models import Base


# Alembic 配置对象
config = context.config


# 从 .env / config.py 获取数据库连接地址
# Alembic 配置内部会把 % 当作特殊字符，所以需要转义
database_url = settings.database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", database_url)


# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)


# ORM 元数据
# 以后 Alembic 会根据这里识别 Beam、Device 等模型
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """离线迁移模式。"""

    url = config.get_main_option("sqlalchemy.url")

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """在线迁移模式。"""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()