import os
import unittest
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.config import Settings
from app.models.auth import account_ranches, accounts, auth_engine, metadata
from app.schemas.auth import SessionClaims
from app.services.auth import create_token
from app.services.ranch_access import RanchPermission, require_ranch_access


class RanchAccessTest(unittest.TestCase):
    def test_current_membership_and_branch_permissions(self):
        with TemporaryDirectory() as directory:
            url = f"sqlite:///{directory}/test.sqlite"
            secret = "temporary-signing-secret-for-test-only"
            with patch.dict(os.environ, DATABASE_URL=url, JWT_SECRET=secret):
                app = FastAPI()
                app.state.settings = Settings()

            @app.get("/ranchos/{ranch_id}", dependencies=[Depends(require_ranch_access(RanchPermission.READ))])
            def read_ranch(ranch_id: str):
                return {"id": ranch_id}

            @app.patch("/ranchos/{ranch_id}", dependencies=[Depends(require_ranch_access(RanchPermission.EDIT))])
            def edit_ranch(ranch_id: str):
                return {"id": ranch_id}

            engine = auth_engine(url)
            metadata.create_all(engine)
            try:
                with engine.begin() as connection:
                    connection.execute(accounts.insert(), [
                        {"id": role, "username": role, "password_hash": "unused", "role": role}
                        for role in ("productor", "rama", "tecnico", "asociacion")
                    ])
                    connection.execute(account_ranches.insert(), [
                        {"account_id": account, "ranch_id": ranch, "can_read": True}
                        for account, ranch in (
                            ("productor", "A"), ("rama", "A"), ("tecnico", "A"), ("tecnico", "B"),
                            ("asociacion", "A"), ("asociacion", "B"),
                        )
                    ])

                def authorization(role):
                    # The JWT intentionally overstates access. The database is authoritative.
                    token = create_token(SessionClaims(sub=role, role=role, ranch_ids=["A", "B", "C"]), secret)
                    return {"Authorization": f"Bearer {token}"}

                with TestClient(app) as client:
                    self.assertEqual(client.get("/ranchos/A").status_code, 401)
                    self.assertEqual(client.get("/ranchos/A", headers=authorization("productor")).status_code, 200)
                    self.assertEqual(client.get("/ranchos/B", headers=authorization("productor")).status_code, 403)
                    self.assertEqual(client.get("/ranchos/A", headers=authorization("rama")).status_code, 200)
                    self.assertEqual(client.patch("/ranchos/A", headers=authorization("rama")).status_code, 403)
                    for role in ("tecnico", "asociacion"):
                        self.assertEqual(client.get("/ranchos/B", headers=authorization(role)).status_code, 200)
                        self.assertEqual(client.get("/ranchos/C", headers=authorization(role)).status_code, 403)
                    with engine.begin() as connection:
                        connection.execute(
                            account_ranches.update().where(account_ranches.c.account_id == "rama").values(can_edit=True)
                        )
                    self.assertEqual(client.patch("/ranchos/A", headers=authorization("rama")).status_code, 200)
            finally:
                engine.dispose()
                auth_engine.cache_clear()
