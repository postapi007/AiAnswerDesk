from __future__ import annotations

from typing import List

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field

from config import SETTINGS
from config.settings import load_settings
from web.service import get_web_chat_settings, update_web_chat_settings

from .auth import (
    COOKIE_NAME,
    clear_auth_cookie,
    create_session,
    delete_session,
    is_authenticated,
    require_admin,
    set_auth_cookie,
)
from .html import dashboard_page_html, login_page_html
from .service import (
    DOCS_COLLECTION_NAME,
    FAQ_COLLECTION,
    PENDING_COLLECTION_NAME,
    approve_pending_knowledge_point,
    batch_create_knowledge,
    batch_delete_knowledge_points,
    create_knowledge_point,
    delete_knowledge_point,
    get_app_api_settings,
    get_fragment_read_settings,
    get_qa_prompt_template,
    import_docs_chunk_entries,
    import_batch_knowledge,
    list_knowledge_points,
    preview_docs_chunk_import,
    preview_batch_knowledge,
    save_uploaded_image_to_picture,
    test_docs_chunk_similarity,
    update_app_api_settings,
    update_fragment_read_settings,
    update_qa_prompt_template,
)


router = APIRouter(prefix=SETTINGS.admin_route_prefix)


class AdminLoginRequest(BaseModel):
    password: str = Field(..., min_length=1)


