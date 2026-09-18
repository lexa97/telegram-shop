"""Custom SQLAdmin pages (ТЗ-10): stock import, sales stats."""

from __future__ import annotations

from html import escape

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from bot.database import Database
from bot.database.methods.create import add_values_bulk
from bot.database.models.main import Goods
from bot.misc import EnvKeys
from bot.money import format_cents_for_ui
from bot.web.admin_helpers import aggregate_completed_order_stats
from sqlalchemy import select


def _page_shell(title: str, body: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{escape(title)}</title>
<style>
body {{ font-family: system-ui, sans-serif; margin: 2rem; max-width: 52rem; }}
label {{ display: block; margin-top: 1rem; font-weight: 600; }}
textarea, select {{ width: 100%; margin-top: 0.25rem; }}
button {{ margin-top: 1rem; padding: 0.5rem 1rem; }}
.msg {{ padding: 0.75rem; background: #ecfdf5; border-radius: 6px; margin-bottom: 1rem; }}
.err {{ background: #fef2f2; }}
a {{ color: #2563eb; }}
</style></head><body>
<p><a href="/admin">← Admin</a></p>
<h1>{escape(title)}</h1>
{body}
</body></html>"""


class SalesStatsView(BaseView):
    name = "Sales statistics"
    icon = "fa-solid fa-chart-line"

    @expose("/sales-stats", methods=["GET"])
    async def sales_stats(self, request: Request) -> HTMLResponse:
        async with Database().session() as session:
            stats = await aggregate_completed_order_stats(session)

        body = f"""
<p>Completed orders only; profit from <code>orders.profit_cents</code> snapshot.</p>
<table border="1" cellpadding="8" cellspacing="0">
<tr><th>Completed orders</th><td>{stats['completed_orders']}</td></tr>
<tr><th>Revenue</th><td>{escape(format_cents_for_ui(stats['revenue_cents']))}</td></tr>
<tr><th>Profit</th><td>{escape(format_cents_for_ui(stats['profit_cents']))}</td></tr>
</table>
"""
        return HTMLResponse(_page_shell("Sales statistics", body))


class StockImportView(BaseView):
    name = "Stock import"
    icon = "fa-solid fa-file-import"

    @expose("/stock-import", methods=["GET", "POST"])
    async def stock_import(self, request: Request) -> HTMLResponse:
        message = ""
        error = False
        goods_options = ""

        async with Database().session() as session:
            rows = (
                await session.execute(select(Goods.id, Goods.name).order_by(Goods.name))
            ).all()
        for gid, name in rows:
            goods_options += f'<option value="{escape(name)}">{escape(name)} (id={gid})</option>\n'

        if request.method == "POST":
            form = await request.form()
            item_name = (form.get("item_name") or "").strip()
            raw = form.get("values_text") or ""
            is_infinity = form.get("is_infinity") == "on"
            lines = raw.replace("\r\n", "\n").split("\n")

            added, skip_db, skip_batch, skip_invalid = await add_values_bulk(
                item_name, lines, is_infinity=is_infinity
            )
            if not item_name:
                message = "Select a product."
                error = True
            elif added == 0 and skip_db == 0 and skip_batch == 0 and skip_invalid == len(lines):
                message = "No valid lines to import."
                error = True
            else:
                message = (
                    f"Added {added}; skipped duplicates in DB: {skip_db}; "
                    f"duplicates in batch: {skip_batch}; invalid/empty: {skip_invalid}."
                )
        msg_html = ""
        if message:
            cls = "msg err" if error else "msg"
            msg_html = f'<div class="{cls}">{escape(message)}</div>'

        body = f"""
{msg_html}
<form method="post">
<label>Product (by name)</label>
<select name="item_name" required>
<option value="">— choose —</option>
{goods_options}
</select>
<label>Stock values (one per line)</label>
<textarea name="values_text" rows="12" placeholder="key1&#10;key2&#10;..."></textarea>
<label><input type="checkbox" name="is_infinity"> Unlimited stock (single shared value)</label>
<button type="submit">Import</button>
</form>
<p>Uses <code>add_values_bulk</code> (ТЗ-03).</p>
"""
        return HTMLResponse(_page_shell("Bulk stock import", body))


_SUPPORT_ERROR_TEXT = {
    "support.not_found": "Тикет не найден.",
    "support.ticket_closed": "Тикет закрыт — сначала смените статус.",
}


def _support_flash(code_or_text: str) -> tuple[str, bool]:
    if code_or_text in _SUPPORT_ERROR_TEXT:
        return _SUPPORT_ERROR_TEXT[code_or_text], True
    return code_or_text, False


class SupportReplyView(BaseView):
    """Переписка и ответ оператора (открывается из Support Tickets, не из меню)."""

    name = "Support reply"
    icon = "fa-solid fa-reply"
    category = "Support"

    def is_visible(self, request: Request) -> bool:
        return False

    async def _template(
        self, request: Request, context: dict
    ):
        base = {
            "admin": self._admin_ref,
            "title": "Support",
            "subtitle": "Переписка и ответ",
            "request": request,
        }
        base.update(context)
        return await self.templates.TemplateResponse(
            request, "support_reply.html", base
        )

    @expose("/support-reply", methods=["GET", "POST"])
    async def support_reply(self, request: Request):
        from bot.database.methods.support import (
            SupportError,
            get_ticket_for_staff,
            list_tickets_for_staff,
            staff_reply,
        )
        from bot.database.methods.audit import log_audit
        from bot.web.admin import _notifier_bot
        from bot.i18n import localize
        from bot.web.admin_helpers import web_panel_operator_id

        staff_id = web_panel_operator_id()
        flash_message = ""
        flash_error = False

        if request.method == "POST":
            form = await request.form()
            try:
                ticket_id = int(form.get("ticket_id") or 0)
            except ValueError:
                ticket_id = 0
            body = form.get("body") or ""
            try:
                form_staff = int(form.get("staff_id") or staff_id)
            except ValueError:
                form_staff = staff_id

            try:
                async with Database().session() as session:
                    msg = await staff_reply(session, ticket_id, form_staff, body)
                    ticket = await get_ticket_for_staff(session, ticket_id)
                    target_user = ticket.user_id if ticket else None
                    body_text = msg.body
                    await session.commit()
            except SupportError as exc:
                flash_message, flash_error = _support_flash(exc.code)
            else:
                await log_audit(
                    "support_reply_web",
                    user_id=form_staff,
                    resource_type="SupportTicket",
                    resource_id=str(ticket_id),
                )
                if _notifier_bot and target_user:
                    try:
                        await _notifier_bot.send_message(
                            target_user,
                            localize("support.staff_reply_notify", body=body_text),
                            parse_mode="HTML",
                        )
                    except Exception:
                        pass
                return RedirectResponse(
                    url=f"/admin/support-reply?ticket_id={ticket_id}&ok=1",
                    status_code=303,
                )

        if request.query_params.get("ok") == "1":
            flash_message = "Ответ сохранён и отправлен пользователю (если Telegram доставил сообщение)."
        ticket_id_raw = request.query_params.get("ticket_id") or ""
        try:
            ticket_id = int(ticket_id_raw) if ticket_id_raw else 0
        except ValueError:
            ticket_id = 0

        ticket = None
        messages = []
        ticket_rows = []

        async with Database().session() as session:
            if ticket_id:
                ticket = await get_ticket_for_staff(session, ticket_id)
                if ticket is None:
                    flash_message, flash_error = _support_flash("support.not_found")
                else:
                    messages = sorted(
                        ticket.messages,
                        key=lambda m: m.created_at or "",
                    )
            else:
                ticket_rows = await list_tickets_for_staff(session, limit=50)

        return await self._template(
            request,
            {
                "ticket": ticket,
                "messages": messages,
                "ticket_rows": ticket_rows,
                "staff_id": staff_id,
                "flash_message": flash_message,
                "flash_error": flash_error,
            },
        )
