from datetime import date, timedelta
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response

from app.models.animals import animals
from app.models.auth import ranches
from app.models.events import births, weaning_alerts
from app.services.ranch_access import RanchPermission, database, require_ranch_access
from app.services.weaning import pending_weanings

router = APIRouter(prefix="/ranchos/{ranch_id}/alertas/destete", tags=["destete"])


@router.get("", dependencies=[Depends(require_ranch_access(RanchPermission.READ))])
def list_weaning_alerts(ranch_id: UUID, engine=Depends(database)):
    today = date.today()
    alerts = []
    query = pending_weanings().where(
        ranches.c.id == str(ranch_id),
        weaning_alerts.select().where(weaning_alerts.c.parto_id == births.c.id).exists(),
    )
    with engine.connect() as connection:
        for birth in connection.execute(query).mappings():
            due = birth["fecha_parto"] + timedelta(days=birth["dias_lactancia"])
            if due <= today:
                alerts.append({
                    "parto_id": birth["parto_id"], "madre_id": birth["madre_id"], "fecha_destete": due,
                })
    return sorted(alerts, key=lambda alert: (alert["fecha_destete"], alert["parto_id"]))


@router.post(
    "/{birth_id}/confirmar",
    status_code=204,
    dependencies=[Depends(require_ranch_access(RanchPermission.EDIT))],
)
def confirm_weaning(ranch_id: UUID, birth_id: UUID, engine=Depends(database)):
    with engine.begin() as connection:
        pending = pending_weanings().where(ranches.c.id == str(ranch_id), births.c.id == str(birth_id))
        birth = connection.execute(pending).mappings().one_or_none()
        if birth is None:
            raise HTTPException(404, "Alerta de destete no encontrada")
        due = birth["fecha_parto"] + timedelta(days=birth["dias_lactancia"])
        if due > date.today():
            raise HTTPException(409, "Todavía no se cumple la fecha de destete")
        candidate = pending.with_only_columns(births.c.madre_id).where(
            ranches.c.dias_lactancia == birth["dias_lactancia"],
            births.c.fecha == birth["fecha_parto"],
        )
        result = connection.execute(
            animals.update().where(
                animals.c.id.in_(candidate), animals.c.estado_reproductivo == "lactancia",
            ).values(estado_reproductivo="mantenimiento")
        )
        if not result.rowcount:
            raise HTTPException(409, "La alerta cambió antes de confirmarse")
    return Response(status_code=204)
