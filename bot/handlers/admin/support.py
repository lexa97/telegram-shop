from html import escape as _esc

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database import Database
from bot.database.methods.audit import log_audit
from bot.database.methods.support import (
    SupportError,
    get_order_summary_for_ticket,
    get_ticket_for_staff,
    list_tickets_for_staff,
    set_ticket_status_staff,
    staff_reply,
)
from bot.database.models import Permission
from bot.filters import HasPermissionFilter
from bot.i18n import localize
from bot.keyboards.inline import back, simple_buttons
from bot.states import SupportFSM

router = Router()


def _staff_ticket_text(ticket, order_summary: dict | None) -> str:
    lines = [
        localize(
            "admin.support.detail",
            id=ticket.id,
            user_id=ticket.user_id,
            status=ticket.status,
        )
    ]
    if order_summary:
        lines.append(
            localize(
                "admin.support.order_linked",
                order_id=order_summary["id"],
                order_status=order_summary["status"],
                total_cents=order_summary["total_cents"],
            )
        )
    for msg in ticket.messages:
        role_key = "support.role.user" if msg.author_role == "user" else "support.role.staff"
        lines.append(
            localize(
                "support.message.line",
                role=localize(role_key),
                body=_esc(msg.body),
                date=msg.created_at.strftime("%Y-%m-%d %H:%M"),
            )
        )
    return "\n\n".join(lines)


@router.callback_query(F.data == "support_tickets", HasPermissionFilter(Permission.TICKETS_MANAGE))
async def support_ticket_list(call: CallbackQuery, state: FSMContext):
    await state.clear()
    async with Database().session() as s:
        tickets = await list_tickets_for_staff(s, limit=25)

    if not tickets:
        await call.message.edit_text(
            localize("admin.support.list_empty"),
            reply_markup=back("console"),
        )
        return

    buttons = [
        (
            localize(
                "admin.support.list_item",
                id=t.id,
                status=t.status,
                user_id=t.user_id,
            ),
            f"support_tk_{t.id}",
        )
        for t in tickets
    ]
    buttons.append((localize("btn.back"), "console"))
    await call.message.edit_text(
        localize("admin.support.list_title"),
        reply_markup=simple_buttons(buttons, per_row=1),
    )


@router.callback_query(
    F.data.startswith("support_tk_"),
    HasPermissionFilter(Permission.TICKETS_MANAGE),
)
async def support_ticket_view(call: CallbackQuery, state: FSMContext):
    try:
        ticket_id = int(call.data.split("_")[-1])
    except (ValueError, TypeError):
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return

    async with Database().session() as s:
        ticket = await get_ticket_for_staff(s, ticket_id)
        if ticket is None:
            await call.answer(localize("support.not_found"), show_alert=True)
            return
        order_summary = await get_order_summary_for_ticket(s, ticket.linked_order_id)

    buttons = [
        (localize("admin.support.btn.reply"), f"support_staff_reply_{ticket_id}"),
    ]
    if ticket.status != "closed":
        buttons.append(
            (localize("admin.support.btn.close"), f"support_st_closed_{ticket_id}")
        )
    else:
        buttons.append(
            (localize("admin.support.btn.reopen"), f"support_st_open_{ticket_id}")
        )
    buttons.append((localize("btn.back"), "support_tickets"))

    await call.message.edit_text(
        _staff_ticket_text(ticket, order_summary),
        parse_mode="HTML",
        reply_markup=simple_buttons(buttons, per_row=1),
    )


@router.callback_query(
    F.data.regexp(r"^support_st_(open|pending|closed)_(\d+)$"),
    HasPermissionFilter(Permission.TICKETS_MANAGE),
)
async def support_set_status(call: CallbackQuery):
    parts = call.data.split("_")
    status = parts[2]
    ticket_id = int(parts[3])
    try:
        async with Database().session() as s:
            ticket = await set_ticket_status_staff(s, ticket_id, status)
            await s.commit()
            user_id = ticket.user_id
    except SupportError as exc:
        await call.answer(localize(exc.code), show_alert=True)
        return

    await log_audit(
        "support_status",
        user_id=call.from_user.id,
        resource_type="SupportTicket",
        resource_id=str(ticket_id),
        details=f"status={status}",
    )
    await call.answer(localize("admin.support.status_updated"))

    async with Database().session() as s:
        ticket = await get_ticket_for_staff(s, ticket_id)
        order_summary = await get_order_summary_for_ticket(s, ticket.linked_order_id) if ticket else None

    if ticket is None:
        return

    buttons = [
        (localize("admin.support.btn.reply"), f"support_staff_reply_{ticket_id}"),
    ]
    if ticket.status != "closed":
        buttons.append(
            (localize("admin.support.btn.close"), f"support_st_closed_{ticket_id}")
        )
    else:
        buttons.append(
            (localize("admin.support.btn.reopen"), f"support_st_open_{ticket_id}")
        )
    buttons.append((localize("btn.back"), "support_tickets"))

    await call.message.edit_text(
        _staff_ticket_text(ticket, order_summary),
        parse_mode="HTML",
        reply_markup=simple_buttons(buttons, per_row=1),
    )


@router.callback_query(
    F.data.startswith("support_staff_reply_"),
    HasPermissionFilter(Permission.TICKETS_MANAGE),
)
async def support_staff_reply_start(call: CallbackQuery, state: FSMContext):
    try:
        ticket_id = int(call.data.split("_")[-1])
    except (ValueError, TypeError):
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return
    await state.update_data(staff_ticket_id=ticket_id)
    await state.set_state(SupportFSM.waiting_staff_reply)
    await call.message.edit_text(
        localize("admin.support.prompt.reply"),
        reply_markup=back(f"support_tk_{ticket_id}"),
    )


@router.message(
    SupportFSM.waiting_staff_reply,
    F.text,
    HasPermissionFilter(Permission.TICKETS_MANAGE),
)
async def support_staff_reply_message(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("staff_ticket_id")
    if not ticket_id:
        await state.clear()
        return

    staff_id = message.from_user.id
    try:
        async with Database().session() as s:
            msg = await staff_reply(s, int(ticket_id), staff_id, message.text)
            ticket = await get_ticket_for_staff(s, int(ticket_id))
            await s.commit()
            target_user_id = ticket.user_id
            body_text = msg.body
    except SupportError as exc:
        await message.answer(localize(exc.code))
        return

    await state.clear()
    await message.answer(localize("admin.support.reply_sent"))

    try:
        await message.bot.send_message(
            target_user_id,
            localize("support.staff_reply_notify", body=_esc(body_text)),
            parse_mode="HTML",
        )
    except Exception:
        pass

    await log_audit(
        "support_reply",
        user_id=staff_id,
        resource_type="SupportTicket",
        resource_id=str(ticket_id),
        details=f"to_user={target_user_id}",
    )
