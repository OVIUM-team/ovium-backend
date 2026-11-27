from datetime import date
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.models.animals import animals, removals
from app.services.ranch_access import RanchPermission, database, require_ranch_access

router = APIRouter(prefix="/ranchos/{ranch_id}/bajas", tags=["bajas"])


@router.get("", dependencies=[Depends(require_ranch_access(RanchPermission.READ))])
def list_removals(ranch_id: UUID, motivo: Literal["muerte", "venta", "desecho"] | None = None,
                  desde: date | None = None, hasta: date | None = None, engine=Depends(database)):
    if desde and hasta and desde > hasta:
        raise HTTPException(422, "Periodo inválido")
    query = select(removals).join(animals).where(animals.c.rancho_id == str(ranch_id))
    if motivo:
        query = query.where(removals.c.motivo == motivo)
    if desde:
        query = query.where(removals.c.fecha >= desde)
    if hasta:
        query = query.where(removals.c.fecha <= hasta)
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(query.order_by(removals.c.fecha, removals.c.id)).mappings()]
