"""Datos ficticios de desarrollo: python -m app.seed --demo."""
import argparse
import os
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import create_engine, select, text

from app.config import Settings
from app.models.auth import accounts, ranches, account_ranches
from app.models.animals import breeds
from app.models.events import birth_types, conception_methods, weight_types
from app.services.auth import password_hasher

ROLES = ("productor", "rama", "tecnico", "asociacion")


def demo_id(key):
    return str(uuid5(NAMESPACE_URL, "https://ovium.example/demo/" + key))


def insert_once(connection, table, values):
    existing = connection.execute(select(table).where(table.c.id == values["id"])).mappings().one_or_none()
    if existing is None:
        connection.execute(table.insert().values(**values))
    elif any(existing[key] != value for key, value in values.items() if key != "password_hash"):
        raise ValueError(f"El registro demo de {table.name} fue modificado; no se sobrescribe")


def seed_demo(engine, password):
    if len(password) < 12:
        raise ValueError("DEMO_PASSWORD debe tener al menos 12 caracteres")
    with engine.begin() as c:
        version = c.scalar(text("SELECT version_num FROM alembic_version"))
        if version != "0004_ajuste_modelo":
            raise ValueError("Ejecuta alembic upgrade head antes de cargar los datos demo")
        for name in ("Pelibuey", "Dorper", "Katahdin", "Suffolk", "Rambouillet", "Cruza"):
            insert_once(c, breeds, dict(id=demo_id("raza/" + name), nombre=name))
        for count, name in enumerate(("Simple", "Doble", "Triple", "Cuadruple", "Quintuple"), 1):
            insert_once(c, birth_types, dict(id=demo_id("parto/" + str(count)), nombre=name, numero_crias=count))
        for code, name in (("MN", "Monta natural"), ("IA", "Inseminacion artificial"), ("TE", "Transferencia de embriones")):
            insert_once(c, conception_methods, dict(id=demo_id("concepcion/" + code), codigo=code, nombre=name))
        for code, name in (("nacimiento", "Nacimiento"), ("destete", "Destete"), ("120_d", "120 dias"), ("150_d", "150 dias"), ("evaluacion", "Evaluacion")):
            insert_once(c, weight_types, dict(id=demo_id("pesaje/" + code), codigo=code, nombre=name))
        for role in ROLES:
            # La API representa a una rama con tipo productor y membresia rol=rama.
            insert_once(c, accounts, dict(
                id=demo_id("usuario/" + role), nombre="Demo " + role,
                email=role + "@demo.ovium.test", tipo="productor" if role == "rama" else role,
                password_hash=password_hasher.hash(password),
            ))
        ranch_id = demo_id("rancho")
        insert_once(c, ranches, dict(id=ranch_id, nombre="Rancho Demo Ovium",
            domicilio="Datos ficticios de prueba", propietario_id=demo_id("usuario/productor"), dias_lactancia=75))
        for role in ROLES:
            insert_once(c, account_ranches, dict(
                id=demo_id("membresia/" + role), usuario_id=demo_id("usuario/" + role),
                rancho_id=ranch_id, rol=role, puede_leer=True,
                puede_capturar=role in ("productor", "rama"),
                puede_editar=role in ("productor", "rama"), puede_exportar=True,
            ))
    return {role: role + "@demo.ovium.test" for role in ROLES}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", required=True, help="Confirma carga de usuarios ficticios en una BD de desarrollo")
    parser.parse_args()
    url, password = Settings().database_url, os.environ.get("DEMO_PASSWORD")
    if not url or not password:
        parser.error("Configura DATABASE_URL y DEMO_PASSWORD en el entorno; no se incluyen secretos en el repositorio")
    engine = create_engine(url, hide_parameters=True)
    try:
        users = seed_demo(engine, password)
        print("Datos demo listos. Las claves existentes no se restablecen al repetir el script.")
        for role, email in users.items():
            print(f"{role}: {email}")
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
