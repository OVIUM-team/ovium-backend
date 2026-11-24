from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.animals import animals
from app.models.events import weanings, weights, weight_types
from app.routes.animals import animal_in_ranch
from app.routes.weights import today
from app.schemas.auth import SessionClaims
from app.schemas.weanings import WeaningCreate
from app.services.ranch_access import RanchPermission, database, require_ranch_access

router = APIRouter(prefix="/ranchos/{ranch_id}/animales/{animal_id}/destete", tags=["destetes"])


@router.get("", dependencies=[Depends(require_ranch_access(RanchPermission.READ))])
def read_weaning(ranch_id: UUID, animal_id: UUID, engine=Depends(database)):
    with engine.connect() as connection:
        if connection.scalar(select(animals.c.id).where(animal_in_ranch(ranch_id, animal_id))) is None:
            raise HTTPException(404, "Animal no encontrado")
        row = connection.execute(select(weanings).where(weanings.c.animal_id == str(animal_id))).mappings().one_or_none()
        if row is None:
            raise HTTPException(404, "Destete no registrado")
        return dict(row)


@router.post("", status_code=201)
def register_weaning(
    ranch_id: UUID, animal_id: UUID, data: WeaningCreate, engine=Depends(database),
    claims: SessionClaims = Depends(require_ranch_access(RanchPermission.CAPTURE)),
):
    try:
        with engine.begin() as connection:
            animal = connection.execute(select(animals).where(animal_in_ranch(ranch_id, animal_id))).mappings().one_or_none()
            if animal is None:
                raise HTTPException(404, "Animal no encontrado")
            if animal["estado"] != "activo":
                raise HTTPException(409, "El animal está dado de baja")
            if data.fecha > today() or (animal["fecha_nacimiento"] and data.fecha < animal["fecha_nacimiento"]):
                raise HTTPException(422, "Fecha de destete fuera del historial del animal")
            if data.pesaje_id:
                weight = connection.execute(
                    select(weights.c.fecha, weight_types.c.codigo).select_from(weights.join(weight_types))
                    .where(weights.c.id == str(data.pesaje_id), weights.c.animal_id == str(animal_id))
                ).one_or_none()
                if weight is None or weight.codigo != "destete" or weight.fecha != data.fecha:
                    raise HTTPException(422, "El pesaje debe ser de destete, del mismo animal y de la misma fecha")
            values = dict(id=str(data.id), animal_id=str(animal_id), fecha=data.fecha,
                          destino=data.destino, pesaje_id=str(data.pesaje_id) if data.pesaje_id else None,
                          registrado_por=claims.sub)
            connection.execute(weanings.insert().values(**values))
            return values
    except IntegrityError:
        raise HTTPException(409, "El destete o su identificador ya existe") from None
