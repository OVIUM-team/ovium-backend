from functools import lru_cache

from sqlalchemy import Boolean, Column, ForeignKey, MetaData, String, Table, create_engine, select

metadata = MetaData()
accounts = Table(
    "auth_accounts",
    metadata,
    Column("id", String(64), primary_key=True),
    Column("username", String(255), unique=True, nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("role", String(64), nullable=False),
)
account_ranches = Table(
    "auth_account_ranches",
    metadata,
    Column("account_id", ForeignKey("auth_accounts.id"), primary_key=True),
    Column("ranch_id", String(64), primary_key=True),
    Column("can_read", Boolean, nullable=False, server_default="0"),
    Column("can_capture", Boolean, nullable=False, server_default="0"),
    Column("can_edit", Boolean, nullable=False, server_default="0"),
    Column("can_export", Boolean, nullable=False, server_default="0"),
)


@lru_cache(maxsize=1)
def auth_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, hide_parameters=True)


def find_account(database_url: str, username: str):
    query = (
        select(accounts.c.id, accounts.c.password_hash, accounts.c.role, account_ranches.c.ranch_id)
        .select_from(accounts.outerjoin(account_ranches))
        .where(accounts.c.username == username)
        .order_by(account_ranches.c.ranch_id)
    )
    with auth_engine(database_url).connect() as connection:
        rows = connection.execute(query).all()
    if not rows:
        return None
    account = rows[0]
    return account.id, account.password_hash, account.role, [
        row.ranch_id for row in rows if row.ranch_id is not None
    ]


def find_ranch_access(database_url: str, account_id: str, ranch_id: str):
    query = (
        select(
            accounts.c.role,
            account_ranches.c.can_read,
            account_ranches.c.can_capture,
            account_ranches.c.can_edit,
            account_ranches.c.can_export,
        )
        .select_from(accounts.join(account_ranches))
        .where(accounts.c.id == account_id, account_ranches.c.ranch_id == ranch_id)
    )
    with auth_engine(database_url).connect() as connection:
        return connection.execute(query).mappings().one_or_none()
