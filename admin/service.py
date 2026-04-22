from __future__ import annotations

import base64
import binascii
import json
import math
import os
import posixpath
import re
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from xml.etree import ElementTree as ET

from fastapi import HTTPException

from api.embedding import build_query_embedding
from api.http import http_error_detail, request_json
from api.qdrant import PENDING_COLLECTION, ensure_collection_ready
from api.text_normalize import normalize_for_keyword
from config import SETTINGS
from config.settings import CONFIG_FILE_PATH, _strip_json_comments, load_settings


FAQ_COLLECTION = SETTINGS.qdrant_collection
PENDING_COLLECTION_NAME = PENDING_COLLECTION
ALLOWED_ADMIN_COLLECTIONS = {FAQ_COLLECTION, PENDING_COLLECTION_NAME}


def _normalize_admin_collection_name(
    collection_name: str | None,
    *,
    default: str = FAQ_COLLECTION,
) -> str:
    clean_name = str(collection_name or "").strip() or default
    if clean_name not in ALLOWED_ADMIN_COLLECTIONS:
        allowed = ", ".join(sorted(ALLOWED_ADMIN_COLLECTIONS))
        raise HTTPException(
            status_code=422,
            detail=f"collection 不支持: {clean_name}，仅允许: {allowed}",
        )
    return clean_name


def _extract_points(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    result = response_data.get("result")
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        points = result.get("points")
        if isinstance(points, list):
            return points
    return []


def _extract_next_page_offset(response_data: dict[str, Any]) -> Any:
    result = response_data.get("result")
    if isinstance(result, dict):
        return result.get("next_page_offset")
    return None


def _serialize_point(point: dict[str, Any]) -> dict[str, Any]:
    payload = point.get("payload") or {}
    raw_cached_from_score = payload.get("cached_from_score", 1)
    try:
        cached_from_score = float(raw_cached_from_score)
    except (TypeError, ValueError):
        cached_from_score = 1.0
    return {
        "id": point.get("id"),
        "question": str(payload.get("question", "")).strip(),
        "normalized_question": str(payload.get("normalized_question", "")).strip(),
        "answer": str(payload.get("answer", "")).strip(),
        "status": str(payload.get("status", "")).strip(),
        "cache_type": str(payload.get("cache_type", "")).strip(),
        "cached_from_score": cached_from_score,
    }


def _coerce_point_id(raw: str) -> int | str:
    value = raw.strip()
    if value.lstrip("-").isdigit():
        try:
            return int(value)
        except ValueError:
            return value
    return value


def _contains_casefold(haystack: str, needle: str) -> bool:
    return needle.casefold() in haystack.casefold()


def _match_keyword(item: dict[str, Any], keyword: str, normalized_keyword: str) -> bool:
    if not keyword and not normalized_keyword:
        return True

    question = str(item.get("question", ""))
    answer = str(item.get("answer", ""))
    normalized_question = str(item.get("normalized_question", ""))
    point_id = str(item.get("id", ""))

    if keyword:
        if (
            _contains_casefold(question, keyword)
            or _contains_casefold(answer, keyword)
            or _contains_casefold(point_id, keyword)
        ):
            return True

    if normalized_keyword:
        if (
            normalized_keyword in normalized_question
            or normalized_keyword in normalize_for_keyword(question)
            or normalized_keyword in normalize_for_keyword(answer)
        ):
            return True

    return False


def _format_float(value: float) -> str:
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return text or "0"


def _read_app_config_text(config_path: Path = CONFIG_FILE_PATH) -> str:
    try:
        return config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"读取配置文件失败: {exc}") from exc


def _read_app_config_dict(config_path: Path = CONFIG_FILE_PATH) -> dict[str, Any]:
    raw_text = _read_app_config_text(config_path)
    try:
        parsed = json.loads(_strip_json_comments(raw_text.lstrip("\ufeff")))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail=f"配置文件JSON解析失败: {exc}") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=500, detail="配置文件格式错误，根节点必须是对象")
    return parsed


