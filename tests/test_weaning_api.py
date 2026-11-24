import os
import unittest
from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.config import Settings
from app.main import app
from app.models.auth import accounts, ranches, auth_engine
from app.models.animals import animals, removals
from app.models.events import weights, weight_types
from app.services.auth import password_hasher
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
                with engine.begin() as c:
                    c.execute(accounts.insert().values(id=owner, nombre="Demo", email="demo", tipo="productor",
                                                       password_hash=password_hasher.hash("test-password")))
                    c.execute(ranches.insert().values(id=ranch, nombre="Demo", propietario_id=owner))
                    for aid in (animal, other):
                        c.execute(animals.insert().values(id=aid, rancho_id=ranch, sexo="hembra", estado="activo",
                                                         fecha_nacimiento=date(2026, 1, 1)))
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
                    self.assertEqual(client.post(base + "/destete", json=payload, headers=headers).status_code, 409)
                    self.assertEqual(client.get(base + "/destete", headers=headers).json(), response.json())
                    self.assertEqual(client.post(other_base + "/destete", json=payload | {"pesaje_id": None}, headers=headers).status_code, 201)
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
                    self.assertEqual(client.post(base + "/destete", json=payload, headers=headers).status_code, 409)
                    for suffix in ("destete", "baja"):
                        self.assertEqual(client.get(f"/ranchos/{uuid4()}/animales/{animal}/{suffix}", headers=headers).status_code, 403)
                        self.assertEqual(client.get(f"/ranchos/{ranch}/animales/{uuid4()}/{suffix}", headers=headers).status_code, 404)
                    with engine.connect() as c:
                        self.assertEqual(c.scalar(select(animals.c.estado).where(animals.c.id == animal)), "baja")
                        self.assertEqual(c.scalar(select(removals.c.motivo)), "Venta")
            finally:
                engine.dispose()
                auth_engine.cache_clear()
