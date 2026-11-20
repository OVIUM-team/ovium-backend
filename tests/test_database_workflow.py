"""Pruebas de migraciones reales y login. SQL Server usa una base VACIA dedicada."""
import io
import os
import unittest
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from alembic import command
from alembic.config import Config
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, inspect, select, text
from sqlalchemy.exc import DatabaseError

from app.config import Settings
from app.main import app
from app.models import metadata
from app.models.auth import auth_engine, accounts, ranches
from app.models.animals import animals, identifiers, removals
from app.models.events import births, weights, weanings, photos, birth_offspring
from app.models.audit import corrections, sync_operations
from app.seed import seed_demo, demo_id, ROLES
from test_migrations import migrate


class DatabaseWorkflowTest(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.url = os.environ.get("OVIUM_TEST_DATABASE_URL", f"sqlite:///{self.directory.name}/workflow.sqlite")
        self.engine = create_engine(self.url, hide_parameters=True)
        if self.engine.dialect.name == "sqlite":
            @event.listens_for(self.engine, "connect")
            def fk(c, _):
                c.execute("PRAGMA foreign_keys=ON")
        if inspect(self.engine).get_table_names():
            self.engine.dispose()
            self.directory.cleanup()
            self.fail("OVIUM_TEST_DATABASE_URL debe apuntar a una base VACIA de pruebas")

    def tearDown(self):
        self.engine.dispose()
        for cached_url in (self.url,):
            auth_engine(cached_url).dispose()
        auth_engine.cache_clear()
        self.directory.cleanup()

    def test_migrations_seed_login_and_history(self):
        migrate(self.engine)
        migrate(self.engine)  # repetir upgrade es inocuo
        password = "Temporary-password-for-tests-only"
        seed_demo(self.engine, password)
        with self.engine.connect() as c:
            before = {t.name: c.scalar(select(func.count()).select_from(t)) for t in metadata.sorted_tables}
            hashes = list(c.scalars(select(accounts.c.password_hash)))
        seed_demo(self.engine, "Another-password-not-applied")
        with self.engine.connect() as c:
            self.assertEqual(before, {t.name: c.scalar(select(func.count()).select_from(t)) for t in metadata.sorted_tables})
            self.assertEqual(hashes, list(c.scalars(select(accounts.c.password_hash))))
            self.assertEqual(compare_metadata(MigrationContext.configure(c), metadata), [])
        secret = "temporary-jwt-secret-for-integration-tests-only"
        settings = Settings(database_url=self.url, jwt_secret=secret)
        with patch.object(app.state, "settings", settings), TestClient(app) as client:
            for role in ROLES:
                login = client.post("/auth/login", json={"username": role + "@demo.ovium.test", "password": password})
                self.assertEqual(login.status_code, 200, login.text)
                headers = {"Authorization": "Bearer " + login.json()["access_token"]}
                session = client.get("/auth/session", headers=headers).json()
                self.assertEqual(session["role"], role)
                self.assertEqual(session["ranch_ids"], [demo_id("rancho")])
                self.assertEqual(len(client.get("/ranchos", headers=headers).json()), 1)
                if role == "productor":
                    bad = client.put("/ranchos/" + demo_id("rancho"), json={"nombre": "Demo", "dias_lactancia": 61}, headers=headers)
                    self.assertEqual(bad.status_code, 422)

        animal_id, other_id, birth_id, weight_id = (str(uuid4()) for _ in range(4))
        user = demo_id("usuario/productor")
        with self.engine.begin() as c:
            for ident in (animal_id, other_id):
                c.execute(animals.insert().values(id=ident, rancho_id=demo_id("rancho"), sexo="hembra", estado="activo"))
            c.execute(identifiers.insert().values(id=str(uuid4()), animal_id=animal_id, tipo="SINIIGA", valor="TEST-OFFICIAL-001"))
            c.execute(births.insert().values(id=birth_id, madre_id=animal_id, fecha=date(2026, 11, 1),
                tipo_parto_id=demo_id("parto/1"), metodo_concepcion_id=demo_id("concepcion/MN"),
                registrado_por=user, fecha_captura=datetime(2026, 11, 1), cierre_edicion=datetime(2026, 12, 1), bloqueado=True))
            c.execute(birth_offspring.insert().values(id=str(uuid4()), parto_id=birth_id, animal_id=other_id, peso_nacimiento=3.5))
            c.execute(weights.insert().values(id=weight_id, animal_id=other_id, fecha=date(2026, 11, 19),
                tipo_pesaje_id=demo_id("pesaje/evaluacion"), peso=20, peso_evaluacion=20,
                circunferencia_testicular=15, registrado_por=user))
            c.execute(removals.insert().values(id=str(uuid4()), animal_id=other_id, fecha=date(2026,11,19), motivo="Venta", registrada_por=user))
            c.execute(animals.update().where(animals.c.id==other_id).values(estado="baja"))
        correction_id, operation_id = str(uuid4()), str(uuid4())
        with self.engine.begin() as c:
            c.execute(corrections.insert().values(id=correction_id, parto_id=birth_id, campo="fecha", valor_anterior="2026-11-01",
                valor_nuevo="2026-11-02", motivo="Verificacion de captura", evidencia="https://example.test/evidencia.jpg", aprobado_por=demo_id("usuario/tecnico")))
            c.execute(photos.insert().values(id=str(uuid4()), parto_id=birth_id, correccion_id=correction_id,
                url="https://example.test/evidencia.jpg", registrada_por=user))
            operation = dict(id=operation_id, rancho_id=demo_id("rancho"), usuario_id=user,
                entidad="pesaje", registro_id=weight_id, operacion="crear", estado="aplicada")
            c.execute(sync_operations.insert().values(**operation))
        invalid_statements = [
            sync_operations.insert().values(**operation),
            corrections.update().where(corrections.c.id==correction_id).values(motivo="Cambio"),
            corrections.delete().where(corrections.c.id==correction_id),
            births.update().where(births.c.id==birth_id).values(fecha=date(2026,11,2)),
            animals.delete().where(animals.c.id==other_id),
            identifiers.insert().values(id=str(uuid4()), animal_id=other_id, tipo="SINIIGA", valor="TEST-OFFICIAL-001"),
            ranches.update().where(ranches.c.id==demo_id("rancho")).values(dias_lactancia=61),
            weights.insert().values(id=str(uuid4()), animal_id=other_id, fecha=date.today(), tipo_pesaje_id=demo_id("pesaje/evaluacion"), peso=-1, registrado_por=user),
            weanings.insert().values(id=str(uuid4()), animal_id=animal_id, pesaje_id=weight_id, fecha=date.today(), destino="venta", registrado_por=user),
        ]
        for statement in invalid_statements:
            with self.subTest(statement=str(statement)):
                with self.assertRaises(DatabaseError), self.engine.begin() as c:
                    c.execute(statement)
        with self.engine.connect() as c:
            self.assertEqual(c.scalar(select(births.c.fecha)), date(2026,11,1))
            self.assertEqual(c.scalar(select(animals.c.estado).where(animals.c.id==other_id)), "baja")
            self.assertEqual(c.scalar(select(func.count()).select_from(sync_operations)), 1)


class SqlServerCompilationTest(unittest.TestCase):
    def test_offline_upgrade_sqlserver(self):
        output = io.StringIO()
        config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"), output_buffer=output)
        config.set_main_option("sqlalchemy.url", "mssql+pyodbc://example/test?driver=ODBC+Driver+18+for+SQL+Server")
        command.upgrade(config, "head", sql=True)
        sql = output.getvalue()
        self.assertIn("CREATE TABLE sync_operacion", sql)
        self.assertIn("CREATE TRIGGER tr_animal_no_delete", sql)
        self.assertIn("UNIQUEIDENTIFIER", sql)
