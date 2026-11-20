from datetime import datetime, timedelta, timezone
from secrets import token_urlsafe

import jwt
from pwdlib import PasswordHash

from app.schemas.auth import SessionClaims

ALGORITHM = "HS256"
ISSUER = "ovium-api"
AUDIENCE = "ovium"
TOKEN_TTL = timedelta(minutes=30)
password_hasher = PasswordHash.recommended()
DUMMY_HASH = password_hasher.hash(token_urlsafe(32))


def create_token(claims: SessionClaims, secret: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            **claims.model_dump(),
            "iss": ISSUER,
            "aud": AUDIENCE,
            "iat": now,
            "exp": now + TOKEN_TTL,
        },
        secret,
        algorithm=ALGORITHM,
    )


def read_token(token: str, secret: str) -> SessionClaims:
    payload = jwt.decode(
        token,
        secret,
        algorithms=[ALGORITHM],
        issuer=ISSUER,
        audience=AUDIENCE,
        options={"require": ["sub", "iat", "exp", "iss", "aud", "role", "ranch_ids"]},
    )
    return SessionClaims.model_validate(payload)
