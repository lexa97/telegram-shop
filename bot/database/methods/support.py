"""Support ticket persistence (ТЗ-09)."""

from __future__ import annotations

import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from bot.database import Database
from bot.database.models.orders import Order
from bot.database.models.support import (
    MessageAuthorRole,
    SupportMessage,
    SupportTicket,
    TicketStatus,
)

MAX_BODY_LEN = 4000


class SupportError(Exception):
    """Domain error with a user-facing i18n key in `code`."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _trim_body(body: str) -> str:
    text = (body or "").strip()
    if not text:
        raise SupportError("support.empty_message")
    if len(text) > MAX_BODY_LEN:
        raise SupportError("support.message_too_long")
    return text


async def get_active_ticket_for_user(
    session: AsyncSession, user_id: int
) -> Optional[SupportTicket]:
    return (
        await session.execute(
            select(SupportTicket)
            .where(
                SupportTicket.user_id == user_id,
                SupportTicket.status.in_(TicketStatus.ACTIVE),
            )
            .order_by(SupportTicket.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def create_ticket(
    session: AsyncSession,
    user_id: int,
    body: str,
    *,
    linked_order_id: Optional[int] = None,
) -> SupportTicket:
    if await get_active_ticket_for_user(session, user_id) is not None:
        raise SupportError("support.active_ticket_exists")

    if linked_order_id is not None:
        order = (
            await session.execute(
                select(Order).where(
                    Order.id == linked_order_id,
                    Order.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if order is None:
            raise SupportError("support.order_not_found")

    text = _trim_body(body)
    ticket = SupportTicket(
        user_id=user_id,
        status=TicketStatus.OPEN,
        linked_order_id=linked_order_id,
    )
    session.add(ticket)
    await session.flush()
    session.add(
        SupportMessage(
            ticket_id=ticket.id,
            author_role=MessageAuthorRole.USER,
            author_user_id=user_id,
            body=text,
        )
    )
    await session.flush()
    return ticket


async def get_ticket_for_user(
    session: AsyncSession, ticket_id: int, user_id: int
) -> Optional[SupportTicket]:
    return (
        await session.execute(
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages))
            .where(SupportTicket.id == ticket_id, SupportTicket.user_id == user_id)
        )
    ).scalar_one_or_none()


async def add_user_message(
    session: AsyncSession, ticket_id: int, user_id: int, body: str
) -> SupportMessage:
    ticket = await get_ticket_for_user(session, ticket_id, user_id)
    if ticket is None:
        raise SupportError("support.not_found")
    if ticket.status == TicketStatus.CLOSED:
        raise SupportError("support.ticket_closed")

    text = _trim_body(body)
    ticket.status = TicketStatus.OPEN
    ticket.updated_at = datetime.datetime.now(datetime.timezone.utc)
    msg = SupportMessage(
        ticket_id=ticket.id,
        author_role=MessageAuthorRole.USER,
        author_user_id=user_id,
        body=text,
    )
    session.add(msg)
    await session.flush()
    return msg


async def close_ticket_by_user(
    session: AsyncSession, ticket_id: int, user_id: int
) -> SupportTicket:
    ticket = await get_ticket_for_user(session, ticket_id, user_id)
    if ticket is None:
        raise SupportError("support.not_found")
    ticket.status = TicketStatus.CLOSED
    ticket.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()
    return ticket


async def link_order_to_ticket(
    session: AsyncSession, ticket_id: int, user_id: int, order_id: int
) -> SupportTicket:
    ticket = await get_ticket_for_user(session, ticket_id, user_id)
    if ticket is None:
        raise SupportError("support.not_found")
    if ticket.status == TicketStatus.CLOSED:
        raise SupportError("support.ticket_closed")

    order = (
        await session.execute(
            select(Order).where(Order.id == order_id, Order.user_id == user_id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise SupportError("support.order_not_found")

    ticket.linked_order_id = order_id
    await session.flush()
    return ticket


async def list_tickets_for_staff(
    session: AsyncSession,
    *,
    status: Optional[str] = None,
    limit: int = 30,
    offset: int = 0,
) -> list[SupportTicket]:
    q = select(SupportTicket).order_by(SupportTicket.updated_at.desc())
    if status:
        q = q.where(SupportTicket.status == status)
    q = q.offset(offset).limit(limit)
    return list((await session.execute(q)).scalars().all())


async def get_ticket_for_staff(
    session: AsyncSession, ticket_id: int
) -> Optional[SupportTicket]:
    return (
        await session.execute(
            select(SupportTicket)
            .options(selectinload(SupportTicket.messages))
            .where(SupportTicket.id == ticket_id)
        )
    ).scalar_one_or_none()


async def staff_reply(
    session: AsyncSession,
    ticket_id: int,
    staff_user_id: int,
    body: str,
) -> SupportMessage:
    ticket = await get_ticket_for_staff(session, ticket_id)
    if ticket is None:
        raise SupportError("support.not_found")
    if ticket.status == TicketStatus.CLOSED:
        raise SupportError("support.ticket_closed")

    text = _trim_body(body)
    ticket.status = TicketStatus.PENDING
    ticket.updated_at = datetime.datetime.now(datetime.timezone.utc)
    msg = SupportMessage(
        ticket_id=ticket.id,
        author_role=MessageAuthorRole.STAFF,
        author_user_id=staff_user_id,
        body=text,
    )
    session.add(msg)
    await session.flush()
    return msg


async def set_ticket_status_staff(
    session: AsyncSession, ticket_id: int, status: str
) -> SupportTicket:
    if status not in TicketStatus.ALL:
        raise SupportError("support.invalid_status")
    ticket = await get_ticket_for_staff(session, ticket_id)
    if ticket is None:
        raise SupportError("support.not_found")
    ticket.status = status
    ticket.updated_at = datetime.datetime.now(datetime.timezone.utc)
    await session.flush()
    return ticket


async def get_order_summary_for_ticket(
    session: AsyncSession, order_id: Optional[int]
) -> Optional[dict]:
    if order_id is None:
        return None
    order = (
        await session.execute(select(Order).where(Order.id == order_id))
    ).scalar_one_or_none()
    if order is None:
        return None
    return {
        "id": order.id,
        "status": order.status,
        "total_cents": order.total_cents,
        "user_id": order.user_id,
    }
