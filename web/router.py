from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse

from config.settings import load_settings

from .html import customer_chat_page_html
from .service import render_welcome_message


router = APIRouter()


@router.get("/web", response_class=HTMLResponse)
def web_chat_page(
    username: str = Query("", description="用户名（可为空）"),
):
    runtime = load_settings()
    if not runtime.web_enabled:
        return HTMLResponse(content="")
    welcome_message = render_welcome_message(runtime.web_welcome_template, username)
    return HTMLResponse(
        customer_chat_page_html(
            username=username,
            chat_title=runtime.web_chat_title,
            welcome_message=welcome_message,
            quick_phrases=list(runtime.web_quick_phrases),
        )
    )
