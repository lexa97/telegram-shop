"""ТЗ-03: веб-панель — массовый импорт склада в layout SQLAdmin."""

from starlette.requests import Request

from bot.web.admin import GoodsAdmin


def _request_with_pks(pks: str) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/admin/goods/action/bulk_stock_import",
        "query_string": f"pks={pks}".encode(),
        "headers": [],
        "scheme": "http",
        "server": ("test", 80),
        "client": ("test", 0),
    }
    return Request(scope)


async def test_bulk_stock_import_action_redirects_with_goods_id():
    view = GoodsAdmin()
    resp = await view.bulk_stock_import_action(_request_with_pks("7"))
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/stock-import?goods_id=7"


async def test_bulk_stock_import_action_without_pk_goes_to_import_page():
    view = GoodsAdmin()
    resp = await view.bulk_stock_import_action(_request_with_pks(""))
    assert resp.status_code == 303
    assert resp.headers["location"] == "/admin/stock-import"
