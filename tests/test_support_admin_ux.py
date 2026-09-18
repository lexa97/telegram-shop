"""ТЗ-09: веб-панель — ответ по тикету без ручного ввода ID."""

from starlette.requests import Request

from bot.web.admin import SupportTicketAdmin


def _request_with_pks(pks: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/admin/support-ticket/action/messages_reply",
        "query_string": f"pks={pks}".encode(),
        "headers": [],
        "scheme": "http",
        "server": ("test", 80),
        "client": ("test", 0),
    }
    return Request(scope)


async def test_messages_reply_action_redirects_to_thread():
    admin_view = SupportTicketAdmin()
    resp = await admin_view.messages_reply_action(_request_with_pks("42"))
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/support-reply?ticket_id=42"


async def test_messages_reply_action_without_pk_goes_to_picker():
    admin_view = SupportTicketAdmin()
    resp = await admin_view.messages_reply_action(_request_with_pks(""))
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/support-reply"
