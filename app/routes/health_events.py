from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.animals import animals
from app.models.events import health_events
from app.routes.weights import today
from app.schemas.auth import SessionClaims
from app.schemas.health_events import HealthBatch, HealthCreate, HealthTarget, HealthType
from app.services.ranch_access import RanchPermission, database, require_ranch_access

router = APIRouter(prefix="/ranchos/{ranch_id}", tags=["eventos sanitarios"])


def save_events(connection, ranch_id, data, targets, responsible):
    if data.fecha > today():
        raise HTTPException(422, "La fecha no puede ser futura")
    ids = [str(item.animal_id) for item in targets]
    rows = connection.execute(select(animals.c.id, animals.c.fecha_nacimiento, animals.c.estado).where(
        animals.c.rancho_id == str(ranch_id), animals.c.id.in_(ids),
    )).mappings().all()
    if len(rows) != len(ids):
        raise HTTPException(404, "Uno o más animales no pertenecen al rancho")
    if any(row["estado"] != "activo" for row in rows):
        raise HTTPException(409, "No se pueden registrar eventos en animales dados de baja")
    if any(row["fecha_nacimiento"] and data.fecha < row["fecha_nacimiento"] for row in rows):
        raise HTTPException(422, "La fecha es anterior al nacimiento de un animal")
    common = data.model_dump(exclude={"id", "animales"})
    values = [dict(id=str(item.id), animal_id=str(item.animal_id), responsable_id=responsible, **common)
              for item in targets]
    connection.execute(health_events.insert(), values)
    return values


@router.post("/animales/{animal_id}/eventos-sanitarios", status_code=201)
def register_health_event(
    ranch_id: UUID, animal_id: UUID, data: HealthCreate, engine=Depends(database),
    claims: SessionClaims = Depends(require_ranch_access(RanchPermission.CAPTURE)),
):
    try:
        with engine.begin() as connection:
            return save_events(connection, ranch_id, data, [HealthTarget(animal_id=animal_id, id=data.id)], claims.sub)[0]
    except IntegrityError:
        raise HTTPException(409, "El identificador de evento ya existe o la referencia es inválida") from None


@router.post("/eventos-sanitarios/lote", status_code=201)
def register_health_batch(
    ranch_id: UUID, data: HealthBatch, engine=Depends(database),
    claims: SessionClaims = Depends(require_ranch_access(RanchPermission.CAPTURE)),
):
    try:
        with engine.begin() as connection:
            return save_events(connection, ranch_id, data, data.animales, claims.sub)
    except IntegrityError:
        raise HTTPException(409, "Un identificador de evento ya existe; no se guardó el lote") from None


@router.get("/animales/{animal_id}/eventos-sanitarios", dependencies=[Depends(require_ranch_access(RanchPermission.READ))])
def health_history(
    ranch_id: UUID, animal_id: UUID, tipo: HealthType | None = None,
    desde: date | None = None, hasta: date | None = None, engine=Depends(database),
):
    if desde and hasta and desde > hasta:
        raise HTTPException(422, "El inicio del periodo no puede ser posterior al final")
    with engine.connect() as connection:
        if connection.scalar(select(animals.c.id).where(
            animals.c.id == str(animal_id), animals.c.rancho_id == str(ranch_id),
        )) is None:
            raise HTTPException(404, "Animal no encontrado")
        query = select(health_events).where(health_events.c.animal_id == str(animal_id))
        if tipo:
            query = query.where(health_events.c.tipo == tipo)
        if desde:
            query = query.where(health_events.c.fecha >= desde)
        if hasta:
            query = query.where(health_events.c.fecha <= hasta)
        return [dict(row) for row in connection.execute(query.order_by(health_events.c.fecha, health_events.c.id)).mappings()]
