from functools import lru_cache

from sqlalchemy import Boolean, CheckConstraint, Column, ForeignKey, Integer, MetaData, String, Table, UniqueConstraint, Uuid, create_engine, select

metadata = MetaData()
uuid = Uuid(as_uuid=False)
accounts = Table(
    "usuario", metadata,
    Column("id", uuid, primary_key=True),
    Column("nombre", String(255), nullable=False),
    Column("email", String(255), unique=True, nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("tipo", String(64), nullable=False),
)
ranches = Table(
    "rancho", metadata,
    Column("id", uuid, primary_key=True),
    Column("nombre", String(255), nullable=False),
    Column("domicilio", String(255)),
    Column("propietario_id", ForeignKey("usuario.id"), nullable=False, unique=True),
    Column("dias_lactancia", Integer, nullable=False, server_default="75"),
    CheckConstraint("dias_lactancia IN (60,75,90)", name="ck_rancho_dias_lactancia"),
)
account_ranches = Table(
    "usuario_rancho", metadata,
    Column("id", uuid, primary_key=True),
    Column("usuario_id", ForeignKey("usuario.id"), nullable=False),
    Column("rancho_id", ForeignKey("rancho.id"), nullable=False),
    Column("rol", String(64), nullable=False),
    Column("puede_leer", Boolean, nullable=False, server_default="0"),
    Column("puede_capturar", Boolean, nullable=False, server_default="0"),
    Column("puede_editar", Boolean, nullable=False, server_default="0"),
    Column("puede_exportar", Boolean, nullable=False, server_default="0"),
    UniqueConstraint("usuario_id", "rancho_id"),
)


@lru_cache(maxsize=1)
def auth_engine(database_url: str):
    return create_engine(database_url, pool_pre_ping=True, hide_parameters=True)


def find_account(database_url: str, username: str):
    with auth_engine(database_url).connect() as connection:
        account = connection.execute(select(accounts).where(accounts.c.email == username)).mappings().one_or_none()
        if not account:
            return None
        memberships = connection.execute(
            select(account_ranches).where(account_ranches.c.usuario_id == account["id"])
        ).mappings().all()
        role = account["tipo"]
        if any(member["rol"] == "rama" for member in memberships):
            role = "rama"
            memberships = [member for member in memberships if member["rol"] == "rama"]
        ranch_ids = {member["rancho_id"] for member in memberships}
        if role == "productor":
            ranch_ids = set(connection.scalars(select(ranches.c.id).where(ranches.c.propietario_id == account["id"])))
        elif role == "asociacion":
            ranch_ids = set(connection.scalars(select(ranches.c.id)))
        return account["id"], account["password_hash"], role, sorted(ranch_ids)