def _replace_api_key_value(block_text: str, key: str, literal_value: str) -> tuple[str, bool]:
    pattern = re.compile(
        rf'(^\s*"{re.escape(key)}"\s*:\s*)(.+?)(\s*,?\s*(?://.*)?$)',
        re.MULTILINE,
    )

    def repl(match: re.Match[str]) -> str:
        return f"{match.group(1)}{literal_value}{match.group(3)}"

    replaced_text, count = pattern.subn(repl, block_text, count=1)
    return replaced_text, count > 0


def _find_named_block_bounds(raw_text: str, block_name: str) -> tuple[int, int]:
    block_match = re.search(rf'"{re.escape(block_name)}"\s*:\s*\{{', raw_text)
    if not block_match:
        raise HTTPException(status_code=500, detail=f'配置文件缺少 "{block_name}" 节点')

    start = block_match.end()
    i = start
    depth = 1
    in_string = False
    escaped = False
    while i < len(raw_text):
        ch = raw_text[i]
        if in_string:
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
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1

    if depth != 0 or i >= len(raw_text):
        raise HTTPException(status_code=500, detail=f'配置文件 "{block_name}" 节点结构错误')

    return start, i


def _replace_keys_in_block(raw_text: str, block_name: str, replacements: dict[str, str]) -> str:
    start, end = _find_named_block_bounds(raw_text, block_name)
    block = raw_text[start:end]
    missing_keys: list[str] = []
    updated_block = block
    for key, literal in replacements.items():
        updated_block, changed = _replace_api_key_value(updated_block, key, literal)
        if not changed:
            missing_keys.append(key)

    if missing_keys:
        raise HTTPException(
            status_code=500,
            detail=f'配置文件 "{block_name}" 缺少字段: {", ".join(missing_keys)}',
        )

    return f"{raw_text[:start]}{updated_block}{raw_text[end:]}"


def _replace_api_keys(raw_text: str, replacements: dict[str, str]) -> str:
    return _replace_keys_in_block(raw_text, "api", replacements)


def _replace_qa_keys(raw_text: str, replacements: dict[str, str]) -> str:
    return _replace_keys_in_block(raw_text, "qa", replacements)


def _replace_api_block_values(
    raw_text: str,
    similarity_threshold: float,
    min_embedding_chars: int,
    not_configured_answer: str,
    auto_retrieve_knowledge: bool,
    enable_qa_model: bool,
    auto_cache_qa_answer: bool,
) -> str:
    answer_literal = json.dumps(not_configured_answer, ensure_ascii=False)
    replacements = {
        "similarity_threshold": _format_float(similarity_threshold),
        "min_embedding_chars": str(min_embedding_chars),
        "not_configured_answer": answer_literal,
        "auto_retrieve_knowledge": "true" if auto_retrieve_knowledge else "false",
        "enable_qa_model": "true" if enable_qa_model else "false",
        "auto_cache_qa_answer": "true" if auto_cache_qa_answer else "false",
    }
    return _replace_api_keys(raw_text, replacements)


def get_app_api_settings() -> dict[str, Any]:
    parsed = _read_app_config_dict(CONFIG_FILE_PATH)
    api = parsed.get("api")
    if not isinstance(api, dict):
        raise HTTPException(status_code=500, detail='配置文件缺少 "api" 节点')

    runtime = load_settings(CONFIG_FILE_PATH)
    return {
        "config_path": str(CONFIG_FILE_PATH),
        "api": {
            "similarity_threshold": float(api.get("similarity_threshold", runtime.similarity_threshold)),
            "min_embedding_chars": int(api.get("min_embedding_chars", runtime.min_embedding_chars)),
            "not_configured_answer": str(
                api.get("not_configured_answer", runtime.not_configured_answer)
            ),
            "auto_retrieve_knowledge": (
                api.get("auto_retrieve_knowledge")
                if isinstance(api.get("auto_retrieve_knowledge"), bool)
                else runtime.auto_retrieve_knowledge
            ),
            "enable_qa_model": (
                api.get("enable_qa_model")
                if isinstance(api.get("enable_qa_model"), bool)
                else runtime.enable_qa_model
            ),
            "auto_cache_qa_answer": (
                api.get("auto_cache_qa_answer")
                if isinstance(api.get("auto_cache_qa_answer"), bool)
                else runtime.auto_cache_qa_answer
            ),
        },
        "effective_api": {
            "similarity_threshold": runtime.similarity_threshold,
            "min_embedding_chars": runtime.min_embedding_chars,
            "not_configured_answer": runtime.not_configured_answer,
            "auto_retrieve_knowledge": runtime.auto_retrieve_knowledge,
            "enable_qa_model": runtime.enable_qa_model,
            "auto_cache_qa_answer": runtime.auto_cache_qa_answer,
        },
        "env_overrides": {
            "similarity_threshold": bool(os.getenv("API_SIMILARITY_THRESHOLD")),
            "min_embedding_chars": bool(os.getenv("API_MIN_EMBEDDING_CHARS")),
            "not_configured_answer": bool(os.getenv("API_NOT_CONFIGURED_ANSWER")),
            "auto_retrieve_knowledge": bool(os.getenv("API_AUTO_RETRIEVE_KNOWLEDGE")),
            "enable_qa_model": bool(os.getenv("API_ENABLE_QA_MODEL")),
            "auto_cache_qa_answer": bool(os.getenv("API_AUTO_CACHE_QA_ANSWER")),
        },
    }


