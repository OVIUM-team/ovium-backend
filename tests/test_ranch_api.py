import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import event, select

from app.config import Settings
from app.main import app
from app.models.animals import animals, removals
from app.models.auth import account_ranches, accounts, auth_engine, metadata
from app.services.auth import password_hasher


class RanchApiTest(unittest.TestCase):
    def test_ranch_access_branch_login_and_animal_lifecycle(self):
        with TemporaryDirectory() as directory:
            url = f"sqlite:///{directory}/test.sqlite"
            secret = "temporary-signing-secret-for-test-only"
            with patch.dict(os.environ, DATABASE_URL=url, JWT_SECRET=secret):
                settings = Settings()

            engine = auth_engine(url)

            @event.listens_for(engine, "connect")
            def enforce_foreign_keys(connection, record):
                connection.execute("PRAGMA foreign_keys=ON")

            metadata.create_all(engine)
            try:
                password = "fake-local-password"
                hashed = password_hasher.hash(password)
                account_ids = {name: str(uuid4()) for name in ("owner", "other", "technician", "association")}
                with engine.begin() as connection:
                    connection.execute(accounts.insert(), [
                        dict(id=account_ids[name], nombre=name, email=name, password_hash=hashed, tipo=role)
                        for name, role in (
                            ("owner", "productor"), ("other", "productor"),
                            ("technician", "tecnico"), ("association", "asociacion"),
                        )
                    ])

                with patch.object(app.state, "settings", settings), TestClient(app) as client:
                    def login(username):
                        response = client.post("/auth/login", json={"username": username, "password": password})
                        self.assertEqual(response.status_code, 200, response.text)
                        return {"Authorization": f"Bearer {response.json()['access_token']}"}

                    owner = login("owner")
                    other = login("other")
                    association = login("association")
                    technician = login("technician")
                    ranch_data = {"nombre": "Rancho"}
                    created = client.post("/ranchos", json=ranch_data, headers=owner)
                    self.assertEqual(created.status_code, 201, created.text)
                    ranch = created.json()["id"]
                    other_ranch = client.post("/ranchos", json=ranch_data, headers=other).json()["id"]
                    self.assertEqual(client.post("/ranchos", json=ranch_data, headers=owner).status_code, 409)
                    self.assertEqual(
                        client.put(f"/ranchos/{ranch}", json={"nombre": "Actualizado"}, headers=owner).status_code, 200
                    )

                    branch_route = f"/ranchos/{ranch}/ramas"
                    branch_data = {"nombre": "Rama", "email": "branch", "password": password, "puede_leer": True}
                    self.assertEqual(client.post(branch_route, json=branch_data, headers=other).status_code, 403)
                    branch = client.post(branch_route, json=branch_data, headers=owner)
                    self.assertEqual(branch.status_code, 201, branch.text)
                    branch_headers = login("branch")
                    self.assertEqual([item["id"] for item in client.get("/ranchos", headers=branch_headers).json()], [ranch])
                    self.assertEqual(
                        {item["id"] for item in client.get("/ranchos", headers=association).json()}, {ranch, other_ranch}
                    )
                    with engine.begin() as connection:
                        connection.execute(account_ranches.insert().values(
                            id=str(uuid4()), usuario_id=account_ids["technician"], rancho_id=ranch, rol="tecnico"
                        ))
                    self.assertEqual([item["id"] for item in client.get("/ranchos", headers=technician).json()], [ranch])

                    path = f"/ranchos/{ranch}/animales"
                    other_path = f"/ranchos/{other_ranch}/animales"
                    self.assertEqual(client.get(other_path, headers=owner).status_code, 403)
                    self.assertEqual(client.get(other_path, headers=branch_headers).status_code, 403)

                    def create(payload):
                        response = client.post(path, json=payload, headers=owner)
                        self.assertEqual(response.status_code, 201, response.text)
                        return response.json()

                    mother = create({"sexo": "hembra"})
                    father = create({"sexo": "macho", "criador": "Criador externo"})
                    official_id = {"tipo": "SINIIGA", "valor": "test-001"}
                    calf = create({"sexo": "hembra", "madre_id": mother["id"], "padre_id": father["id"],
                                   "identificadores": [official_id]})
                    item_path = f"{path}/{calf['id']}"
                    detail = client.get(item_path, headers=branch_headers).json()
                    self.assertEqual(detail["madre"]["id"], mother["id"])
                    self.assertEqual(detail["padre"]["id"], father["id"])
                    self.assertEqual(detail["identificadores"], [official_id])
                    self.assertEqual(client.get(f"{other_path}/{calf['id']}", headers=other).status_code, 404)
                    self.assertEqual(client.get(path + "?sexo=macho", headers=owner).json()[0]["id"], father["id"])
                    self.assertEqual(
                        client.post(path, json={"sexo": "hembra", "identificadores": [official_id]}, headers=owner).status_code,
                        409,
                    )
                    data = {"sexo": "hembra", "madre_id": mother["id"], "padre_id": father["id"]}
                    self.assertEqual(client.put(item_path, json=data, headers=branch_headers).status_code, 403)
                    self.assertEqual(client.put(item_path, json=data, headers=owner).status_code, 200)
                    removed = client.post(
                        f"{item_path}/baja", json={"fecha": "2026-11-19", "motivo": "Venta"}, headers=owner
                    )
                    self.assertEqual(removed.status_code, 201, removed.text)
                    self.assertEqual(client.get(item_path, headers=owner).json()["estado"], "baja")
                    with engine.connect() as connection:
                        self.assertEqual(connection.scalar(select(animals.c.estado).where(animals.c.id == calf["id"])), "baja")
                        self.assertEqual(connection.scalar(select(removals.c.motivo)), "Venta")
            finally:
                engine.dispose()
                auth_engine.cache_clear()
