"""Support tickets (ТЗ-09)."""

import datetime
from typing import Optional

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from bot.database.main import Database


class TicketStatus:
    OPEN = "open"
    PENDING = "pending"
    CLOSED = "closed"

    ALL = frozenset({OPEN, PENDING, CLOSED})
    ACTIVE = frozenset({OPEN, PENDING})


class MessageAuthorRole:
    USER = "user"
    STAFF = "staff"

    ALL = frozenset({USER, STAFF})


class SupportTicket(Database.BASE):
    __tablename__ = "support_tickets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, server_default=TicketStatus.OPEN)
    linked_order_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    messages: Mapped[list["SupportMessage"]] = relationship(
        "SupportMessage",
        back_populates="ticket",
        lazy="raise",
        order_by="SupportMessage.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            f"status IN ({','.join(repr(s) for s in TicketStatus.ALL)})",
            name="ck_support_tickets_status",
        ),
        Index("ix_support_tickets_user_status", "user_id", "status"),
    )

    def __str__(self) -> str:
        return f"Ticket#{self.id}"


class SupportMessage(Database.BASE):
    __tablename__ = "support_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_role: Mapped[str] = mapped_column(String(16), nullable=False)
    author_user_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    ticket: Mapped["SupportTicket"] = relationship(
        "SupportTicket", back_populates="messages", lazy="raise"
    )

    __table_args__ = (
        CheckConstraint(
            f"author_role IN ({','.join(repr(r) for r in MessageAuthorRole.ALL)})",
            name="ck_support_messages_author_role",
        ),
        Index("ix_support_messages_ticket_created", "ticket_id", "created_at"),
    )