def update_app_api_settings(
    similarity_threshold: float,
    min_embedding_chars: int,
    not_configured_answer: str,
    auto_retrieve_knowledge: bool,
    enable_qa_model: bool,
    auto_cache_qa_answer: bool,
) -> dict[str, Any]:
    if similarity_threshold < 0 or similarity_threshold > 1:
        raise HTTPException(status_code=422, detail="similarity_threshold 必须在 0~1 之间")
    if min_embedding_chars < 1:
        raise HTTPException(status_code=422, detail="min_embedding_chars 必须 >= 1")
    clean_answer = not_configured_answer.strip()
    if not clean_answer:
        raise HTTPException(status_code=422, detail="not_configured_answer 不能为空")
    if not isinstance(auto_retrieve_knowledge, bool):
        raise HTTPException(status_code=422, detail="auto_retrieve_knowledge 必须是布尔值")
    if not isinstance(enable_qa_model, bool):
        raise HTTPException(status_code=422, detail="enable_qa_model 必须是布尔值")
    if not isinstance(auto_cache_qa_answer, bool):
        raise HTTPException(status_code=422, detail="auto_cache_qa_answer 必须是布尔值")

    raw_text = _read_app_config_text(CONFIG_FILE_PATH)
    updated_text = _replace_api_block_values(
        raw_text=raw_text,
        similarity_threshold=similarity_threshold,
        min_embedding_chars=min_embedding_chars,
        not_configured_answer=clean_answer,
        auto_retrieve_knowledge=auto_retrieve_knowledge,
        enable_qa_model=enable_qa_model,
        auto_cache_qa_answer=auto_cache_qa_answer,
    )

    try:
        CONFIG_FILE_PATH.write_text(updated_text, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"写入配置文件失败: {exc}") from exc

    return {
        "saved": True,
        "message": "已更新 config/app.json",
        **get_app_api_settings(),
    }


def get_qa_prompt_template() -> dict[str, Any]:
    parsed = _read_app_config_dict(CONFIG_FILE_PATH)
    qa = parsed.get("qa")
    if not isinstance(qa, dict):
        raise HTTPException(status_code=500, detail='配置文件缺少 "qa" 节点')

    runtime = load_settings(CONFIG_FILE_PATH)
    raw_template = qa.get("qa_prompt_template")
    template = str(raw_template).strip() if isinstance(raw_template, str) else runtime.qa_prompt_template
    return {
        "config_path": str(CONFIG_FILE_PATH),
        "qa_prompt_template": template,
        "effective_qa_prompt_template": runtime.qa_prompt_template,
    }


def update_qa_prompt_template(qa_prompt_template: str) -> dict[str, Any]:
    clean_template = qa_prompt_template.strip()
    if not clean_template:
        raise HTTPException(status_code=422, detail="qa_prompt_template 不能为空")
    if "{content}" not in clean_template:
        raise HTTPException(status_code=422, detail='qa_prompt_template 必须包含占位符 "{content}"')

    raw_text = _read_app_config_text(CONFIG_FILE_PATH)
    updated_text = _replace_qa_keys(
        raw_text,
        {"qa_prompt_template": json.dumps(clean_template, ensure_ascii=False)},
    )
    try:
        CONFIG_FILE_PATH.write_text(updated_text, encoding="utf-8")
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"写入配置文件失败: {exc}") from exc

    result = get_qa_prompt_template()
    return {
        "saved": True,
        "message": "已更新 LLM 自定义模版",
        **result,
    }


