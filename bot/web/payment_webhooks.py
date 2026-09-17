import json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from bot.database import Database
from bot.database.models.payment_config import PaymentGateway
from bot.payments.gateways.platega import gateway_config_from_json
from bot.payments.service import finalize_platega_webhook
from sqlalchemy import select

logger = logging.getLogger(__name__)


async def platega_webhook(request: Request) -> Response:
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    async with Database().session() as s:
        gw = (
            await s.execute(select(PaymentGateway).where(PaymentGateway.code == "platega"))
        ).scalars().first()
    if not gw or not gw.enabled:
        return JSONResponse({"error": "gateway_disabled"}, status_code=503)

    cfg = gateway_config_from_json(gw.config_json)
    status, detail = await finalize_platega_webhook(
        cfg,
        body,
        request.headers.get("X-MerchantId"),
        request.headers.get("X-Secret"),
    )
    if status >= 400:
        return JSONResponse({"error": detail}, status_code=status)
    return JSONResponse({"status": detail}, status_code=status)
