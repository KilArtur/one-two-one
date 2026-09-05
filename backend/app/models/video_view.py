"""Аудит фактического воспроизведения записей внутренними пользователями."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class VideoViewLog(Base):
    __tablename__ = "video_view_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    answer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("answer.id", ondelete="CASCADE"), index=True
    )
    viewer: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(40))
    position_sec: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
