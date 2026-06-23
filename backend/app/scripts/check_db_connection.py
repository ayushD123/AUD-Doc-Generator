from app.services.db_health import (
    build_connection_diagnostics,
    check_database_connection,
    create_health_check_engine,
)
from app.core.config import get_settings


def main() -> int:
    database_config, diagnostics = build_connection_diagnostics()
    settings = get_settings()
    engine = create_health_check_engine(database_config)
    try:
        result = check_database_connection(
            engine,
            database_config.provider,
            secrets=(settings.ORACLE_DB_PASSWORD, settings.ORACLE_DB_WALLET_PASSWORD),
        )
        print(f"provider: {diagnostics['provider']}")
        print(f"dialect: {engine.dialect.name}")
        print(f"url: {diagnostics['sanitized_url']}")
        print(f"dsn: {diagnostics['dsn'] or ''}")
        print(f"wallet_dir_exists: {diagnostics['wallet_dir_exists']}")
        print(f"can_connect: {result['can_connect']}")
        print(f"status: {result['status']}")
        print(f"message: {result['message']}")
        return 0 if result["can_connect"] else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
