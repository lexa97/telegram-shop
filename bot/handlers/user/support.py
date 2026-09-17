from html import escape as _esc

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.database import Database
from bot.database.methods.support import (
    SupportError,
    add_user_message,
    close_ticket_by_user,
    create_ticket,
    get_active_ticket_for_user,
    get_ticket_for_user,
    link_order_to_ticket,
)
from bot.i18n import localize
from bot.keyboards.inline import back, simple_buttons
from bot.states import SupportFSM

router = Router()


def _format_history(ticket) -> str:
    lines = [
        localize(
            "support.ticket.header",
            id=ticket.id,
            status=ticket.status,
            order_id=ticket.linked_order_id or "—",
        )
    ]
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


@router.callback_query(F.data == "support")
async def support_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    user_id = call.from_user.id
    async with Database().session() as s:
        active = await get_active_ticket_for_user(s, user_id)
        if active:
            ticket = await get_ticket_for_user(s, active.id, user_id)
        else:
            ticket = None

    if ticket is None:
        buttons = [
            (localize("support.btn.new"), "support_new"),
            (localize("btn.back"), "back_to_menu"),
        ]
        await call.message.edit_text(
            localize("support.intro"),
            reply_markup=simple_buttons(buttons, per_row=1),
        )
        return

    buttons = [
        (localize("support.btn.reply"), f"support_reply_{ticket.id}"),
        (localize("support.btn.link_order"), f"support_link_{ticket.id}"),
        (localize("support.btn.close"), f"support_close_{ticket.id}"),
        (localize("btn.back"), "back_to_menu"),
    ]
    await call.message.edit_text(
        _format_history(ticket),
        parse_mode="HTML",
        reply_markup=simple_buttons(buttons, per_row=1),
    )


@router.callback_query(F.data == "support_new")
async def support_new_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text(
        localize("support.prompt.new_body"),
        reply_markup=back("support"),
    )
    await state.set_state(SupportFSM.waiting_new_body)


@router.message(SupportFSM.waiting_new_body, F.text)
async def support_new_body(message: Message, state: FSMContext):
    user_id = message.from_user.id
    try:
        async with Database().session() as s:
            ticket = await create_ticket(s, user_id, message.text)
            await s.commit()
            tid = ticket.id
    except SupportError as exc:
        await message.answer(localize(exc.code))
        return

    await state.clear()
    await message.answer(localize("support.created", id=tid), reply_markup=back("support"))


@router.callback_query(F.data.startswith("support_reply_"))
async def support_reply_start(call: CallbackQuery, state: FSMContext):
    try:
        ticket_id = int(call.data.split("_")[-1])
    except (ValueError, TypeError):
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return
    await state.update_data(support_ticket_id=ticket_id)
    await state.set_state(SupportFSM.waiting_message)
    await call.message.edit_text(
        localize("support.prompt.reply"),
        reply_markup=back("support"),
    )


@router.message(SupportFSM.waiting_message, F.text)
async def support_reply_message(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("support_ticket_id")
    if not ticket_id:
        await state.clear()
        return
    user_id = message.from_user.id
    try:
        async with Database().session() as s:
            await add_user_message(s, int(ticket_id), user_id, message.text)
            await s.commit()
    except SupportError as exc:
        await message.answer(localize(exc.code))
        return

    await state.clear()
    await message.answer(localize("support.message_sent"), reply_markup=back("support"))


@router.callback_query(F.data.startswith("support_close_"))
async def support_close(call: CallbackQuery, state: FSMContext):
    try:
        ticket_id = int(call.data.split("_")[-1])
    except (ValueError, TypeError):
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return
    user_id = call.from_user.id
    try:
        async with Database().session() as s:
            await close_ticket_by_user(s, ticket_id, user_id)
            await s.commit()
    except SupportError as exc:
        await call.answer(localize(exc.code), show_alert=True)
        return

    await state.clear()
    await call.message.edit_text(
        localize("support.closed", id=ticket_id),
        reply_markup=back("back_to_menu"),
    )


@router.callback_query(F.data.startswith("support_link_"))
async def support_link_start(call: CallbackQuery, state: FSMContext):
    try:
        ticket_id = int(call.data.split("_")[-1])
    except (ValueError, TypeError):
        await call.answer(localize("errors.invalid_data"), show_alert=True)
        return
    await state.update_data(support_ticket_id=ticket_id)
    await state.set_state(SupportFSM.waiting_order_id)
    await call.message.edit_text(
        localize("support.prompt.order_id"),
        reply_markup=back("support"),
    )


@router.message(SupportFSM.waiting_order_id, F.text)
async def support_link_order(message: Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("support_ticket_id")
    if not ticket_id:
        await state.clear()
        return
    if not message.text.strip().isdigit():
        await message.answer(localize("support.invalid_order_id"))
        return
    user_id = message.from_user.id
    try:
        async with Database().session() as s:
            await link_order_to_ticket(s, int(ticket_id), user_id, int(message.text.strip()))
            await s.commit()
    except SupportError as exc:
        await message.answer(localize(exc.code))
        return

    await state.clear()
    await message.answer(
        localize("support.order_linked", order_id=message.text.strip()),
        reply_markup=back("support"),
    )
