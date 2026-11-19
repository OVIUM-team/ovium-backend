import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib.exceptions import UnknownHashError
from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.models.auth import find_account
from app.schemas.auth import LoginRequest, SessionClaims, TokenResponse
from app.services.auth import DUMMY_HASH, create_token, password_hasher, read_token

class AuthRoute(APIRoute):
    def get_route_handler(self):
        handle = super().get_route_handler()

        async def handle_auth_request(request: Request):
            try:
                return await handle(request)
            except RequestValidationError:
                return JSONResponse(status_code=422, content={"detail": "Solicitud inválida"})

        return handle_auth_request


router = APIRouter(prefix="/auth", tags=["auth"], route_class=AuthRoute)
bearer_scheme = HTTPBearer(auto_error=False)


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(status_code=401, detail=detail, headers={"WWW-Authenticate": "Bearer"})


def signing_secret(request: Request) -> str:
    value = request.app.state.settings.jwt_secret
    if not value or len(value.encode()) < 32:
        raise HTTPException(status_code=503, detail="Autenticación no configurada")
    return value


@router.post("/login", response_model=TokenResponse)
def login(
    credentials: LoginRequest, request: Request, secret: str = Depends(signing_secret)
) -> TokenResponse:
    database_url = request.app.state.settings.database_url
    if not database_url:
        raise HTTPException(status_code=503, detail="Autenticación no configurada")
    try:
        account = find_account(database_url, credentials.username)
    except (SQLAlchemyError, ImportError):
        raise HTTPException(status_code=503, detail="Autenticación no disponible") from None

    stored_hash = account[1] if account else DUMMY_HASH
    try:
        valid_password = password_hasher.verify(credentials.password.get_secret_value(), stored_hash)
    except UnknownHashError:
        valid_password = False

    if not valid_password or account is None:
        raise unauthorized("Credenciales inválidas")

    account_id, _, role, ranch_ids = account
    claims = SessionClaims(sub=account_id, role=role, ranch_ids=ranch_ids)
    return TokenResponse(access_token=create_token(claims, secret))


@router.get("/session", response_model=SessionClaims)
def session(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    secret: str = Depends(signing_secret),
) -> SessionClaims:
    if credentials is None:
        raise unauthorized("Token requerido")
    try:
        return read_token(credentials.credentials, secret)
    except jwt.ExpiredSignatureError:
        raise unauthorized("Sesión expirada") from None
    except (jwt.InvalidTokenError, ValidationError):
        raise unauthorized("Token inválido") from None
