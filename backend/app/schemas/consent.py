"""Схемы явного согласия на запись и обработку данных."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, StrictBool, field_validator


class ConsentRequest(BaseModel):
    """Принимает только явное булево согласие."""

    model_config = ConfigDict(extra="forbid")
    accepted: StrictBool

    @field_validator("accepted")
    @classmethod
    def must_accept(cls, value: bool) -> bool:
        if not value:
            raise ValueError("Consent must be accepted to continue")
        return value


class ConsentRead(BaseModel):
    """Время согласия, установленное сервером."""

    consent_given_at: datetime | None
