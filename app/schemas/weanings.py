from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class WeaningCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID = Field(default_factory=uuid4)
    fecha: date
    destino: Literal["engorda", "venta", "recria"]
    pesaje_id: UUID | None = None
    peso: Decimal | None = Field(default=None, gt=0, max_digits=8, decimal_places=2)

    @model_validator(mode="after")
    def require_weight(self):
        if (self.pesaje_id is None) == (self.peso is None):
            raise ValueError("Envía peso o pesaje_id, exactamente uno")
        return self
