from enum import Enum

from fastapi import Depends, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.models.auth import find_ranch_access
from app.routes.auth import authenticated_session
from app.schemas.auth import SessionClaims


class RanchPermission(str, Enum):
    READ = "can_read"
    CAPTURE = "can_capture"
    EDIT = "can_edit"
    EXPORT = "can_export"


def require_ranch_access(permission: RanchPermission):
    def check_access(
        ranch_id: str, request: Request, claims: SessionClaims = Depends(authenticated_session)
    ) -> SessionClaims:
        database_url = request.app.state.settings.database_url
        if not database_url:
            raise HTTPException(status_code=503, detail="Autorización no configurada")
        try:
            access = find_ranch_access(database_url, claims.sub, ranch_id)
        except (SQLAlchemyError, ImportError):
            raise HTTPException(status_code=503, detail="Autorización no disponible") from None

        if access and access["role"] == claims.role:
            if claims.role in {"productor", "tecnico", "asociacion"}:
                return claims
            if claims.role == "rama" and access[permission.value]:
                return claims

        raise HTTPException(status_code=403, detail="Sin permiso para este rancho")

    return check_access
