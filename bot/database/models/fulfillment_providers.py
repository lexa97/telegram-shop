"""Fulfillment providers and goods links (ТЗ-05). Not payment gateways."""

import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.main import Database


class FulfillmentProvider(Database.BASE):
    __tablename__ = "fulfillment_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)
    config_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}", default="{}")
    default_timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="30", default=30)
    default_retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3", default=3)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    links: Mapped[list["GoodsProviderLink"]] = relationship(
        "GoodsProviderLink", back_populates="provider", lazy="raise"
    )

    def __str__(self) -> str:
        return self.name or self.code


class GoodsProviderLink(Database.BASE):
    __tablename__ = "goods_provider_links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goods_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("goods.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("fulfillment_providers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    external_product_id: Mapped[str] = mapped_column(String(128), nullable=False)
    cost_cents: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    request_params: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}", default="{}")
    result_mapping: Mapped[str] = mapped_column(Text, nullable=False, server_default="{}", default="{}")
    timeout_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    retry_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delivery_template: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="100", default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true", default=True)

    provider: Mapped["FulfillmentProvider"] = relationship(
        "FulfillmentProvider", back_populates="links", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint(
            "goods_id",
            "provider_id",
            "external_product_id",
            name="uq_goods_provider_external_product",
        ),
    )

    def __str__(self) -> str:
        return f"link g={self.goods_id} p={self.provider_id}"
