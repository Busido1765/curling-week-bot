import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column

from bot.db.base import Base


class RegistrationStatus(str, enum.Enum):
    none = "NONE"
    token_verified = "TOKEN_VERIFIED"
    subscription_verified = "SUBSCRIPTION_VERIFIED"
    confirmed = "CONFIRMED"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    tg_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False)
    username: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[RegistrationStatus] = mapped_column(
        Enum(RegistrationStatus), default=RegistrationStatus.none, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )
