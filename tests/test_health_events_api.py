import os
import unittest
from datetime import date
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, func, select

from app.config import Settings
from app.main import app
from app.models.auth import accounts, account_ranches, ranches, auth_engine
from app.models.animals import animals
from app.models.events import health_events
from app.services.auth import password_hasher
from test_migrations import migrate


class HealthEventsApiTest(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        url = f"sqlite:///{self.directory.name}/health.sqlite"
        self.engine = auth_engine(url)
        self.addCleanup(auth_engine.cache_clear)
        self.addCleanup(self.engine.dispose)
        @event.listens_for(self.engine, "connect")
        def fk(connection, _):
            connection.execute("PRAGMA foreign_keys=ON")
        migrate(self.engine)
        self.ids = {key: str(uuid4()) for key in ("owner", "other", "rama", "tecnico", "asociacion", "ranch", "ranch2", "a", "b", "foreign")}
        ids = self.ids
        with self.engine.begin() as c:
            hashed = password_hasher.hash("test-password")
            for user, role in (("owner", "productor"), ("other", "productor"), ("rama", "productor"),
                               ("tecnico", "tecnico"), ("asociacion", "asociacion")):
                c.execute(accounts.insert().values(id=ids[user], nombre=user, email=user, tipo=role, password_hash=hashed))
            for ranch, owner in (("ranch", "owner"), ("ranch2", "other")):
                c.execute(ranches.insert().values(id=ids[ranch], nombre=ranch, propietario_id=ids[owner]))
            for member in ("rama", "tecnico"):
                c.execute(account_ranches.insert().values(id=str(uuid4()), usuario_id=ids[member], rancho_id=ids["ranch"],
                                                          rol=member, puede_leer=True, puede_capturar=False))
            for animal, ranch in (("a", "ranch"), ("b", "ranch"), ("foreign", "ranch2")):
                c.execute(animals.insert().values(id=ids[animal], rancho_id=ids[ranch], sexo="hembra", estado="activo",
                                                 fecha_nacimiento=date(2026, 1, 1)))
        with patch.dict(os.environ, DATABASE_URL=url, JWT_SECRET="temporary-signing-secret-for-health-api"):
            settings = Settings()
        self.settings_patch = patch.object(app.state, "settings", settings)
        self.settings_patch.start()
        self.addCleanup(self.settings_patch.stop)
        self.client = TestClient(app)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {}
        for user in ("owner", "other", "rama", "tecnico", "asociacion"):
            response = self.client.post("/auth/login", json={"username": user, "password": "test-password"})
            self.assertEqual(response.status_code, 200, response.text)
            self.headers[user] = {"Authorization": f"Bearer {response.json()['access_token']}"}
        self.base = f"/ranchos/{ids['ranch']}"
        self.path = f"{self.base}/animales/{ids['a']}/eventos-sanitarios"
        self.batch = f"{self.base}/eventos-sanitarios/lote"
        self.data = {"fecha": "2026-02-01", "tipo": "vacunacion", "producto": "Producto de prueba", "dosis": "Dosis de prueba"}

    def post(self, path, payload, status=201, user="owner"):
        result = self.client.post(path, json=payload, headers=self.headers[user])
        self.assertEqual(result.status_code, status, result.text)
        return result

    def test_single_types_and_chronological_history(self):
        for i, kind in enumerate(("vacunacion", "vitaminas", "selenio", "desparasitacion", "tratamiento")):
            response = self.post(self.path, self.data | {"tipo": kind, "fecha": f"2026-02-{10-i:02}"})
            self.assertEqual(response.json()["responsable_id"], self.ids["owner"])
        history = self.client.get(self.path, headers=self.headers["owner"]).json()
        self.assertEqual(len(history), 5)
        self.assertEqual([r["fecha"] for r in history], sorted(r["fecha"] for r in history))
        filtered = self.client.get(self.path + "?tipo=vacunacion&desde=2026-02-10&hasta=2026-02-10", headers=self.headers["owner"])
        self.assertEqual(len(filtered.json()), 1)
        self.assertEqual(self.client.get(self.path + "?desde=2026-03-01&hasta=2026-02-01", headers=self.headers["owner"]).status_code, 422)

    def test_batch_creates_each_record_and_rolls_back_on_duplicate(self):
        targets = [{"animal_id": self.ids[k], "id": str(uuid4())} for k in ("a", "b")]
        result = self.post(self.batch, self.data | {"animales": targets}).json()
        self.assertEqual({r["animal_id"] for r in result}, {self.ids["a"], self.ids["b"]})
        # First insert would succeed, second collides; neither may persist.
        targets[0]["id"] = str(uuid4())
        self.post(self.batch, self.data | {"animales": targets}, 409)
        with self.engine.connect() as c:
            self.assertEqual(c.scalar(select(func.count()).select_from(health_events)), 2)

    def test_batch_is_atomic_for_foreign_missing_inactive_and_young_animals(self):
        for aid in (self.ids["foreign"], str(uuid4())):
            self.post(self.batch, self.data | {"animales": [{"animal_id": self.ids["a"]}, {"animal_id": aid}]}, 404)
        with self.engine.begin() as c:
            c.execute(animals.update().where(animals.c.id == self.ids["b"]).values(estado="baja"))
        payload = self.data | {"animales": [{"animal_id": self.ids[k]} for k in ("a", "b")]}
        self.post(self.batch, payload, 409)
        with self.engine.begin() as c:
            c.execute(animals.update().where(animals.c.id == self.ids["b"]).values(estado="activo", fecha_nacimiento=date(2026, 3, 1)))
        self.post(self.batch, payload, 422)
        with self.engine.connect() as c:
            self.assertEqual(c.scalar(select(func.count()).select_from(health_events)), 0)

    def test_validations_and_duplicate_ids(self):
        for change in ({"fecha": "2999-01-01"}, {"fecha": "2025-01-01"}, {"tipo": "otro"},
                       {"producto": "  "}, {"dosis": "  "}, {"producto": "a" * 256},
                       {"responsable_id": self.ids["other"]}):
            self.post(self.path, self.data | change, 422)
        for targets in ([], [{"animal_id": self.ids["a"]}] * 2):
            self.post(self.batch, self.data | {"animales": targets}, 422)
        payload = self.data | {"id": str(uuid4())}
        self.post(self.path, payload)
        self.post(self.path, payload, 409)

    def test_permissions_and_history_after_removal(self):
        self.assertEqual(self.client.post(self.path, json=self.data).status_code, 401)
        for user in ("other", "rama", "tecnico", "asociacion"):
            self.post(self.path, self.data, 403, user)
            self.post(self.batch, self.data | {"animales": [{"animal_id": self.ids["a"]}]}, 403, user)
        for user in ("rama", "tecnico", "asociacion"):
            self.assertEqual(self.client.get(self.path, headers=self.headers[user]).status_code, 200)
        self.assertEqual(self.client.get(self.path, headers=self.headers["other"]).status_code, 403)
        with self.engine.begin() as c:
            c.execute(account_ranches.update().where(account_ranches.c.usuario_id == self.ids["rama"]).values(puede_capturar=True))
        response = self.post(self.path, self.data, user="rama")
        self.assertEqual(response.json()["responsable_id"], self.ids["rama"])
        with self.engine.begin() as c:
            c.execute(animals.update().where(animals.c.id == self.ids["a"]).values(estado="baja"))
        self.assertEqual(len(self.client.get(self.path, headers=self.headers["owner"]).json()), 1)
        self.post(self.path, self.data, 409)
        foreign_path = f"{self.base}/animales/{self.ids['foreign']}/eventos-sanitarios"
        self.assertEqual(self.client.get(foreign_path, headers=self.headers["owner"]).status_code, 404)
