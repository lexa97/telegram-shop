"""Payment instruments and gateways (ТЗ-04)."""

import datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.main import Database


class PaymentGateway(Database.BASE):
    __tablename__ = "payment_gateways"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}", default="{}")
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    instruments: Mapped[list["PaymentInstrument"]] = relationship(
        "PaymentInstrument", back_populates="gateway", lazy="raise"
    )

    def __str__(self) -> str:
        return self.code or ""


class PaymentInstrument(Database.BASE):
    __tablename__ = "payment_instruments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0", default=0)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, server_default="RUB", default="RUB")
    gateway_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("payment_gateways.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    gateway: Mapped["PaymentGateway"] = relationship("PaymentGateway", back_populates="instruments", lazy="raise")

    __table_args__ = (UniqueConstraint("code", name="uq_payment_instruments_code"),)

    def __str__(self) -> str:
        return self.title or self.code