def list_knowledge_points(
    max_items: int = 10,
    keyword: str = "",
    page: int = 1,
    collection_name: str = FAQ_COLLECTION,
) -> dict[str, Any]:
    resolved_collection = _normalize_admin_collection_name(collection_name)
    scroll_url = f"{SETTINGS.qdrant_url}/collections/{resolved_collection}/points/scroll"
    items: list[dict[str, Any]] = []
    offset = None
    clean_keyword = keyword.strip()
    normalized_keyword = normalize_for_keyword(clean_keyword)
    page = max(int(page), 1)
    start_index = (page - 1) * max_items
    end_index = start_index + max_items
    total = 0

    for _ in range(1000):

        body: dict[str, Any] = {
            "limit": 100,
            "with_payload": True,
            "with_vector": False,
        }
        if offset is not None:
            body["offset"] = offset

        try:
            response_data = request_json(
                url=scroll_url,
                body=body,
                timeout=SETTINGS.qdrant_timeout_seconds,
            )
        except HTTPError as exc:
            if exc.code == 404:
                return {
                    "collection": resolved_collection,
                    "keyword": clean_keyword,
                    "page": page,
                    "limit": max_items,
                    "items": [],
                    "count": 0,
                    "total": 0,
                    "total_pages": 0,
                    "has_prev": page > 1,
                    "has_next": False,
                }
            raise HTTPException(status_code=503, detail=http_error_detail("读取Qdrant数据失败", exc)) from exc
        except (URLError, TimeoutError) as exc:
            raise HTTPException(status_code=503, detail=f"读取Qdrant数据失败: {exc}") from exc

        points = _extract_points(response_data)
        if not points:
            break

        for point in points:
            item = _serialize_point(point)
            if _match_keyword(item, clean_keyword, normalized_keyword):
                if start_index <= total < end_index:
                    items.append(item)
                total += 1

        offset = _extract_next_page_offset(response_data)
        if offset is None:
            break

    total_pages = math.ceil(total / max_items) if total else 0

    return {
        "collection": resolved_collection,
        "keyword": clean_keyword,
        "page": page,
        "limit": max_items,
        "items": items,
        "count": len(items),
        "total": total,
        "total_pages": total_pages,
        "has_prev": page > 1 and total_pages > 0,
        "has_next": page < total_pages,
    }


def create_knowledge_point(
    question: str,
    answer: str,
    collection_name: str = FAQ_COLLECTION,
    *,
    point_id: str | int | None = None,
    vector_override: list[float] | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_collection = _normalize_admin_collection_name(collection_name)
    clean_question = question.strip()
    normalized_question = normalize_for_keyword(clean_question)
    clean_answer = answer.strip()

    if not normalized_question:
        raise HTTPException(status_code=422, detail="question不能为空")
    if not clean_answer:
        raise HTTPException(status_code=422, detail="answer不能为空")

    vector = vector_override if vector_override is not None else build_query_embedding(clean_question)
    if not isinstance(vector, list) or not vector:
        raise HTTPException(status_code=422, detail="向量不能为空")

    collection_action = ensure_collection_ready(
        len(vector),
        collection_name=resolved_collection,
    )
    final_point_id = point_id if point_id is not None else str(uuid.uuid4())
    upsert_url = f"{SETTINGS.qdrant_url}/collections/{resolved_collection}/points?wait=true"
    payload: dict[str, Any] = {
        "question": clean_question,
        "normalized_question": normalized_question,
        "answer": clean_answer,
    }
    if extra_payload:
        for key, value in extra_payload.items():
            if key in {"question", "normalized_question", "answer"}:
                continue
            payload[str(key)] = value
    body = {
        "points": [
            {
                "id": final_point_id,
                "vector": vector,
                "payload": payload,
            }
        ]
    }

    try:
        qdrant_result = request_json(
            url=upsert_url,
            body=body,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="PUT",
        )
    except HTTPError as exc:
        raise HTTPException(status_code=503, detail=http_error_detail("写入Qdrant失败", exc)) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=f"写入Qdrant失败: {exc}") from exc

    return {
        "saved": True,
        "collection": resolved_collection,
        "collection_action": collection_action,
        "id": final_point_id,
        "question": clean_question,
        "answer": clean_answer,
        "vector_size": len(vector),
        "qdrant_result": qdrant_result.get("result"),
    }


