from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.animals import animals, identifiers, removals
from app.schemas.auth import SessionClaims
from app.services.ranch_access import RanchPermission, database, require_ranch_access

router = APIRouter(prefix="/ranchos/{ranch_id}/animales", tags=["animales"])


class Identifier(BaseModel):
    tipo: Literal["folio", "arete", "SINIIGA", "folio UNO"]
    valor: str = Field(min_length=1, max_length=255)


class AnimalData(BaseModel):
    madre_id: UUID | None = None
    padre_id: UUID | None = None
    raza_id: UUID | None = None
    sexo: str = Field(min_length=1, max_length=32)
    fecha_nacimiento: date | None = None
    etapa_vida: str | None = Field(default=None, max_length=64)
    estado_reproductivo: str | None = Field(default=None, max_length=64)
    criador: str | None = Field(default=None, max_length=255)
    propietario: str | None = Field(default=None, max_length=255)
    circunferencia_testicular: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    identificadores: list[Identifier] = Field(default_factory=list, max_length=20)


class AnimalCreate(AnimalData):
    id: UUID = Field(default_factory=uuid4)


class RemovalData(BaseModel):
    fecha: date
    motivo: str = Field(min_length=1, max_length=255)


def animal_in_ranch(ranch_id: UUID, animal_id: UUID):
    return (animals.c.rancho_id == str(ranch_id)) & (animals.c.id == str(animal_id))


def animal_details(connection, ranch_id: UUID, animal_id: UUID):
    row = connection.execute(select(animals).where(animal_in_ranch(ranch_id, animal_id))).mappings().one_or_none()
    if row is None:
        raise HTTPException(404, "Animal no encontrado")
    result = dict(row)
    result["identificadores"] = [
        dict(identifier)
        for identifier in connection.execute(
            select(identifiers.c.tipo, identifiers.c.valor).where(identifiers.c.animal_id == row["id"])
        ).mappings()
    ]
    for name in ("madre", "padre"):
        parent_id = row[f"{name}_id"]
        parent = None
        if parent_id:
            parent = connection.execute(
                select(animals.c.id, animals.c.sexo, animals.c.criador, animals.c.propietario)
                .where(animal_in_ranch(ranch_id, parent_id))
            ).mappings().one_or_none()
        result[name] = dict(parent) if parent else None
        result[f"{name}_id"] = parent["id"] if parent else None
    return result


def save_animal(connection, ranch_id: UUID, animal_id: UUID, data: AnimalData, *, create: bool):
    values = data.model_dump(exclude={"id", "identificadores"})
    for field in ("madre_id", "padre_id", "raza_id"):
        if values[field]:
            values[field] = str(values[field])
    for parent_id in (data.madre_id, data.padre_id):
        if parent_id and (
            parent_id == animal_id
            or not connection.scalar(select(animals.c.id).where(animal_in_ranch(ranch_id, parent_id)))
        ):
            raise HTTPException(422, "La madre y el padre deben ser otros animales registrados en el rancho")
    if create:
        connection.execute(animals.insert().values(id=str(animal_id), rancho_id=str(ranch_id), estado="activo", **values))
    else:
        changed = connection.execute(animals.update().where(animal_in_ranch(ranch_id, animal_id)).values(**values))
        if not changed.rowcount:
            raise HTTPException(404, "Animal no encontrado")
        connection.execute(identifiers.delete().where(identifiers.c.animal_id == str(animal_id)))
    if data.identificadores:
        connection.execute(identifiers.insert(), [
            {"id": str(uuid4()), "animal_id": str(animal_id), **item.model_dump()}
            for item in data.identificadores
        ])


@router.get("", dependencies=[Depends(require_ranch_access(RanchPermission.READ))])
def list_animals(
    ranch_id: UUID, sexo: str | None = None, raza_id: UUID | None = None,
    estado: Literal["activo", "baja"] | None = None, engine=Depends(database),
):
    # Return inventory summaries. Details include identifiers and parents.
    query = select(animals.c.id, animals.c.sexo, animals.c.raza_id, animals.c.estado, animals.c.fecha_nacimiento)
    query = query.where(animals.c.rancho_id == str(ranch_id)).order_by(animals.c.id)
    for column, value in ((animals.c.sexo, sexo), (animals.c.raza_id, str(raza_id) if raza_id else None),
                          (animals.c.estado, estado)):
        if value is not None:
            query = query.where(column == value)
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(query).mappings()]


@router.post("", status_code=201, dependencies=[Depends(require_ranch_access(RanchPermission.CAPTURE))])
def create_animal(ranch_id: UUID, data: AnimalCreate, engine=Depends(database)):
    animal_id = data.id
    try:
        with engine.begin() as connection:
            save_animal(connection, ranch_id, animal_id, data, create=True)
            return animal_details(connection, ranch_id, animal_id)
    except IntegrityError:
        raise HTTPException(409, "Identificador en uso o referencia de animal inválida") from None


@router.get("/{animal_id}", dependencies=[Depends(require_ranch_access(RanchPermission.READ))])
def read_animal(ranch_id: UUID, animal_id: UUID, engine=Depends(database)):
    with engine.connect() as connection:
        return animal_details(connection, ranch_id, animal_id)


@router.put("/{animal_id}", dependencies=[Depends(require_ranch_access(RanchPermission.EDIT))])
def update_animal(ranch_id: UUID, animal_id: UUID, data: AnimalData, engine=Depends(database)):
    try:
        with engine.begin() as connection:
            save_animal(connection, ranch_id, animal_id, data, create=False)
            return animal_details(connection, ranch_id, animal_id)
    except IntegrityError:
        raise HTTPException(409, "Identificador en uso o referencia de animal inválida") from None


@router.post("/{animal_id}/baja", status_code=201)
def remove_animal(
    ranch_id: UUID, animal_id: UUID, data: RemovalData, engine=Depends(database),
    claims: SessionClaims = Depends(require_ranch_access(RanchPermission.EDIT)),
):
    with engine.begin() as connection:
        result = connection.execute(animals.update().where(
            animal_in_ranch(ranch_id, animal_id), animals.c.estado == "activo",
        ).values(estado="baja"))
        if not result.rowcount:
            animal_details(connection, ranch_id, animal_id)
            raise HTTPException(409, "El animal ya está dado de baja")
        values = {"id": str(uuid4()), "animal_id": str(animal_id), "registrada_por": claims.sub, **data.model_dump()}
        connection.execute(removals.insert().values(**values))
    return values
