from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.animals import animals
from app.models.events import births, birth_offspring, weanings, weights, weight_types
from app.routes.animals import animal_in_ranch
from app.routes.weights import today
from app.schemas.auth import SessionClaims
from app.schemas.weanings import WeaningCreate
from app.services.ranch_access import RanchPermission, database, require_ranch_access

router = APIRouter(prefix="/ranchos/{ranch_id}/animales/{animal_id}/destete", tags=["destetes"])


def finish_lactation(connection, ranch_id, animal):
    birth = connection.execute(select(births).join(birth_offspring, birth_offspring.c.parto_id == births.c.id)
                               .where(birth_offspring.c.animal_id == animal["id"])).mappings().one_or_none()
    mother_id = birth["madre_id"] if birth else animal["madre_id"]
    if not mother_id:
        return
    # Serialize sibling confirmations against the mother's row (SQL Server).
    connection.execute(animals.update().where(animal_in_ranch(ranch_id, mother_id)).values(
        estado_reproductivo=animals.c.estado_reproductivo))
    latest = connection.execute(select(births).where(births.c.madre_id == mother_id)
                                .order_by(births.c.fecha.desc(), births.c.fecha_captura.desc(), births.c.id.desc())).mappings().first()
    if latest:
        if birth is None or birth["id"] != latest["id"]:
            return  # A historical weaning must not end a newer lactation.
        siblings = select(animals.c.id).join(birth_offspring, birth_offspring.c.animal_id == animals.c.id).where(
            birth_offspring.c.parto_id == latest["id"], birth_offspring.c.viva.is_(True))
    else:
        siblings = select(animals.c.id).where(animals.c.madre_id == mother_id)
    pending = siblings.where(animals.c.rancho_id == str(ranch_id), animals.c.estado == "activo",
                             ~select(weanings.c.id).where(weanings.c.animal_id == animals.c.id).exists())
    if connection.execute(pending).first() is None:
        connection.execute(animals.update().where(animal_in_ranch(ranch_id, mother_id),
                           animals.c.estado == "activo", animals.c.estado_reproductivo == "lactancia")
                           .values(estado_reproductivo="mantenimiento"))


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
                weight_id = str(data.pesaje_id)
            else:
                kind = connection.scalar(select(weight_types.c.id).where(weight_types.c.codigo == "destete"))
                if kind is None:
                    raise HTTPException(503, "Tipo de pesaje de destete no configurado")
                weight_id = str(uuid4())
                connection.execute(weights.insert().values(id=weight_id, animal_id=str(animal_id), fecha=data.fecha,
                                   tipo_pesaje_id=kind, peso=data.peso, registrado_por=claims.sub))
            values = dict(id=str(data.id), animal_id=str(animal_id), fecha=data.fecha,
                          destino=data.destino, pesaje_id=weight_id,
                          registrado_por=claims.sub)
            connection.execute(weanings.insert().values(**values))
            finish_lactation(connection, ranch_id, animal)
            return values
    except IntegrityError:
        raise HTTPException(409, "El destete o su identificador ya existe") from None