def delete_knowledge_point(
    point_id: str,
    collection_name: str = FAQ_COLLECTION,
) -> dict[str, Any]:
    resolved_collection = _normalize_admin_collection_name(collection_name)
    point_id_value = _coerce_point_id(point_id)
    delete_url = f"{SETTINGS.qdrant_url}/collections/{resolved_collection}/points/delete?wait=true"
    body = {"points": [point_id_value]}

    try:
        qdrant_result = request_json(
            url=delete_url,
            body=body,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="POST",
        )
    except HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=404, detail="集合不存在或点位不存在") from exc
        raise HTTPException(status_code=503, detail=http_error_detail("删除Qdrant数据失败", exc)) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=f"删除Qdrant数据失败: {exc}") from exc

    return {
        "deleted": True,
        "id": point_id_value,
        "collection": resolved_collection,
        "qdrant_result": qdrant_result.get("result"),
    }


def batch_delete_knowledge_points(
    point_ids: list[str],
    collection_name: str = FAQ_COLLECTION,
) -> dict[str, Any]:
    resolved_collection = _normalize_admin_collection_name(collection_name)
    unique_ids: list[int | str] = []
    seen: set[str] = set()
    for raw_id in point_ids:
        text = str(raw_id).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        unique_ids.append(_coerce_point_id(text))

    if not unique_ids:
        raise HTTPException(status_code=422, detail="ids不能为空")

    delete_url = f"{SETTINGS.qdrant_url}/collections/{resolved_collection}/points/delete?wait=true"
    body = {"points": unique_ids}

    try:
        qdrant_result = request_json(
            url=delete_url,
            body=body,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="POST",
        )
    except HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=404, detail="集合不存在或点位不存在") from exc
        raise HTTPException(status_code=503, detail=http_error_detail("批量删除Qdrant数据失败", exc)) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=f"批量删除Qdrant数据失败: {exc}") from exc

    return {
        "deleted": True,
        "deleted_count": len(unique_ids),
        "ids": unique_ids,
        "collection": resolved_collection,
        "qdrant_result": qdrant_result.get("result"),
    }


def _column_index_from_ref(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha()).upper()
    if not letters:
        return 0
    index = 0
    for ch in letters:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return max(index - 1, 0)


def _decode_base64_file(file_content_base64: str) -> bytes:
    text = (file_content_base64 or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="文件内容不能为空")
    try:
        return base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(status_code=422, detail="文件内容不是合法base64") from exc


