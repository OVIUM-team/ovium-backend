import os
import unittest
from datetime import date, datetime
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.config import Settings
from app.main import app
from app.models.auth import accounts, account_ranches, ranches, auth_engine
from app.models.animals import animals, removals
from app.models.events import weights, weight_types, births, birth_offspring, birth_types, conception_methods
from app.services.auth import create_token, password_hasher
from app.schemas.auth import SessionClaims
from test_migrations import migrate


class WeaningApiTest(unittest.TestCase):
    def test_weaning_and_removal_validation_and_preservation(self):
        with TemporaryDirectory() as directory:
            url = f"sqlite:///{directory}/events.sqlite"
            engine = auth_engine(url)
            @event.listens_for(engine, "connect")
            def fk(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
            try:
                migrate(engine)
                owner, ranch, animal, other, weight, kind = [str(uuid4()) for _ in range(6)]
                mother = str(uuid4())
                with engine.begin() as c:
                    c.execute(accounts.insert().values(id=owner, nombre="Demo", email="demo", tipo="productor",
                                                       password_hash=password_hasher.hash("test-password")))
                    c.execute(ranches.insert().values(id=ranch, nombre="Demo", propietario_id=owner))
                    c.execute(animals.insert().values(id=mother, rancho_id=ranch, sexo="hembra", estado="activo",
                                                     estado_reproductivo="lactancia"))
                    for aid in (animal, other):
                        c.execute(animals.insert().values(id=aid, rancho_id=ranch, sexo="hembra", estado="activo",
                                                         fecha_nacimiento=date(2026, 1, 1), madre_id=mother))
                    birth_id, birth_type, method = [str(uuid4()) for _ in range(3)]
                    c.execute(birth_types.insert().values(id=birth_type, nombre="Doble", numero_crias=2))
                    c.execute(conception_methods.insert().values(id=method, codigo="MN", nombre="Monta natural"))
                    c.execute(births.insert().values(id=birth_id, madre_id=mother, fecha=date(2026, 1, 1),
                              tipo_parto_id=birth_type, metodo_concepcion_id=method, registrado_por=owner,
                              fecha_captura=datetime(2026, 1, 1), cierre_edicion=datetime(2026, 1, 31)))
                    for aid in (animal, other):
                        c.execute(birth_offspring.insert().values(id=str(uuid4()), parto_id=birth_id, animal_id=aid, viva=True))
                    c.execute(weight_types.insert().values(id=kind, codigo="destete", nombre="Destete"))
                    c.execute(weights.insert().values(id=weight, animal_id=animal, tipo_pesaje_id=kind,
                                                      fecha=date(2026, 3, 17), peso=25, registrado_por=owner))
                with patch.dict(os.environ, DATABASE_URL=url, JWT_SECRET="temporary-signing-secret-for-events-api-only"):
                    settings = Settings()
                with patch.object(app.state, "settings", settings), TestClient(app) as client:
                    token = client.post("/auth/login", json={"username": "demo", "password": "test-password"}).json()["access_token"]
                    headers = {"Authorization": f"Bearer {token}"}
                    base = f"/ranchos/{ranch}/animales/{animal}"
                    payload = {"fecha": "2026-03-17", "destino": "recria", "pesaje_id": weight}
                    self.assertEqual(client.post(base + "/destete", json=payload).status_code, 401)
                    self.assertEqual(client.get(base + "/destete", headers=headers).status_code, 404)
                    for change in ({"fecha": "2025-01-01"}, {"fecha": "2999-01-01"},
                                   {"destino": "invalido"}, {"pesaje_id": str(uuid4())}, {"fecha": "2026-03-18"}):
                        self.assertEqual(client.post(base + "/destete", json=payload | change, headers=headers).status_code, 422)
                    other_base = f"/ranchos/{ranch}/animales/{other}"
                    self.assertEqual(client.post(other_base + "/destete", json=payload, headers=headers).status_code, 422)
                    response = client.post(base + "/destete", json=payload, headers=headers)
                    self.assertEqual(response.status_code, 201, response.text)
                    self.assertEqual(response.json()["registrado_por"], owner)
                    self.assertEqual(client.get(f"/ranchos/{ranch}/animales/{mother}", headers=headers).json()["estado_reproductivo"], "lactancia")
                    self.assertEqual(client.post(base + "/destete", json=payload, headers=headers).status_code, 409)
                    self.assertEqual(client.get(base + "/destete", headers=headers).json(), response.json())
                    self.assertEqual(client.post(other_base + "/destete", json=payload | {"pesaje_id": None}, headers=headers).status_code, 422)
                    self.assertEqual(client.post(other_base + "/destete", json=payload | {"pesaje_id": None, "peso": 24}, headers=headers).status_code, 201)
                    self.assertEqual(client.get(f"/ranchos/{ranch}/animales/{mother}", headers=headers).json()["estado_reproductivo"], "mantenimiento")
                    # A duplicate must also roll back its newly-created weighing.
                    self.assertEqual(client.post(other_base + "/destete", json=payload | {"pesaje_id": None, "peso": 24}, headers=headers).status_code, 409)
                    with engine.connect() as c:
                        self.assertEqual(c.scalar(select(func.count()).select_from(weights)), 2)
                    removal = {"fecha": "2026-04-01", "motivo": "Venta", "id": str(uuid4())}
                    for change in ({"motivo": "   "}, {"fecha": "2025-01-01"}, {"fecha": "2999-01-01"}):
                        self.assertEqual(client.post(base + "/baja", json=removal | change, headers=headers).status_code, 422)
                    response = client.post(base + "/baja", json=removal, headers=headers)
                    self.assertEqual(response.status_code, 201, response.text)
                    self.assertEqual(client.get(base + "/baja", headers=headers).json(), response.json())
                    self.assertEqual(client.post(base + "/baja", json=removal, headers=headers).status_code, 409)
                    # Duplicate UUID must roll back the other animal's status change.
                    self.assertEqual(client.post(other_base + "/baja", json=removal, headers=headers).status_code, 409)
                    self.assertEqual(client.get(other_base, headers=headers).json()["estado"], "activo")
                    active = client.get(f"/ranchos/{ranch}/animales?estado=activo", headers=headers).json()
                    self.assertNotIn(animal, {a["id"] for a in active})
                    deaths = client.get(f"/ranchos/{ranch}/bajas?motivo=muerte", headers=headers).json()
                    self.assertEqual(deaths, [])
                    self.assertEqual(len(client.get(f"/ranchos/{ranch}/bajas?motivo=venta", headers=headers).json()), 1)
                    self.assertEqual(client.post(other_base + "/baja", json={"fecha": "2026-04-02", "motivo": "muerte"}, headers=headers).status_code, 201)
                    self.assertEqual(len(client.get(f"/ranchos/{ranch}/bajas?motivo=muerte&desde=2026-04-02&hasta=2026-04-02", headers=headers).json()), 1)
                    # Permissions are checked against current database membership.
                    for role in ("rama", "tecnico", "asociacion"):
                        uid = str(uuid4())
                        with engine.begin() as c:
                            c.execute(accounts.insert().values(id=uid, nombre=role, email=role, tipo="productor" if role == "rama" else role,
                                                               password_hash="not-used"))
                            if role != "asociacion":
                                c.execute(account_ranches.insert().values(id=str(uuid4()), usuario_id=uid, rancho_id=ranch,
                                                                          rol=role, puede_leer=True))
                        token = create_token(SessionClaims(sub=uid, role=role, ranch_ids=[ranch]), settings.jwt_secret)
                        restricted = {"Authorization": f"Bearer {token}"}
                        for suffix, data in (("destete", payload), ("baja", removal)):
                            self.assertEqual(client.get(base + "/" + suffix, headers=restricted).status_code, 200)
                            self.assertEqual(client.post(base + "/" + suffix, json=data, headers=restricted).status_code, 403)
                        if role == "rama":
                            with engine.begin() as c:
                                c.execute(account_ranches.update().where(account_ranches.c.usuario_id == uid)
                                          .values(puede_capturar=True, puede_editar=True))
                            # Permission now passes; duplicate business state returns 409.
                            self.assertEqual(client.post(base + "/destete", json=payload, headers=restricted).status_code, 409)
                            self.assertEqual(client.post(base + "/baja", json=removal, headers=restricted).status_code, 409)
                    self.assertEqual(client.post(base + "/destete", json=payload, headers=headers).status_code, 409)
                    for suffix in ("destete", "baja"):
                        self.assertEqual(client.get(f"/ranchos/{uuid4()}/animales/{animal}/{suffix}", headers=headers).status_code, 403)
                        self.assertEqual(client.get(f"/ranchos/{ranch}/animales/{uuid4()}/{suffix}", headers=headers).status_code, 404)
                    with engine.connect() as c:
                        self.assertEqual(c.scalar(select(animals.c.estado).where(animals.c.id == animal)), "baja")
                        self.assertEqual(c.scalar(select(removals.c.motivo).where(removals.c.animal_id == animal)), "venta")
            finally:
                engine.dispose()
                auth_engine.cache_clear()
