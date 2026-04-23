from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CONFIG_FILE_PATH = Path(__file__).resolve().parent / "app.json"


@dataclass(frozen=True)
class AppSettings:
    qdrant_url: str
    qdrant_collection: str
    qdrant_pending_collection: str
    qdrant_docs_collection: str
    qdrant_timeout_seconds: int
    embedding_base_url: str
    embedding_model: str
    embedding_api_key_env: str
    embedding_timeout_seconds: int
    qa_base_url: str
    qa_model: str
    qa_api_key_env: str
    qa_timeout_seconds: int
    qa_prompt_template: str
    fragment_read_similarity_threshold: float
    fragment_read_limit: int
    web_enabled: bool
    web_chat_title: str
    web_welcome_template: str
    web_quick_phrases: list[str]
    default_limit: int
    max_limit: int
    similarity_threshold: float
    min_embedding_chars: int
    not_configured_answer: str
    auto_retrieve_knowledge: bool
    enable_qa_model: bool
    auto_cache_qa_answer: bool
    admin_route_prefix: str
    admin_password: str
    admin_session_ttl_seconds: int


def _to_int(value: Any, fallback: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _to_float(value: Any, fallback: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _to_bool(value: Any, fallback: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"1", "true", "yes", "on", "y"}:
            return True
        if text in {"0", "false", "no", "off", "n"}:
            return False
        return fallback
    if isinstance(value, (int, float)):
        return bool(value)
    return fallback


def _strip_json_comments(content: str) -> str:
    chars = []
    i = 0
    in_string = False
    in_line_comment = False
    in_block_comment = False
    escaped = False

    while i < len(content):
        ch = content[i]
        nxt = content[i + 1] if i + 1 < len(content) else ""

        if in_line_comment:
            if ch == "\n":
                in_line_comment = False
                chars.append(ch)
            i += 1
            continue

        if in_block_comment:
            if ch == "*" and nxt == "/":
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue

        if in_string:
            chars.append(ch)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == '"':
            in_string = True
            chars.append(ch)
            i += 1
            continue

        if ch == "/" and nxt == "/":
            in_line_comment = True
            i += 2
            continue

        if ch == "/" and nxt == "*":
            in_block_comment = True
            i += 2
            continue

        if ch == "#":
            in_line_comment = True
            i += 1
            continue

        chars.append(ch)
        i += 1

    return "".join(chars)


def _normalize_route_prefix(value: Any, fallback: str = "/admin") -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    if not text.startswith("/"):
        text = f"/{text}"
    normalized = "/" + text.strip("/")
    if normalized == "/":
        return fallback
    return normalized


def _read_json_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            content = f.read().lstrip("\ufeff")
            raw = json.loads(_strip_json_comments(content))
    except (OSError, json.JSONDecodeError):
        return {}

    return raw if isinstance(raw, dict) else {}


def load_settings(config_path: Path = CONFIG_FILE_PATH) -> AppSettings:
    data = _read_json_config(config_path)
    qdrant = data.get("qdrant", {})
    embedding = data.get("embedding", {})
    api = data.get("api", {})
    qa = data.get("qa", {})
    fragment_read = data.get("fragment_read", {})
    web = data.get("web", {})

    qdrant_url = str(qdrant.get("url", "http://127.0.0.1:3333")).strip().rstrip("/")
    qdrant_url = os.getenv("QDRANT_URL", qdrant_url).strip().rstrip("/")
    if not qdrant_url:
        qdrant_url = "http://127.0.0.1:3333"

    qdrant_collection = str(qdrant.get("collection", "faq")).strip() or "faq"
    qdrant_collection = os.getenv("QDRANT_COLLECTION", qdrant_collection).strip() or "faq"

    qdrant_pending_collection = str(qdrant.get("pending_collection", "pending_kb")).strip() or "pending_kb"
    qdrant_pending_collection = (
        os.getenv("QDRANT_PENDING_COLLECTION", qdrant_pending_collection).strip() or "pending_kb"
    )

    qdrant_docs_collection = str(qdrant.get("docs_collection", "kb_docs_v1")).strip() or "kb_docs_v1"
    qdrant_docs_collection = (
        os.getenv("QDRANT_DOCS_COLLECTION", qdrant_docs_collection).strip() or "kb_docs_v1"
    )

    qdrant_timeout_seconds = max(_to_int(qdrant.get("timeout_seconds", 5), 5), 1)
    qdrant_timeout_seconds = max(
        _to_int(os.getenv("QDRANT_TIMEOUT_SECONDS", qdrant_timeout_seconds), qdrant_timeout_seconds),
        1,
    )

    embedding_base_url = str(embedding.get("base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")).strip().rstrip("/")
    embedding_base_url = os.getenv("EMBEDDING_BASE_URL", embedding_base_url).strip().rstrip("/")
    if not embedding_base_url:
        embedding_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    embedding_model = str(embedding.get("model", "text-embedding-v4")).strip() or "text-embedding-v4"
    embedding_model = os.getenv("EMBEDDING_MODEL", embedding_model).strip() or "text-embedding-v4"

    embedding_api_key_env = str(embedding.get("api_key_env", "DASHSCOPE_API_KEY")).strip() or "DASHSCOPE_API_KEY"
    embedding_api_key_env = os.getenv("EMBEDDING_API_KEY_ENV", embedding_api_key_env).strip() or "DASHSCOPE_API_KEY"

    embedding_timeout_seconds = max(_to_int(embedding.get("timeout_seconds", 15), 15), 1)
    embedding_timeout_seconds = max(
        _to_int(
            os.getenv("EMBEDDING_TIMEOUT_SECONDS", embedding_timeout_seconds),
            embedding_timeout_seconds,
        ),
        1,
    )

    max_limit = max(_to_int(api.get("max_limit", 10), 10), 1)
    max_limit = max(_to_int(os.getenv("API_MAX_LIMIT", max_limit), max_limit), 1)

    default_limit = _to_int(api.get("default_limit", 3), 3)
    default_limit = _to_int(os.getenv("API_DEFAULT_LIMIT", default_limit), default_limit)
    if default_limit < 1:
        default_limit = 1
    if default_limit > max_limit:
        default_limit = max_limit

    similarity_threshold = _to_float(api.get("similarity_threshold", 0.75), 0.75)
    similarity_threshold = _to_float(
        os.getenv("API_SIMILARITY_THRESHOLD", similarity_threshold),
        similarity_threshold,
    )
    if similarity_threshold < 0:
        similarity_threshold = 0.0
    if similarity_threshold > 1:
        similarity_threshold = 1.0

    min_embedding_chars = max(_to_int(api.get("min_embedding_chars", 2), 2), 1)
    min_embedding_chars = max(
        _to_int(os.getenv("API_MIN_EMBEDDING_CHARS", min_embedding_chars), min_embedding_chars),
        1,
    )

    not_configured_answer = str(api.get("not_configured_answer", "未配置")).strip() or "未配置"
    not_configured_answer = os.getenv("API_NOT_CONFIGURED_ANSWER", not_configured_answer).strip() or "未配置"

    qa_base_url = str(qa.get("qa_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")).strip().rstrip("/")
    qa_base_url = os.getenv("QA_BASE_URL", os.getenv("API_QA_BASE_URL", qa_base_url)).strip().rstrip("/")
    if not qa_base_url:
        qa_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

    qa_model = str(qa.get("qa_model", "qwen3.6-plus")).strip() or "qwen3.6-plus"
    qa_model = os.getenv("QA_MODEL", os.getenv("API_QA_MODEL", qa_model)).strip() or "qwen3.6-plus"

    qa_api_key_env = str(qa.get("qa_api_key_env", "DASHSCOPE_API_KEY")).strip() or "DASHSCOPE_API_KEY"
    qa_api_key_env = os.getenv("QA_API_KEY_ENV", os.getenv("API_QA_API_KEY_ENV", qa_api_key_env)).strip() or "DASHSCOPE_API_KEY"

    qa_timeout_seconds = max(_to_int(qa.get("qa_timeout_seconds", 30), 30), 1)
    qa_timeout_seconds = max(
        _to_int(
            os.getenv("QA_TIMEOUT_SECONDS", os.getenv("API_QA_TIMEOUT_SECONDS", qa_timeout_seconds)),
            qa_timeout_seconds,
        ),
        1,
    )

    qa_prompt_template = str(qa.get("qa_prompt_template", "{content}")).strip() or "{content}"
    qa_prompt_template = os.getenv("QA_PROMPT_TEMPLATE", os.getenv("API_QA_PROMPT_TEMPLATE", qa_prompt_template)).strip() or "{content}"

    fragment_read_similarity_threshold = _to_float(
        fragment_read.get("similarity_threshold", 0.75),
        0.75,
    )
    fragment_read_similarity_threshold = _to_float(
        os.getenv(
            "FRAGMENT_READ_SIMILARITY_THRESHOLD",
            fragment_read_similarity_threshold,
        ),
        fragment_read_similarity_threshold,
    )
    if fragment_read_similarity_threshold < 0:
        fragment_read_similarity_threshold = 0.0
    if fragment_read_similarity_threshold > 1:
        fragment_read_similarity_threshold = 1.0

    fragment_read_limit = _to_int(fragment_read.get("limit", 3), 3)
    fragment_read_limit = _to_int(
        os.getenv("FRAGMENT_READ_LIMIT", fragment_read_limit),
        fragment_read_limit,
    )
    if fragment_read_limit < 1:
        fragment_read_limit = 1
    if fragment_read_limit > 10:
        fragment_read_limit = 10

    web_enabled = _to_bool(web.get("enabled", True), True)
    web_enabled = _to_bool(os.getenv("WEB_ENABLED", web_enabled), web_enabled)

    web_chat_title = str(web.get("chat_title", "智能客服")).strip() or "智能客服"
    web_chat_title = os.getenv("WEB_CHAT_TITLE", web_chat_title).strip() or "智能客服"

    web_welcome_template = str(web.get("welcome_template", "")).strip()
    web_welcome_template = os.getenv("WEB_WELCOME_TEMPLATE", web_welcome_template).strip()

    web_quick_phrases: list[str] = []
    raw_quick_phrases = web.get("quick_phrases")
    if isinstance(raw_quick_phrases, list):
        for item in raw_quick_phrases:
            phrase = str(item or "").strip()
            if phrase:
                web_quick_phrases.append(phrase)
    elif isinstance(raw_quick_phrases, str):
        for item in raw_quick_phrases.splitlines():
            phrase = item.strip()
            if phrase:
                web_quick_phrases.append(phrase)

    env_quick_phrases = os.getenv("WEB_QUICK_PHRASES", "").strip()
    if env_quick_phrases:
        web_quick_phrases = [
            item.strip()
            for item in env_quick_phrases.split("||")
            if item.strip()
        ]

    auto_retrieve_knowledge = _to_bool(api.get("auto_retrieve_knowledge", True), True)
    auto_retrieve_knowledge = _to_bool(
        os.getenv("API_AUTO_RETRIEVE_KNOWLEDGE", auto_retrieve_knowledge),
        auto_retrieve_knowledge,
    )

    enable_qa_model = _to_bool(api.get("enable_qa_model", False), False)
    enable_qa_model = _to_bool(
        os.getenv("API_ENABLE_QA_MODEL", enable_qa_model),
        enable_qa_model,
    )

    auto_cache_qa_answer = _to_bool(api.get("auto_cache_qa_answer", True), True)
    auto_cache_qa_answer = _to_bool(
        os.getenv("API_AUTO_CACHE_QA_ANSWER", auto_cache_qa_answer),
        auto_cache_qa_answer,
    )

    admin = data.get("admin", {})
    admin_route_prefix = _normalize_route_prefix(admin.get("route_prefix", "/admin"), "/admin")
    admin_route_prefix = _normalize_route_prefix(
        os.getenv("ADMIN_ROUTE_PREFIX", admin_route_prefix),
        admin_route_prefix,
    )

    admin_password = str(admin.get("password", "admin123456")).strip() or "admin123456"
    admin_password = os.getenv("ADMIN_PASSWORD", admin_password).strip() or "admin123456"

    admin_session_ttl_seconds = max(_to_int(admin.get("session_ttl_seconds", 28800), 28800), 60)
    admin_session_ttl_seconds = max(
        _to_int(
            os.getenv("ADMIN_SESSION_TTL_SECONDS", admin_session_ttl_seconds),
            admin_session_ttl_seconds,
        ),
        60,
    )

    return AppSettings(
        qdrant_url=qdrant_url,
        qdrant_collection=qdrant_collection,
        qdrant_pending_collection=qdrant_pending_collection,
        qdrant_docs_collection=qdrant_docs_collection,
        qdrant_timeout_seconds=qdrant_timeout_seconds,
        embedding_base_url=embedding_base_url,
        embedding_model=embedding_model,
        embedding_api_key_env=embedding_api_key_env,
        embedding_timeout_seconds=embedding_timeout_seconds,
        qa_base_url=qa_base_url,
        qa_model=qa_model,
        qa_api_key_env=qa_api_key_env,
        qa_timeout_seconds=qa_timeout_seconds,
        qa_prompt_template=qa_prompt_template,
        fragment_read_similarity_threshold=fragment_read_similarity_threshold,
        fragment_read_limit=fragment_read_limit,
        web_enabled=web_enabled,
        web_chat_title=web_chat_title,
        web_welcome_template=web_welcome_template,
        web_quick_phrases=web_quick_phrases,
        default_limit=default_limit,
        max_limit=max_limit,
        similarity_threshold=similarity_threshold,
        min_embedding_chars=min_embedding_chars,
        not_configured_answer=not_configured_answer,
        auto_retrieve_knowledge=auto_retrieve_knowledge,
        enable_qa_model=enable_qa_model,
        auto_cache_qa_answer=auto_cache_qa_answer,
        admin_route_prefix=admin_route_prefix,
        admin_password=admin_password,
        admin_session_ttl_seconds=admin_session_ttl_seconds,
    )


SETTINGS = load_settings()