def _decode_text_file_bytes(file_bytes: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return file_bytes.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise HTTPException(status_code=422, detail="txt文件编码无法识别，请使用UTF-8")


def _extract_xlsx_shared_strings(zip_file: zipfile.ZipFile) -> list[str]:
    try:
        raw = zip_file.read("xl/sharedStrings.xml")
    except KeyError:
        return []

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    root = ET.fromstring(raw)
    values: list[str] = []
    for si in root.findall(".//m:si", ns):
        parts: list[str] = []
        for text_node in si.findall(".//m:t", ns):
            parts.append(text_node.text or "")
        values.append("".join(parts))
    return values


def _resolve_first_sheet_path(zip_file: zipfile.ZipFile) -> str:
    workbook_xml = zip_file.read("xl/workbook.xml")
    wb_ns = {
        "m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
        "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    }
    workbook_root = ET.fromstring(workbook_xml)
    first_sheet = workbook_root.find(".//m:sheets/m:sheet", wb_ns)
    relation_id = first_sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id") if first_sheet is not None else None

    rel_xml = zip_file.read("xl/_rels/workbook.xml.rels")
    rel_ns = {"r": "http://schemas.openxmlformats.org/package/2006/relationships"}
    rel_root = ET.fromstring(rel_xml)
    if relation_id:
        for rel in rel_root.findall(".//r:Relationship", rel_ns):
            if rel.attrib.get("Id") != relation_id:
                continue
            target = rel.attrib.get("Target", "").strip()
            if not target:
                break
            if target.startswith("/"):
                return target.lstrip("/")
            return posixpath.normpath(posixpath.join("xl", target))

    worksheet_paths = sorted(
        name for name in zip_file.namelist() if name.startswith("xl/worksheets/") and name.endswith(".xml")
    )
    if worksheet_paths:
        return worksheet_paths[0]
    raise HTTPException(status_code=422, detail="xlsx文件缺少工作表")


def _parse_xlsx_rows(file_bytes: bytes) -> list[tuple[int, list[str]]]:
    try:
        with zipfile.ZipFile(BytesIO(file_bytes)) as zip_file:
            shared_strings = _extract_xlsx_shared_strings(zip_file)
            sheet_path = _resolve_first_sheet_path(zip_file)
            sheet_xml = zip_file.read(sheet_path)
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=422, detail="xlsx文件损坏或格式错误") from exc
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=f"xlsx文件结构错误: {exc}") from exc
    except ET.ParseError as exc:
        raise HTTPException(status_code=422, detail=f"xlsx文件XML解析失败: {exc}") from exc

    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    try:
        root = ET.fromstring(sheet_xml)
    except ET.ParseError as exc:
        raise HTTPException(status_code=422, detail=f"xlsx工作表解析失败: {exc}") from exc
    rows: list[tuple[int, list[str]]] = []
    auto_row_number = 0
    for row_node in root.findall(".//m:sheetData/m:row", ns):
        auto_row_number += 1
        row_number = auto_row_number
        raw_row_no = row_node.attrib.get("r", "").strip()
        if raw_row_no.isdigit():
            row_number = int(raw_row_no)

        col_values: dict[int, str] = {}
        for cell in row_node.findall("m:c", ns):
            ref = cell.attrib.get("r", "")
            col_idx = _column_index_from_ref(ref)
            cell_type = cell.attrib.get("t", "")
            value = ""

            if cell_type == "inlineStr":
                text_node = cell.find("m:is/m:t", ns)
                if text_node is not None and text_node.text is not None:
                    value = text_node.text
            else:
                value_node = cell.find("m:v", ns)
                if value_node is not None and value_node.text is not None:
                    raw_text = value_node.text
                    if cell_type == "s":
                        try:
                            shared_index = int(raw_text)
                        except ValueError:
                            shared_index = -1
                        if 0 <= shared_index < len(shared_strings):
                            value = shared_strings[shared_index]
                    else:
                        value = raw_text

            col_values[col_idx] = str(value).strip()

        if not col_values:
            rows.append((row_number, []))
            continue

        max_col = max(col_values.keys())
        row_values = [col_values.get(i, "").strip() for i in range(max_col + 1)]
        rows.append((row_number, row_values))
    return rows


def _is_header_row(first: str, second: str) -> bool:
    first_key = first.strip().lower().replace(" ", "")
    second_key = second.strip().lower().replace(" ", "")
    return first_key in {"question", "问题", "问法"} and second_key in {"answer", "答案", "回复"}


