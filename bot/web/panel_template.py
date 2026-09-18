"""Shared SQLAdmin Jinja context for custom BaseView pages."""

from __future__ import annotations

from starlette.requests import Request


async def render_admin_page(
    view,
    request: Request,
    template_name: str,
    *,
    title: str,
    subtitle: str = "",
    **context,
):
    payload = {
        "admin": view._admin_ref,
        "title": title,
        "subtitle": subtitle,
        "request": request,
    }
    payload.update(context)
    return await view.templates.TemplateResponse(request, template_name, payload)
