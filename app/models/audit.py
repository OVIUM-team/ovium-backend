"""Correcciones anexas al original y registro de IDs de sincronizacion."""
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, String, Table, func

from app.models.auth import metadata, uuid
from app.models.events import photos

corrections = Table(
    "correccion", metadata,
    Column("id", uuid, primary_key=True),
    Column("parto_id", ForeignKey("parto.id"), nullable=False, index=True),
    Column("campo", String(128), nullable=False),
    Column("valor_anterior", String(4000), nullable=True),
    Column("valor_nuevo", String(4000), nullable=True),
    Column("motivo", String(1000), nullable=False),
    Column("evidencia", String(2048), nullable=False),
    Column("aprobado_por", ForeignKey("usuario.id"), nullable=False),
    Column("fecha", DateTime, nullable=False, server_default=func.current_timestamp()),
    CheckConstraint("ltrim(rtrim(motivo)) <> ''", name="ck_correccion_motivo"),
    CheckConstraint("ltrim(rtrim(evidencia)) <> ''", name="ck_correccion_evidencia"),
)
photos.append_column(Column("correccion_id", ForeignKey("correccion.id", name="fk_foto_correccion")))
sync_operations = Table(
    "sync_operacion", metadata,
    Column("id", uuid, primary_key=True),
    Column("rancho_id", ForeignKey("rancho.id"), nullable=False),
    Column("usuario_id", ForeignKey("usuario.id"), nullable=False),
    Column("estado", String(32), nullable=False, server_default="pendiente"),
    Column("fecha", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("entidad", String(64), nullable=False),
    Column("registro_id", uuid, nullable=False),
    Column("operacion", String(16), nullable=False),
    Column("error", String(1000)),
    CheckConstraint("estado IN ('pendiente','aplicada','error')", name="ck_sync_estado"),
    CheckConstraint("operacion IN ('crear','actualizar')", name="ck_sync_operacion"),
)
Index("ix_sync_rancho_estado", sync_operations.c.rancho_id, sync_operations.c.estado)
