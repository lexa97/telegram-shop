"""Custom SQLAdmin pages (ТЗ-10): stock import, sales stats."""

from __future__ import annotations

from html import escape

from sqladmin import BaseView, expose
from starlette.requests import Request
from starlette.responses import HTMLResponse, RedirectResponse

from bot.web.panel_template import render_admin_page

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
    category = "Catalog"

    @expose("/stock-import", methods=["GET", "POST"])
    async def stock_import(self, request: Request):
        flash_message = ""
        flash_error = False
        values_text = ""
        is_infinity = False
        selected_goods_id = 0
        selected_item_name = ""

        goods_id_raw = request.query_params.get("goods_id") or ""
        try:
            selected_goods_id = int(goods_id_raw) if goods_id_raw else 0
        except ValueError:
            selected_goods_id = 0
        selected_item_name = (request.query_params.get("item_name") or "").strip()

        if request.method == "POST":
            form = await request.form()
            item_name = (form.get("item_name") or "").strip()
            selected_item_name = item_name
            raw = form.get("values_text") or ""
            values_text = raw
            is_infinity = form.get("is_infinity") == "on"
            lines = raw.replace("\r\n", "\n").split("\n")

            added, skip_db, skip_batch, skip_invalid = await add_values_bulk(
                item_name, lines, is_infinity=is_infinity
            )
            if not item_name:
                flash_message = "Выберите товар."
                flash_error = True
            elif added == 0 and skip_db == 0 and skip_batch == 0 and skip_invalid == len(lines):
                flash_message = "Нет валидных строк для импорта."
                flash_error = True
            else:
                flash_message = (
                    f"Добавлено: {added}; дубликаты в БД: {skip_db}; "
                    f"дубликаты в файле: {skip_batch}; пустые/невалидные: {skip_invalid}."
                )
                if not flash_error:
                    values_text = ""

        async with Database().session() as session:
            rows = (
                await session.execute(select(Goods.id, Goods.name).order_by(Goods.name))
            ).all()
        goods = [{"id": gid, "name": name} for gid, name in rows]
        if selected_goods_id and not selected_item_name:
            for g in goods:
                if g["id"] == selected_goods_id:
                    selected_item_name = g["name"]
                    break

        return await render_admin_page(
            self,
            request,
            "stock_import.html",
            title="Catalog",
            subtitle="Массовый импорт склада",
            goods=goods,
            flash_message=flash_message,
            flash_error=flash_error,
            values_text=values_text,
            is_infinity=is_infinity,
            selected_goods_id=selected_goods_id,
            selected_item_name=selected_item_name,
        )


class SupportReplyView(BaseView):
    name = "Support reply"
    icon = "fa-solid fa-reply"

    @expose("/support-reply", methods=["GET", "POST"])
    async def support_reply(self, request: Request) -> HTMLResponse:
        from bot.database.methods.support import SupportError, staff_reply
        from bot.database.methods.audit import log_audit
        from bot.web.admin import _notifier_bot
        from bot.i18n import localize

        ticket_id_raw = request.query_params.get("ticket_id") or ""
        message = ""
        error = False

        if request.method == "POST":
            form = await request.form()
            try:
                ticket_id = int(form.get("ticket_id") or 0)
            except ValueError:
                ticket_id = 0
            body = form.get("body") or ""
            staff_id = int(form.get("staff_id") or "0")

            try:
                async with Database().session() as session:
                    msg = await staff_reply(session, ticket_id, staff_id, body)
                    ticket = msg.ticket if hasattr(msg, "ticket") else None
                    if ticket is None:
                        from bot.database.methods.support import get_ticket_for_staff

                        ticket = await get_ticket_for_staff(session, ticket_id)
                    target_user = ticket.user_id if ticket else None
                    body_text = msg.body
                    await session.commit()
            except SupportError as exc:
                message = exc.code
                error = True
            else:
                message = "Reply saved."
                await log_audit(
                    "support_reply_web",
                    user_id=staff_id,
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
            message = "Reply sent to user (if Telegram delivery succeeded)."
        try:
            ticket_id = int(ticket_id_raw) if ticket_id_raw else 0
        except ValueError:
            ticket_id = 0

        from bot.web.admin_helpers import web_panel_operator_id

        default_staff = web_panel_operator_id()
        msg_html = ""
        if message:
            msg_html = f'<div class="msg{" err" if error else ""}">{escape(message)}</div>'

        body = f"""
{msg_html}
<form method="post">
<label>Ticket ID</label>
<input name="ticket_id" value="{ticket_id or ""}" required />
<label>Staff Telegram ID (audit)</label>
<input name="staff_id" value="{default_staff}" required />
<label>Message</label>
<textarea name="body" rows="6" required></textarea>
<button type="submit">Send reply</button>
</form>
"""
        return HTMLResponse(_page_shell("Support reply", body))
