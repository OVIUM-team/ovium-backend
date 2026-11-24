from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.animals import animals
from app.models.events import weight_types, weights
from app.schemas.auth import SessionClaims
from app.services.ranch_access import RanchPermission, database, require_ranch_access

router = APIRouter(prefix="/ranchos/{ranch_id}/animales/{animal_id}/pesajes", tags=["pesajes"])
TypeCode = Literal["nacimiento", "destete", "120_d", "150_d", "evaluacion"]


class WeightData(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    fecha: date
    tipo: TypeCode
    peso: Decimal = Field(gt=0, max_digits=8, decimal_places=2)
    peso_evaluacion: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)
    circunferencia_testicular: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)


def today() -> date:
    return datetime.now(ZoneInfo("America/Mexico_City")).date()


def age_at(birth: date | None, target: date):
    if birth is None or target < birth:
        return None
    months = (target.year - birth.year) * 12 + target.month - birth.month

    def anniversary(count):
        year, month = divmod(birth.year * 12 + birth.month - 1 + count, 12)
        return date(year, month + 1, min(birth.day, monthrange(year, month + 1)[1]))

    if anniversary(months) > target:
        months -= 1
    return {"meses": months, "dias": (target - anniversary(months)).days}


def animal_birth(connection, ranch_id, animal_id):
    row = connection.execute(select(animals.c.fecha_nacimiento).where(
        animals.c.id == str(animal_id), animals.c.rancho_id == str(ranch_id)
    )).one_or_none()
    if row is None:
        raise HTTPException(404, "Animal no encontrado")
    return row.fecha_nacimiento


def history(connection, animal_id, birth):
    rows = connection.execute(
        select(weights.c.id, weights.c.fecha, weights.c.peso, weights.c.peso_evaluacion,
               weights.c.circunferencia_testicular, weight_types.c.codigo.label("tipo"))
        .select_from(weights.join(weight_types))
        .where(weights.c.animal_id == str(animal_id))
        .order_by(weights.c.fecha, weights.c.id)
    ).mappings()
    result = []
    previous_day = current_day = None
    for row in rows:
        if current_day is None or row["fecha"] > current_day["fecha"]:
            previous_day, current_day = current_day, row
        gain = None
        if previous_day is not None:
            days = (row["fecha"] - previous_day["fecha"]).days
            gain = ((row["peso"] - previous_day["peso"]) / days).quantize(
                Decimal("0.0001"), rounding=ROUND_HALF_UP
            )
        result.append({**row, "edad_al_pesaje": age_at(birth, row["fecha"]), "gdp_kg_dia": gain})
    return result


@router.get("", dependencies=[Depends(require_ranch_access(RanchPermission.READ))])
def list_weights(ranch_id: UUID, animal_id: UUID, engine=Depends(database)):
    with engine.connect() as connection:
        birth = animal_birth(connection, ranch_id, animal_id)
        return {"edad_actual": age_at(birth, today()), "pesajes": history(connection, animal_id, birth)}


@router.post("", status_code=201)
def register_weight(
    ranch_id: UUID, animal_id: UUID, data: WeightData, engine=Depends(database),
    claims: SessionClaims = Depends(require_ranch_access(RanchPermission.CAPTURE)),
):
    try:
        with engine.begin() as connection:
            birth = animal_birth(connection, ranch_id, animal_id)
            if data.fecha > today() or (birth is not None and data.fecha < birth):
                raise HTTPException(422, "Fecha de pesaje fuera del historial del animal")
            if data.tipo == "nacimiento" and birth is not None and data.fecha != birth:
                raise HTTPException(422, "El pesaje de nacimiento debe coincidir con la fecha de nacimiento")
            kind = connection.scalar(select(weight_types.c.id).where(weight_types.c.codigo == data.tipo))
            if kind is None:
                raise HTTPException(503, "Tipo de pesaje no configurado en el catálogo")
            connection.execute(weights.insert().values(
                id=str(data.id), animal_id=str(animal_id), tipo_pesaje_id=kind, registrado_por=claims.sub,
                **data.model_dump(exclude={"id", "tipo"}),
            ))
            return next(item for item in history(connection, animal_id, birth) if item["id"] == str(data.id))
    except IntegrityError:
        raise HTTPException(409, "El identificador de pesaje ya existe o la referencia es inválida") from None
