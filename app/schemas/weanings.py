from datetime import date
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class WeaningCreate(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    fecha: date
    destino: Literal["engorda", "venta", "recria"]
    pesaje_id: UUID | None = None
