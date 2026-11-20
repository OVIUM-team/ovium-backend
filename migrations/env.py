from alembic import context
from sqlalchemy import create_engine, pool

from app.config import Settings
from app.models import metadata

config = context.config
target_metadata = metadata


def configure(connection=None, url=None):
    context.configure(
        connection=connection, url=url, target_metadata=target_metadata,
        literal_binds=connection is None, compare_type=True,
        render_as_batch=connection is not None and connection.dialect.name == "sqlite",
    )
    with context.begin_transaction():
        context.run_migrations()


if config.attributes.get("connection") is not None:
    configure(connection=config.attributes["connection"])
else:
    url = config.get_main_option("sqlalchemy.url") or Settings().database_url
    if not url:
        raise RuntimeError("Configura DATABASE_URL para ejecutar las migraciones")
    if context.is_offline_mode():
        configure(url=url)
    else:
        engine = create_engine(url, poolclass=pool.NullPool, hide_parameters=True)
        with engine.connect() as connection:
            configure(connection=connection)
        engine.dispose()
