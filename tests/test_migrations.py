import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.exc import IntegrityError, DatabaseError


def migrate(engine, revision="head"):
    config = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)


class CoreMigrationTest(unittest.TestCase):
    def test_core_constraints_and_animal_preservation(self):
        with TemporaryDirectory() as directory:
            engine = create_engine(f"sqlite:///{directory}/core.sqlite")
            @event.listens_for(engine, "connect")
            def fk(connection, _):
                connection.execute("PRAGMA foreign_keys=ON")
            try:
                migrate(engine, "0001_nucleo")
                migrate(engine, "0001_nucleo")
                self.assertIn("usuario_rancho", inspect(engine).get_table_names())
                # SQL literals avoid coupling this historical revision to future models.
                with engine.begin() as c:
                    c.execute(text("INSERT INTO usuario VALUES ('u','Demo','demo@test','hash','productor')"))
                    c.execute(text("INSERT INTO rancho VALUES ('r','Demo',NULL,'u',75)"))
                    for animal in ("a", "b"):
                        c.execute(text("INSERT INTO animal (id,rancho_id,sexo,estado) VALUES (:id,'r','hembra','activo')"), {"id": animal})
                    c.execute(text("INSERT INTO animal_identificador VALUES ('i','a','SINIIGA','001')"))
                with self.assertRaises(IntegrityError), engine.begin() as c:
                    c.execute(text("INSERT INTO animal_identificador VALUES ('j','b','SINIIGA','001')"))
                with self.assertRaises(DatabaseError), engine.begin() as c:
                    c.execute(text("DELETE FROM animal WHERE id='b'"))
                with engine.connect() as c:
                    self.assertEqual(c.scalar(text("SELECT COUNT(*) FROM animal")), 2)
            finally:
                engine.dispose()
