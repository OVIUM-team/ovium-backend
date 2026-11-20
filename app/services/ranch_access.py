from enum import Enum
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from sqlalchemy import false, select, true
from sqlalchemy.exc import SQLAlchemyError

from app.models.auth import account_ranches, accounts, auth_engine, ranches
from app.routes.auth import authenticated_session
from app.schemas.auth import SessionClaims


class RanchPermission(str, Enum):
    READ = "puede_leer"
    CAPTURE = "puede_capturar"
    EDIT = "puede_editar"
    EXPORT = "puede_exportar"


def database(request: Request):
    url = request.app.state.settings.database_url
    if not url:
        raise HTTPException(503, "Base de datos no configurada")
    try:
        return auth_engine(url)
    except (SQLAlchemyError, ImportError):
        raise HTTPException(503, "Base de datos no disponible") from None


def ranch_access_filter(account_id: str, role: str, permission: RanchPermission):
    account = select(accounts.c.id).where(accounts.c.id == account_id)
    member = select(account_ranches.c.id).where(
        account_ranches.c.usuario_id == account_id,
        account_ranches.c.rancho_id == ranches.c.id,
    )
    if role == "productor":
        return (ranches.c.propietario_id == account_id) & account.where(accounts.c.tipo == "productor").exists()
    if role in {"asociacion", "tecnico"} and permission not in {RanchPermission.READ, RanchPermission.EXPORT}:
        return false()
    if role == "asociacion":
        return account.where(accounts.c.tipo == "asociacion").exists()
    if role == "tecnico":
        return account.where(accounts.c.tipo == "tecnico").exists() & member.where(account_ranches.c.rol == "tecnico").exists()
    if role == "rama":
        return member.where(account_ranches.c.rol == "rama", account_ranches.c[permission.value] == true()).exists()
    raise HTTPException(403, "Rol sin acceso al rancho")


def require_ranch_access(permission: RanchPermission):
    def check_access(
        ranch_id: UUID, claims: SessionClaims = Depends(authenticated_session), engine=Depends(database)
    ) -> SessionClaims:
        query = select(ranches.c.id).where(
            ranches.c.id == str(ranch_id), ranch_access_filter(claims.sub, claims.role, permission)
        )
        try:
            with engine.connect() as connection:
                allowed = connection.scalar(query) is not None
        except SQLAlchemyError:
            raise HTTPException(503, "Autorización no disponible") from None
        if not allowed:
            raise HTTPException(403, "Sin permiso para este rancho")
        return claims

    return check_access
