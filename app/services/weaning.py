import asyncio
import logging
from contextlib import asynccontextmanager, suppress
from datetime import date, timedelta

from sqlalchemy import and_, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.models.animals import animals
from app.models.auth import auth_engine, ranches
from app.models.events import birth_offspring, births, weaning_alerts

logger = logging.getLogger(__name__)


def pending_weanings():
    newer = births.alias("parto_posterior")
    has_newer_birth = select(newer.c.id).where(
        newer.c.madre_id == births.c.madre_id,
        or_(
            newer.c.fecha > births.c.fecha,
            and_(
                newer.c.fecha == births.c.fecha,
                or_(
                    newer.c.fecha_captura > births.c.fecha_captura,
                    and_(newer.c.fecha_captura == births.c.fecha_captura, newer.c.id > births.c.id),
                ),
            ),
        ),
    ).exists()
    has_live_offspring = select(birth_offspring.c.id).where(
        birth_offspring.c.parto_id == births.c.id,
        birth_offspring.c.viva.is_(True),
    ).exists()
    return (
        select(
            births.c.id.label("parto_id"), births.c.madre_id,
            births.c.fecha.label("fecha_parto"), ranches.c.dias_lactancia,
        )
        .join(animals, animals.c.id == births.c.madre_id)
        .join(ranches, ranches.c.id == animals.c.rancho_id)
        .where(
            animals.c.estado == "activo",
            animals.c.estado_reproductivo == "lactancia",
            ~has_newer_birth,
            has_live_offspring,
        )
    )


def generate_weaning_alerts(engine, today: date):
    due = or_(*(
        and_(ranches.c.dias_lactancia == days, births.c.fecha <= today - timedelta(days=days))
        for days in (60, 75, 90)
    ))
    already_generated = select(weaning_alerts.c.parto_id).where(
        weaning_alerts.c.parto_id == births.c.id
    ).exists()
    candidates = pending_weanings().with_only_columns(births.c.id).where(due, ~already_generated)
    insert = weaning_alerts.insert().from_select(["parto_id"], candidates)
    # Otra instancia puede insertar el mismo parto entre la consulta y la escritura.
    try:
        with engine.begin() as connection:
            connection.execute(insert)
    except IntegrityError:
        with engine.begin() as connection:
            connection.execute(insert)


async def run_weaning_job(database_url: str, interval_seconds: int):
    while True:
        try:
            await asyncio.to_thread(generate_weaning_alerts, auth_engine(database_url), date.today())
        except (SQLAlchemyError, ImportError):
            logger.warning("No se pudieron generar las alertas de destete; se reintentará en el próximo ciclo.")
        await asyncio.sleep(interval_seconds)


@asynccontextmanager
async def weaning_lifespan(app):
    settings = app.state.settings
    if not settings.database_url or not settings.weaning_alert_interval_seconds:
        yield
        return
    task = asyncio.create_task(run_weaning_job(settings.database_url, settings.weaning_alert_interval_seconds))
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
