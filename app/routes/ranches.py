from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.auth import account_ranches, accounts, ranches
from app.routes.auth import AuthRoute, authenticated_session
from app.schemas.auth import SessionClaims
from app.services.auth import password_hasher
from app.services.ranch_access import RanchPermission, database, ranch_access_filter, require_ranch_access

router = APIRouter(prefix="/ranchos", tags=["ranchos"], route_class=AuthRoute)


class RanchData(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    domicilio: str | None = Field(default=None, max_length=255)
    dias_lactancia: int = Field(default=75, ge=1)


class BranchData(BaseModel):
    nombre: str = Field(min_length=1, max_length=255)
    email: str = Field(min_length=1, max_length=255)
    password: SecretStr = Field(min_length=12, max_length=1024)
    puede_leer: bool = False
    puede_capturar: bool = False
    puede_editar: bool = False
    puede_exportar: bool = False


@router.get("")
def list_ranches(claims: SessionClaims = Depends(authenticated_session), engine=Depends(database)):
    scope = ranch_access_filter(claims.sub, claims.role, RanchPermission.READ)
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(select(ranches).where(scope)).mappings()]


@router.post("", status_code=201)
def create_ranch(data: RanchData, claims: SessionClaims = Depends(authenticated_session), engine=Depends(database)):
    values = {"id": str(uuid4()), "propietario_id": claims.sub, **data.model_dump()}
    if claims.role != "productor":
        raise HTTPException(403, "Solo un productor puede dar de alta su rancho")
    try:
        with engine.begin() as connection:
            role = connection.scalar(select(accounts.c.tipo).where(accounts.c.id == claims.sub))
            is_branch = connection.scalar(select(account_ranches.c.id).where(
                account_ranches.c.usuario_id == claims.sub, account_ranches.c.rol == "rama"
            ).limit(1))
            if role != "productor" or is_branch:
                raise HTTPException(403, "Solo un productor puede dar de alta su rancho")
            connection.execute(ranches.insert().values(**values))
    except IntegrityError:
        raise HTTPException(409, "El productor ya tiene un rancho") from None
    return values


@router.put("/{ranch_id}", dependencies=[Depends(require_ranch_access(RanchPermission.EDIT))])
def update_ranch(ranch_id: UUID, data: RanchData, engine=Depends(database)):
    with engine.begin() as connection:
        result = connection.execute(ranches.update().where(ranches.c.id == str(ranch_id)).values(**data.model_dump()))
        if not result.rowcount:
            raise HTTPException(404, "Rancho no encontrado")
    return {"id": str(ranch_id), **data.model_dump()}


@router.post("/{ranch_id}/ramas", status_code=201)
def create_branch(
    ranch_id: UUID, data: BranchData, claims: SessionClaims = Depends(authenticated_session), engine=Depends(database)
):
    if claims.role != "productor":
        raise HTTPException(403, "Solo el dueño puede crear subcuentas")
    password_hash = password_hasher.hash(data.password.get_secret_value())
    account_id = str(uuid4())
    grants = data.model_dump(include={"puede_leer", "puede_editar", "puede_capturar", "puede_exportar"})
    try:
        with engine.begin() as connection:
            owned_ranch = select(ranches.c.id).where(
                ranches.c.id == str(ranch_id),
                ranch_access_filter(claims.sub, claims.role, RanchPermission.EDIT),
            )
            if not connection.scalar(owned_ranch):
                raise HTTPException(403, "Solo el dueño puede crear subcuentas")
            connection.execute(accounts.insert().values(
                id=account_id, nombre=data.nombre, email=data.email, password_hash=password_hash, tipo="productor",
            ))
            connection.execute(account_ranches.insert().values(
                id=str(uuid4()), usuario_id=account_id, rancho_id=str(ranch_id), rol="rama", **grants,
            ))
    except IntegrityError:
        raise HTTPException(409, "No se pudo crear la subcuenta con ese correo") from None
    return {"id": account_id, "email": data.email, **grants}
