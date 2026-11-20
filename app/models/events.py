"""Eventos de registro. Las bajas conservan el animal y su historial."""
from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey,
    Index, Integer, Numeric, String, Table, UniqueConstraint, func,
)

from app.models.auth import metadata, uuid

birth_types = Table(
    "tipo_parto", metadata,
    Column("id", uuid, primary_key=True),
    Column("nombre", String(64), nullable=False, unique=True),
    Column("numero_crias", Integer, nullable=False, unique=True),
    CheckConstraint("numero_crias BETWEEN 1 AND 5", name="ck_tipo_parto_crias"),
)
conception_methods = Table(
    "metodo_concepcion", metadata,
    Column("id", uuid, primary_key=True),
    Column("codigo", String(8), nullable=False, unique=True),
    Column("nombre", String(128), nullable=False),
    CheckConstraint("codigo IN ('MN','IA','TE')", name="ck_metodo_concepcion_codigo"),
)
weight_types = Table(
    "tipo_pesaje", metadata,
    Column("id", uuid, primary_key=True),
    Column("codigo", String(32), nullable=False, unique=True),
    Column("nombre", String(128), nullable=False),
    CheckConstraint("codigo IN ('nacimiento','destete','120_d','150_d','evaluacion')", name="ck_tipo_pesaje_codigo"),
)
births = Table(
    "parto", metadata,
    Column("id", uuid, primary_key=True),
    Column("madre_id", ForeignKey("animal.id"), nullable=False, index=True),
    Column("padre_id", ForeignKey("animal.id")),
    Column("fecha", Date, nullable=False),
    Column("tipo_parto_id", ForeignKey("tipo_parto.id"), nullable=False),
    Column("metodo_concepcion_id", ForeignKey("metodo_concepcion.id"), nullable=False),
    Column("registrado_por", ForeignKey("usuario.id"), nullable=False),
    Column("fecha_captura", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("cierre_edicion", DateTime, nullable=False),
    Column("bloqueado", Boolean, nullable=False, server_default="0"),
    Column("observaciones", String(1000)),
    CheckConstraint("cierre_edicion >= fecha_captura", name="ck_parto_cierre"),
)
birth_offspring = Table(
    "parto_cria", metadata,
    Column("id", uuid, primary_key=True),
    Column("parto_id", ForeignKey("parto.id"), nullable=False, index=True),
    Column("animal_id", ForeignKey("animal.id"), nullable=False, unique=True),
    Column("viva", Boolean, nullable=False, server_default="1"),
    Column("peso_nacimiento", Numeric(8, 2)),
    CheckConstraint("peso_nacimiento IS NULL OR peso_nacimiento > 0", name="ck_parto_cria_peso"),
)
weights = Table(
    "pesaje", metadata,
    Column("id", uuid, primary_key=True),
    Column("animal_id", ForeignKey("animal.id"), nullable=False),
    Column("fecha", Date, nullable=False),
    Column("tipo_pesaje_id", ForeignKey("tipo_pesaje.id"), nullable=False),
    Column("peso", Numeric(8, 2), nullable=False),
    Column("circunferencia_testicular", Numeric(8, 2)),
    Column("peso_evaluacion", Numeric(8, 2)),
    Column("registrado_por", ForeignKey("usuario.id"), nullable=False),
    CheckConstraint("peso > 0", name="ck_pesaje_peso"),
    CheckConstraint("circunferencia_testicular IS NULL OR circunferencia_testicular > 0", name="ck_pesaje_circunferencia"),
    CheckConstraint("peso_evaluacion IS NULL OR peso_evaluacion > 0", name="ck_pesaje_evaluacion"),
    UniqueConstraint("id", "animal_id", name="uq_pesaje_animal"),
)
Index("ix_pesaje_animal_fecha", weights.c.animal_id, weights.c.fecha)
weanings = Table(
    "destete", metadata,
    Column("id", uuid, primary_key=True),
    Column("animal_id", ForeignKey("animal.id"), nullable=False, unique=True),
    Column("fecha", Date, nullable=False),
    Column("pesaje_id", uuid),
    Column("destino", String(32), nullable=False),
    Column("registrado_por", ForeignKey("usuario.id"), nullable=False),
    CheckConstraint("destino IN ('engorda','venta','recria')", name="ck_destete_destino"),
)
# Impide asociar al destete un pesaje de otro animal.
from sqlalchemy import ForeignKeyConstraint
weanings.append_constraint(ForeignKeyConstraint(
    ["pesaje_id", "animal_id"], ["pesaje.id", "pesaje.animal_id"], name="fk_destete_pesaje_animal",
))
health_events = Table(
    "evento_sanitario", metadata,
    Column("id", uuid, primary_key=True),
    Column("animal_id", ForeignKey("animal.id"), nullable=False),
    Column("fecha", Date, nullable=False),
    Column("tipo", String(32), nullable=False),
    Column("producto", String(255), nullable=False),
    Column("dosis", String(128), nullable=False),
    Column("responsable_id", ForeignKey("usuario.id"), nullable=False),
    Column("observaciones", String(1000)),
    CheckConstraint("tipo IN ('vacunacion','vitaminas','selenio','desparasitacion','tratamiento')", name="ck_sanitario_tipo"),
)
Index("ix_sanitario_animal_fecha", health_events.c.animal_id, health_events.c.fecha)
photos = Table(
    "foto", metadata,
    Column("id", uuid, primary_key=True),
    Column("parto_id", ForeignKey("parto.id"), nullable=False, index=True),
    Column("url", String(2048), nullable=False),
    Column("sha256", String(64)),
    Column("fecha_captura", DateTime, nullable=False, server_default=func.current_timestamp()),
    Column("registrada_por", ForeignKey("usuario.id"), nullable=False),
)
