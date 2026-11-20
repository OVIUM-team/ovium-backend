from pydantic import BaseModel, Field, SecretStr


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=255)
    password: SecretStr = Field(min_length=1, max_length=1024)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class SessionClaims(BaseModel):
    sub: str
    role: str
    ranch_ids: list[str]