class AdminCreateKnowledgeRequest(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class AdminBatchImportRequest(BaseModel):
    content: str = Field(..., min_length=1)


class AdminBatchDeleteRequest(BaseModel):
    ids: List[str] = Field(default_factory=list)


class AdminBatchPreviewRequest(BaseModel):
    content: str = Field(default="")
    file_name: str = Field(default="")
    file_content_base64: str = Field(default="")
    max_preview: int = Field(default=20, ge=1, le=200)


class AdminBatchImportEntry(BaseModel):
    question: str = Field(..., min_length=1)
    answer: str = Field(..., min_length=1)


class AdminBatchImportConfirmRequest(BaseModel):
    entries: List[AdminBatchImportEntry] = Field(default_factory=list)
    rollback_on_error: bool = Field(default=True)


class AdminDocsChunkPreviewRequest(BaseModel):
    content: str = Field(default="")
    file_name: str = Field(default="")
    file_content_base64: str = Field(default="")
    image_path: str = Field(default="")
    chunk_size: int = Field(default=300, ge=100, le=1200)
    chunk_overlap: int = Field(default=60, ge=0, le=300)
    segment_delimiter_mode: str = Field(default="newline")
    custom_delimiter: str = Field(default="", max_length=20)
    max_preview: int = Field(default=20, ge=1, le=50)


class AdminDocsChunkImportRequest(BaseModel):
    content: str = Field(default="")
    file_name: str = Field(default="")
    file_content_base64: str = Field(default="")
    image_path: str = Field(default="")
    chunk_size: int = Field(default=300, ge=100, le=1200)
    chunk_overlap: int = Field(default=60, ge=0, le=300)
    segment_delimiter_mode: str = Field(default="newline")
    custom_delimiter: str = Field(default="", max_length=20)
    rollback_on_error: bool = Field(default=True)


class AdminUploadImageRequest(BaseModel):
    file_name: str = Field(..., min_length=1)
    file_content_base64: str = Field(..., min_length=1)


class AdminApiSettingsRequest(BaseModel):
    similarity_threshold: float = Field(..., ge=0, le=1)
    min_embedding_chars: int = Field(..., ge=1)
    not_configured_answer: str = Field(..., min_length=1)
    auto_retrieve_knowledge: bool = Field(...)
    enable_qa_model: bool = Field(...)
    auto_cache_qa_answer: bool = Field(...)


class AdminQaTemplateRequest(BaseModel):
    qa_prompt_template: str = Field(..., min_length=1)


class AdminFragmentReadSettingsRequest(BaseModel):
    similarity_threshold: float = Field(..., ge=0, le=1)
    limit: int = Field(..., ge=1, le=10)


class AdminWebChatSettingsRequest(BaseModel):
    enabled: bool = Field(...)
    chat_title: str = Field(..., min_length=1)
    welcome_template: str = Field(default="")
    quick_phrases: List[str] = Field(default_factory=list)


@router.get("", response_class=HTMLResponse)
def admin_home(request: Request):
    runtime = load_settings()
    if is_authenticated(request):
        return HTMLResponse(
            dashboard_page_html(
                min_embedding_chars=runtime.min_embedding_chars,
                similarity_threshold=runtime.similarity_threshold,
                not_configured_answer=runtime.not_configured_answer,
                faq_collection=runtime.qdrant_collection,
                pending_collection=runtime.qdrant_pending_collection,
                docs_collection=runtime.qdrant_docs_collection,
                admin_route_prefix=SETTINGS.admin_route_prefix,
            )
        )
    return HTMLResponse(login_page_html(admin_route_prefix=SETTINGS.admin_route_prefix))


@router.post("/login")
def admin_login(payload: AdminLoginRequest):
    if payload.password.strip() != SETTINGS.admin_password:
        return JSONResponse(status_code=401, content={"detail": "密码错误"})

    token, ttl = create_session()
    response = JSONResponse(content={"logged_in": True})
    set_auth_cookie(response, token, ttl)
    return response


@router.post("/logout")
def admin_logout(request: Request):
    token = request.cookies.get(COOKIE_NAME, "").strip()
    if token:
        delete_session(token)
    response = JSONResponse(content={"logged_out": True})
    clear_auth_cookie(response)
    return response


@router.get("/api/knowledge")
def admin_list_knowledge(
    request: Request,
    limit: int = Query(10, ge=1, le=10, description="每页条数"),
    page: int = Query(1, ge=1, description="页码，从1开始"),
    keyword: str = Query("", description="关键字搜索（问题/答案/id）"),
    collection: str = Query(
        FAQ_COLLECTION,
        description=f"集合名（{FAQ_COLLECTION}/{DOCS_COLLECTION_NAME}/{PENDING_COLLECTION_NAME}）",
    ),
):
    require_admin(request)
    return list_knowledge_points(
        max_items=limit,
        keyword=keyword,
        page=page,
        collection_name=collection,
    )


@router.post("/api/knowledge")
def admin_create_knowledge(request: Request, payload: AdminCreateKnowledgeRequest):
    require_admin(request)
    return create_knowledge_point(payload.question, payload.answer)


@router.delete("/api/knowledge/{point_id}")
def admin_delete_knowledge(
    request: Request,
    point_id: str,
    collection: str = Query(
        FAQ_COLLECTION,
        description=f"集合名（{FAQ_COLLECTION}/{DOCS_COLLECTION_NAME}/{PENDING_COLLECTION_NAME}）",
    ),
):
    require_admin(request)
    return delete_knowledge_point(point_id, collection_name=collection)


@router.post("/api/knowledge/batch")
def admin_batch_import(request: Request, payload: AdminBatchImportRequest):
    require_admin(request)
    return batch_create_knowledge(payload.content, collection_name=FAQ_COLLECTION)


@router.post("/api/knowledge/batch/preview")
def admin_batch_preview(request: Request, payload: AdminBatchPreviewRequest):
    require_admin(request)
    return preview_batch_knowledge(
        content=payload.content,
        file_name=payload.file_name,
        file_content_base64=payload.file_content_base64,
        max_preview=payload.max_preview,
    )


@router.post("/api/knowledge/batch/import")
def admin_batch_import_confirm(request: Request, payload: AdminBatchImportConfirmRequest):
    require_admin(request)
    return import_batch_knowledge(
        entries=[{"question": entry.question, "answer": entry.answer} for entry in payload.entries],
        rollback_on_error=payload.rollback_on_error,
        collection_name=FAQ_COLLECTION,
    )


@router.post("/api/docs-chunk/preview")
def admin_docs_chunk_preview(request: Request, payload: AdminDocsChunkPreviewRequest):
    require_admin(request)
    return preview_docs_chunk_import(
        content=payload.content,
        file_name=payload.file_name,
        file_content_base64=payload.file_content_base64,
        image_path=payload.image_path,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        segment_delimiter_mode=payload.segment_delimiter_mode,
        custom_delimiter=payload.custom_delimiter,
        max_preview=payload.max_preview,
    )


@router.post("/api/docs-chunk/import")
def admin_docs_chunk_import(request: Request, payload: AdminDocsChunkImportRequest):
    require_admin(request)
    return import_docs_chunk_entries(
        content=payload.content,
        file_name=payload.file_name,
        file_content_base64=payload.file_content_base64,
        image_path=payload.image_path,
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        segment_delimiter_mode=payload.segment_delimiter_mode,
        custom_delimiter=payload.custom_delimiter,
        rollback_on_error=payload.rollback_on_error,
    )


@router.post("/api/docs-chunk/upload-image")
def admin_docs_chunk_upload_image(request: Request, payload: AdminUploadImageRequest):
    require_admin(request)
    return save_uploaded_image_to_picture(
        file_name=payload.file_name,
        file_content_base64=payload.file_content_base64,
    )


@router.get("/api/docs-chunk/similarity")
def admin_docs_chunk_similarity(
    request: Request,
    content: str = Query(..., description="测试内容"),
):
    require_admin(request)
    return test_docs_chunk_similarity(content=content)


@router.post("/api/knowledge/batch-delete")
def admin_batch_delete(
    request: Request,
    payload: AdminBatchDeleteRequest,
    collection: str = Query(
        FAQ_COLLECTION,
        description=f"集合名（{FAQ_COLLECTION}/{DOCS_COLLECTION_NAME}/{PENDING_COLLECTION_NAME}）",
    ),
):
    require_admin(request)
    return batch_delete_knowledge_points(payload.ids, collection_name=collection)


@router.post("/api/pending/{point_id}/approve")
def admin_approve_pending(request: Request, point_id: str):
    require_admin(request)
    return approve_pending_knowledge_point(point_id)


@router.get("/api/settings/app")
def admin_get_app_settings(request: Request):
    require_admin(request)
    return get_app_api_settings()


@router.post("/api/settings/app")
def admin_update_app_settings(request: Request, payload: AdminApiSettingsRequest):
    require_admin(request)
    return update_app_api_settings(
        similarity_threshold=payload.similarity_threshold,
        min_embedding_chars=payload.min_embedding_chars,
        not_configured_answer=payload.not_configured_answer,
        auto_retrieve_knowledge=payload.auto_retrieve_knowledge,
        enable_qa_model=payload.enable_qa_model,
        auto_cache_qa_answer=payload.auto_cache_qa_answer,
    )


@router.get("/api/settings/fragment-read")
def admin_get_fragment_read_settings(request: Request):
    require_admin(request)
    return get_fragment_read_settings()


@router.post("/api/settings/fragment-read")
def admin_update_fragment_read_settings(
    request: Request,
    payload: AdminFragmentReadSettingsRequest,
):
    require_admin(request)
    return update_fragment_read_settings(
        similarity_threshold=payload.similarity_threshold,
        limit=payload.limit,
    )


@router.get("/api/settings/qa-template")
def admin_get_qa_template(request: Request):
    require_admin(request)
    return get_qa_prompt_template()


@router.post("/api/settings/qa-template")
def admin_update_qa_template(request: Request, payload: AdminQaTemplateRequest):
    require_admin(request)
    return update_qa_prompt_template(payload.qa_prompt_template)


@router.get("/api/settings/web-chat")
def admin_get_web_chat_settings(request: Request):
    require_admin(request)
    return get_web_chat_settings()


@router.post("/api/settings/web-chat")
def admin_update_web_chat_settings(request: Request, payload: AdminWebChatSettingsRequest):
    require_admin(request)
    return update_web_chat_settings(
        enabled=payload.enabled,
        chat_title=payload.chat_title,
        welcome_template=payload.welcome_template,
        quick_phrases=payload.quick_phrases,
    )
