from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

HealthType = Literal["vacunacion", "vitaminas", "selenio", "desparasitacion", "tratamiento"]


class HealthData(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    fecha: date
    tipo: HealthType
    producto: str = Field(min_length=1, max_length=255)
    dosis: str = Field(min_length=1, max_length=128)
    observaciones: str | None = Field(default=None, max_length=1000)


class HealthCreate(HealthData):
    id: UUID = Field(default_factory=uuid4)


class HealthTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    animal_id: UUID
    id: UUID = Field(default_factory=uuid4)


class HealthBatch(HealthData):
    animales: list[HealthTarget] = Field(min_length=1, max_length=500)

    @field_validator("animales")
    @classmethod
    def distinct_targets(cls, values):
        if len({v.animal_id for v in values}) != len(values) or len({v.id for v in values}) != len(values):
            raise ValueError("No se permiten animales ni identificadores de evento repetidos")
        return values
