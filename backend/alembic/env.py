from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

from app.core.config import get_settings
from app.core.database_url import build_database_engine_config
from app.db.base import Base
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def _database_config():
    return build_database_engine_config(get_settings())


def run_migrations_offline() -> None:
    database_config = _database_config()
    context.configure(
        url=database_config.safe_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    database_config = _database_config()
    engine_args = {
        **database_config.engine_args,
        "poolclass": pool.NullPool,
    }
    engine_args.pop("pool_size", None)
    engine_args.pop("max_overflow", None)
    connectable = create_engine(
        database_config.url,
        connect_args=database_config.connect_args,
        **engine_args,
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