def parse_batch_entries_with_errors(raw_content: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    text = (raw_content or "").strip()
    if not text:
        return [], [{"index": 1, "error": "批量内容不能为空"}]

    entries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []

    if text.startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return [], [{"index": 1, "error": f"JSON解析失败: {exc}"}]
        if not isinstance(parsed, list):
            return [], [{"index": 1, "error": "JSON格式必须是数组"}]

        for idx, item in enumerate(parsed, start=1):
            if not isinstance(item, dict):
                errors.append({"index": idx, "error": "当前项不是对象"})
                continue
            question = str(item.get("question", "")).strip()
            answer = str(item.get("answer", "")).strip()
            if not question or not answer:
                errors.append({"index": idx, "error": "question或answer为空"})
                continue
            entries.append({"index": idx, "question": question, "answer": answer})
        return entries, errors

    lines = raw_content.splitlines()
    for idx, line in enumerate(lines, start=1):
        content = line.strip()
        if not content or content.startswith("#"):
            continue

        question = ""
        answer = ""
        if "|" in content:
            question, answer = content.split("|", 1)
        elif "\t" in content:
            question, answer = content.split("\t", 1)
        else:
            errors.append(
                {
                    "index": idx,
                    "error": "格式错误，请使用 `问题|答案` 或 `问题<TAB>答案`",
                    "raw": content,
                }
            )
            continue

        question = question.strip()
        answer = answer.strip()
        if not question or not answer:
            errors.append({"index": idx, "error": "question或answer为空", "raw": content})
            continue
        entries.append({"index": idx, "question": question, "answer": answer})

    if not entries and not errors:
        errors.append({"index": 1, "error": "未解析到有效数据"})
    return entries, errors


def parse_batch_entries_from_xlsx(file_bytes: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    rows = _parse_xlsx_rows(file_bytes)
    entries: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    start_idx = 0
    if rows:
        first_row_values = rows[0][1]
        first_cell = first_row_values[0] if len(first_row_values) > 0 else ""
        second_cell = first_row_values[1] if len(first_row_values) > 1 else ""
        if _is_header_row(first_cell, second_cell):
            start_idx = 1

    for row_number, row_values in rows[start_idx:]:
        question = row_values[0].strip() if len(row_values) > 0 else ""
        answer = row_values[1].strip() if len(row_values) > 1 else ""
        if not question and not answer:
            continue
        if not question or not answer:
            errors.append({"index": row_number, "error": "question或answer为空"})
            continue
        entries.append({"index": row_number, "question": question, "answer": answer})

    if not entries and not errors:
        errors.append({"index": 1, "error": "xlsx中未解析到有效数据"})
    return entries, errors


def parse_batch_entries(raw_content: str) -> list[dict[str, str]]:
    entries, errors = parse_batch_entries_with_errors(raw_content)
    if errors:
        first = errors[0]
        raise HTTPException(status_code=422, detail=f"第{first.get('index', '?')}行: {first.get('error', '解析失败')}")
    if not entries:
        raise HTTPException(status_code=422, detail="未解析到有效数据")
    return [{"question": item["question"], "answer": item["answer"]} for item in entries]


def preview_batch_knowledge(
    content: str = "",
    file_name: str = "",
    file_content_base64: str = "",
    max_preview: int = 20,
) -> dict[str, Any]:
    has_file = bool((file_content_base64 or "").strip())
    has_content = bool((content or "").strip())
    if not has_file and not has_content:
        raise HTTPException(status_code=422, detail="请上传xlsx/txt文件或粘贴批量内容")

    source_type = "text"
    source_name = ""
    entries: list[dict[str, Any]]
    errors: list[dict[str, Any]]

    if has_file:
        source_name = (file_name or "").strip() or "upload"
        lower_name = source_name.lower()
        file_bytes = _decode_base64_file(file_content_base64)
        if lower_name.endswith(".xlsx"):
            source_type = "xlsx"
            entries, errors = parse_batch_entries_from_xlsx(file_bytes)
        elif lower_name.endswith(".txt"):
            source_type = "txt"
            text = _decode_text_file_bytes(file_bytes)
            entries, errors = parse_batch_entries_with_errors(text)
        else:
            raise HTTPException(status_code=422, detail="仅支持 .xlsx 和 .txt 文件")
    else:
        source_type = "text"
        entries, errors = parse_batch_entries_with_errors(content)

    preview_limit = max(1, min(int(max_preview), 200))
    preview_entries = entries[:preview_limit]
    preview_errors = errors[:preview_limit]
    return {
        "collection": FAQ_COLLECTION,
        "source_type": source_type,
        "file_name": source_name,
        "total_valid": len(entries),
        "total_errors": len(errors),
        "entries": [{"question": item["question"], "answer": item["answer"]} for item in entries],
        "preview_entries": preview_entries,
        "errors": preview_errors,
        "preview_limit": preview_limit,
        "preview_truncated": len(entries) > preview_limit,
        "errors_truncated": len(errors) > preview_limit,
    }


def import_batch_knowledge(
    entries: list[dict[str, Any]],
    rollback_on_error: bool = True,
    collection_name: str = FAQ_COLLECTION,
) -> dict[str, Any]:
    resolved_collection = _normalize_admin_collection_name(collection_name)
    if not entries:
        raise HTTPException(status_code=422, detail="entries不能为空")

    clean_entries: list[dict[str, str]] = []
    for idx, item in enumerate(entries, start=1):
        question = str(item.get("question", "")).strip()
        answer = str(item.get("answer", "")).strip()
        if not question or not answer:
            raise HTTPException(status_code=422, detail=f"第{idx}条question或answer为空")
        clean_entries.append({"question": question, "answer": answer})

    success_items: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    inserted_ids: list[str] = []
    rollback_error = ""
    rolled_back = False
    attempted = 0

    for idx, entry in enumerate(clean_entries, start=1):
        attempted = idx
        try:
            result = create_knowledge_point(
                entry["question"],
                entry["answer"],
                collection_name=resolved_collection,
            )
            point_id = str(result.get("id", "")).strip()
            if point_id:
                inserted_ids.append(point_id)
            success_items.append(
                {
                    "index": idx,
                    "id": result.get("id"),
                    "question": entry["question"],
                }
            )
        except HTTPException as exc:
            errors.append(
                {
                    "index": idx,
                    "question": entry["question"],
                    "error": str(exc.detail),
                }
            )
            if rollback_on_error:
                if inserted_ids:
                    try:
                        batch_delete_knowledge_points(
                            inserted_ids,
                            collection_name=resolved_collection,
                        )
                        rolled_back = True
                        success_items = []
                        inserted_ids = []
                    except HTTPException as rollback_exc:
                        rollback_error = str(rollback_exc.detail)
                break

    total = len(clean_entries)
    skipped = max(total - attempted, 0)
    if rolled_back:
        success_count = 0
        failed_count = total
    else:
        success_count = len(success_items)
        failed_count = len(errors)

    return {
        "collection": resolved_collection,
        "total": total,
        "attempted": attempted,
        "skipped": skipped,
        "success": success_count,
        "failed": failed_count,
        "items": success_items,
        "errors": errors,
        "rollback_on_error": rollback_on_error,
        "rolled_back": rolled_back,
        "rollback_error": rollback_error,
    }


def approve_pending_knowledge_point(point_id: str) -> dict[str, Any]:
    pending_collection = PENDING_COLLECTION_NAME
    pending_point_id = _coerce_point_id(point_id)
    fetch_url = f"{SETTINGS.qdrant_url}/collections/{pending_collection}/points"
    fetch_body = {
        "ids": [pending_point_id],
        "with_payload": True,
        "with_vector": False,
    }

    try:
        response_data = request_json(
            url=fetch_url,
            body=fetch_body,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="POST",
        )
    except HTTPError as exc:
        if exc.code == 404:
            raise HTTPException(status_code=404, detail="待审核集合不存在或记录不存在") from exc
        raise HTTPException(status_code=503, detail=http_error_detail("读取待审核记录失败", exc)) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=f"读取待审核记录失败: {exc}") from exc

    points = _extract_points(response_data)
    if not points:
        raise HTTPException(status_code=404, detail="待审核记录不存在")

    point = points[0]
    payload = point.get("payload") or {}
    question = str(payload.get("question", "")).strip()
    answer = str(payload.get("answer", "")).strip()
    if not question or not answer:
        raise HTTPException(status_code=422, detail="待审核记录缺少 question 或 answer")

    approved_result = create_knowledge_point(
        question=question,
        answer=answer,
        collection_name=FAQ_COLLECTION,
        extra_payload={
            "review_status": "approved",
            "approved_from_collection": pending_collection,
            "approved_from_id": point.get("id"),
        },
    )

    delete_warning = ""
    try:
        delete_knowledge_point(str(point.get("id")), collection_name=pending_collection)
    except HTTPException as exc:
        delete_warning = str(exc.detail)

    return {
        "approved": True,
        "from_collection": pending_collection,
        "to_collection": FAQ_COLLECTION,
        "pending_id": point.get("id"),
        "faq_id": approved_result.get("id"),
        "question": question,
        "answer": answer,
        "delete_warning": delete_warning,
    }


def batch_create_knowledge(
    raw_content: str,
    collection_name: str = FAQ_COLLECTION,
) -> dict[str, Any]:
    entries = parse_batch_entries(raw_content)
    return import_batch_knowledge(
        entries,
        rollback_on_error=False,
        collection_name=collection_name,
    )
