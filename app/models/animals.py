from sqlalchemy import Column, Date, ForeignKey, Index, Numeric, String, Table

from app.models.auth import metadata, uuid

breeds = Table(
    "raza", metadata,
    Column("id", uuid, primary_key=True),
    Column("nombre", String(255), nullable=False),
)
animals = Table(
    "animal", metadata,
    Column("id", uuid, primary_key=True),
    Column("rancho_id", ForeignKey("rancho.id"), nullable=False, index=True),
    Column("madre_id", ForeignKey("animal.id")),
    Column("padre_id", ForeignKey("animal.id")),
    Column("raza_id", ForeignKey("raza.id")),
    Column("sexo", String(32), nullable=False),
    Column("fecha_nacimiento", Date),
    Column("etapa_vida", String(64)),
    Column("estado_reproductivo", String(64)),
    Column("criador", String(255)),
    Column("propietario", String(255)),
    Column("circunferencia_testicular", Numeric(8, 2)),
    Column("estado", String(32), nullable=False),
)
identifiers = Table(
    "animal_identificador", metadata,
    Column("id", uuid, primary_key=True),
    Column("animal_id", ForeignKey("animal.id"), nullable=False, index=True),
    Column("tipo", String(32), nullable=False),
    Column("valor", String(255), nullable=False),
)
official = identifiers.c.tipo.in_(("arete", "SINIIGA"))
Index("uq_identificador_oficial", identifiers.c.tipo, identifiers.c.valor, unique=True,
      sqlite_where=official, mssql_where=official)
removals = Table(
    "baja", metadata,
    Column("id", uuid, primary_key=True),
    Column("animal_id", ForeignKey("animal.id"), nullable=False),
    Column("fecha", Date, nullable=False),
    Column("motivo", String(255), nullable=False),
    Column("registrada_por", ForeignKey("usuario.id"), nullable=False),
)
