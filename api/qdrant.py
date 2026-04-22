from __future__ import annotations

import uuid
from typing import Any
from urllib.error import HTTPError, URLError

from fastapi import HTTPException

from config import SETTINGS

from .embedding import build_query_embedding
from .http import http_error_detail, request_json
from .text_normalize import normalize_for_keyword


PENDING_COLLECTION = SETTINGS.qdrant_pending_collection


# 从Qdrant返回体中提取点位列表（兼容不同result结构）。
def _extract_points(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    result = response_data.get("result")
    if isinstance(result, list):
        return result
    if isinstance(result, dict):
        points = result.get("points")
        if isinstance(points, list):
            return points
    return []


# 从Qdrant滚动查询返回体中提取下一页offset。
def _extract_next_page_offset(response_data: dict[str, Any]) -> Any:
    result = response_data.get("result")
    if isinstance(result, dict):
        return result.get("next_page_offset")
    return None


# 把Qdrant点位结构转换为统一命中结构。
def _point_to_hit(point: dict[str, Any], score: float = 1.0) -> dict[str, Any]:
    payload = point.get("payload") or {}
    return {
        "id": point.get("id"),
        "question": str(payload.get("question", "")).strip(),
        "answer": str(payload.get("answer", "")).strip(),
        "score": score,
    }


# 读取集合配置中的向量维度。
def _extract_vector_size(collection_info: dict[str, Any]) -> int | None:
    vectors = (
        collection_info.get("result", {})
        .get("config", {})
        .get("params", {})
        .get("vectors")
    )
    if isinstance(vectors, dict):
        size = vectors.get("size")
        if isinstance(size, int):
            return size
    return None


# 读取集合当前点位数量。
def _extract_points_count(collection_info: dict[str, Any]) -> int:
    value = collection_info.get("result", {}).get("points_count", 0)
    if isinstance(value, int):
        return value
    return 0


# 按给定维度创建集合（Cosine）。
def _create_collection(vector_size: int, collection_name: str) -> None:
    url = f"{SETTINGS.qdrant_url}/collections/{collection_name}"
    body = {
        "vectors": {
            "size": vector_size,
            "distance": "Cosine",
        }
    }
    request_json(
        url=url,
        body=body,
        timeout=SETTINGS.qdrant_timeout_seconds,
        method="PUT",
    )


# 确保集合存在且向量维度匹配，必要时创建或重建。
def ensure_collection_ready(
    vector_size: int,
    collection_name: str = SETTINGS.qdrant_collection,
) -> str:
    info_url = f"{SETTINGS.qdrant_url}/collections/{collection_name}"

    try:
        info = request_json(
            url=info_url,
            body=None,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="GET",
        )
    except HTTPError as exc:
        if exc.code != 404:
            raise HTTPException(status_code=503, detail=http_error_detail("读取Qdrant集合失败", exc)) from exc

        try:
            _create_collection(vector_size, collection_name=collection_name)
        except HTTPError as create_exc:
            raise HTTPException(
                status_code=503,
                detail=http_error_detail("创建Qdrant集合失败", create_exc),
            ) from create_exc
        except (URLError, TimeoutError) as create_exc:
            raise HTTPException(status_code=503, detail=f"创建Qdrant集合失败: {create_exc}") from create_exc
        return "created"
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=f"读取Qdrant集合失败: {exc}") from exc

    current_size = _extract_vector_size(info)
    if current_size == vector_size:
        return "existing"

    points_count = _extract_points_count(info)
    if points_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Qdrant集合向量维度不匹配，当前{current_size}，需要{vector_size}，"
                f"且集合内仍有{points_count}条数据，请先清理后重建。"
            ),
        )

    try:
        request_json(
            url=info_url,
            body=None,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="DELETE",
        )
        _create_collection(vector_size, collection_name=collection_name)
    except HTTPError as exc:
        raise HTTPException(status_code=503, detail=http_error_detail("重建Qdrant集合失败", exc)) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=f"重建Qdrant集合失败: {exc}") from exc

    return "recreated"


# 读取集合信息；集合不存在时返回None。
def _get_collection_info(collection_name: str) -> dict[str, Any] | None:
    info_url = f"{SETTINGS.qdrant_url}/collections/{collection_name}"
    try:
        return request_json(
            url=info_url,
            body=None,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="GET",
        )
    except HTTPError as exc:
        if exc.code == 404:
            return None
        raise HTTPException(status_code=503, detail=http_error_detail("读取Qdrant集合失败", exc)) from exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=f"读取Qdrant集合失败: {exc}") from exc


# 待审核入库时不用embedding，按现有集合维度写零向量占位。
def _resolve_pending_vector_size(default_size: int = 1024) -> int:
    pending_info = _get_collection_info(PENDING_COLLECTION)
    pending_size = _extract_vector_size(pending_info or {})
    if isinstance(pending_size, int) and pending_size > 0:
        return pending_size

    faq_info = _get_collection_info(SETTINGS.qdrant_collection)
    faq_size = _extract_vector_size(faq_info or {})
    if isinstance(faq_size, int) and faq_size > 0:
        return faq_size

    return default_size


# 先用关键词做精确匹配（归一化字段优先），未命中再滚动扫描兜底。
def retrieve_by_keyword(
    query_text: str,
    limit: int = SETTINGS.default_limit,
) -> list[dict[str, Any]]:
    keyword = query_text.strip()
    normalized_keyword = normalize_for_keyword(keyword)
    if not keyword and not normalized_keyword:
        return []

    scroll_url = f"{SETTINGS.qdrant_url}/collections/{SETTINGS.qdrant_collection}/points/scroll"

    # 发起一次scroll请求，可选带payload过滤条件与分页offset。
    def _scroll_once(
        filter_key: str | None = None,
        filter_value: str | None = None,
        offset: Any | None = None,
        page_size: int | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "limit": page_size or limit,
            "with_payload": True,
            "with_vector": False,
        }
        if filter_key is not None and filter_value is not None:
            body["filter"] = {
                "must": [
                    {
                        "key": filter_key,
                        "match": {"value": filter_value},
                    }
                ]
            }
        if offset is not None:
            body["offset"] = offset

        return request_json(
            url=scroll_url,
            body=body,
            timeout=SETTINGS.qdrant_timeout_seconds,
        )

    # 执行一次带过滤的scroll，并把结果转成统一命中结构。
    def _safe_scroll_hits(filter_key: str, filter_value: str) -> list[dict[str, Any]]:
        try:
            response_data = _scroll_once(filter_key=filter_key, filter_value=filter_value)
        except HTTPError as exc:
            if exc.code == 404:
                return []
            raise HTTPException(status_code=503, detail=http_error_detail("Qdrant关键词检索失败", exc)) from exc
        except (URLError, TimeoutError) as exc:
            raise HTTPException(status_code=503, detail=f"Qdrant关键词检索失败: {exc}") from exc

        return [_point_to_hit(point, score=1.0) for point in _extract_points(response_data)][:limit]

    if normalized_keyword:
        normalized_hits = _safe_scroll_hits("normalized_question", normalized_keyword)
        if normalized_hits:
            return normalized_hits

    if keyword:
        exact_hits = _safe_scroll_hits("question", keyword)
        if exact_hits:
            return exact_hits

    if not normalized_keyword:
        return []

    matched_hits: list[dict[str, Any]] = []
    offset = None
    page_size = max(64, limit)
    for _ in range(20):
        try:
            response_data = _scroll_once(offset=offset, page_size=page_size)
        except HTTPError as exc:
            if exc.code == 404:
                return []
            raise HTTPException(status_code=503, detail=http_error_detail("Qdrant关键词检索失败", exc)) from exc
        except (URLError, TimeoutError) as exc:
            raise HTTPException(status_code=503, detail=f"Qdrant关键词检索失败: {exc}") from exc

        points = _extract_points(response_data)
        if not points:
            break

        for point in points:
            payload = point.get("payload") or {}
            point_normalized = str(payload.get("normalized_question", "")).strip()
            if not point_normalized:
                point_normalized = normalize_for_keyword(str(payload.get("question", "")))
            if point_normalized == normalized_keyword:
                matched_hits.append(_point_to_hit(point, score=1.0))
                if len(matched_hits) >= limit:
                    return matched_hits[:limit]

        offset = _extract_next_page_offset(response_data)
        if offset is None:
            break

    return matched_hits[:limit]


# 用向量到Qdrant做相似度检索，兼容/search与/query两种接口。
def retrieve_from_qdrant(
    query_vector: list[float],
    limit: int = SETTINGS.default_limit,
) -> list[dict[str, Any]]:
    search_url = f"{SETTINGS.qdrant_url}/collections/{SETTINGS.qdrant_collection}/points/search"
    query_url = f"{SETTINGS.qdrant_url}/collections/{SETTINGS.qdrant_collection}/points/query"
    search_body = {
        "vector": query_vector,
        "limit": limit,
        "with_payload": True,
        "with_vector": False,
    }

    try:
        response_data = request_json(
            url=search_url,
            body=search_body,
            timeout=SETTINGS.qdrant_timeout_seconds,
        )
    except HTTPError as exc:
        if exc.code == 404:
            return []
        if exc.code != 405:
            raise HTTPException(status_code=503, detail=http_error_detail("Qdrant请求失败", exc)) from exc

        query_body = {
            "query": query_vector,
            "limit": limit,
            "with_payload": True,
            "with_vector": False,
        }
        try:
            response_data = request_json(
                url=query_url,
                body=query_body,
                timeout=SETTINGS.qdrant_timeout_seconds,
            )
        except HTTPError as fallback_exc:
            if fallback_exc.code == 404:
                return []
            raise HTTPException(
                status_code=503,
                detail=http_error_detail("Qdrant请求失败", fallback_exc),
            ) from fallback_exc
        except (URLError, TimeoutError) as fallback_exc:
            raise HTTPException(status_code=503, detail=f"Qdrant请求失败: {fallback_exc}") from fallback_exc
    except (URLError, TimeoutError) as exc:
        raise HTTPException(status_code=503, detail=f"Qdrant请求失败: {exc}") from exc

    points = _extract_points(response_data)
    hits: list[dict[str, Any]] = []
    for point in points:
        payload = point.get("payload") or {}
        question = str(payload.get("question", "")).strip()
        answer = str(payload.get("answer", "")).strip()

        raw_score = point.get("score", point.get("distance", 0.0))
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            score = 0.0

        hits.append(
            {
                "id": point.get("id"),
                "question": question,
                "answer": answer,
                "score": score,
            }
        )

    return hits[:limit]


# 为关键词缓存生成稳定点位ID（同问法会覆盖更新）。
def _keyword_cache_point_id(
    question: str,
    collection_name: str = SETTINGS.qdrant_collection,
) -> str:
    normalized_question = normalize_for_keyword(question)
    key = f"{collection_name}:keyword:{normalized_question or question.strip()}"
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


# 将embedding命中的问法回写到知识库，便于下次关键词直接命中。
def cache_keyword_from_embedding(
    question: str,
    query_vector: list[float],
    best_hit: dict[str, Any],
) -> dict[str, Any]:
    clean_question = question.strip()
    normalized_question = normalize_for_keyword(clean_question)
    answer = str(best_hit.get("answer", "")).strip()
    if not normalized_question or not answer:
        return {"saved": False, "reason": "question_or_answer_empty"}

    point_id = _keyword_cache_point_id(
        clean_question,
        collection_name=SETTINGS.qdrant_collection,
    )
    upsert_url = (
        f"{SETTINGS.qdrant_url}/collections/{SETTINGS.qdrant_collection}/points?wait=true"
    )
    body = {
        "points": [
            {
                "id": point_id,
                "vector": query_vector,
                "payload": {
                    "question": clean_question,
                    "normalized_question": normalized_question,
                    "answer": answer,
                    "cache_type": "embedding_fallback",
                    "cached_from_id": best_hit.get("id"),
                    "cached_from_score": best_hit.get("score"),
                },
            }
        ]
    }

    try:
        ensure_collection_ready(
            len(query_vector),
            collection_name=SETTINGS.qdrant_collection,
        )
        result = request_json(
            url=upsert_url,
            body=body,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="PUT",
        )
        return {
            "saved": True,
            "id": point_id,
            "result": result.get("result"),
        }
    except HTTPException as exc:
        return {"saved": False, "error": str(exc.detail)}
    except HTTPError as exc:
        return {"saved": False, "error": http_error_detail("写入关键词缓存失败", exc)}
    except (URLError, TimeoutError) as exc:
        return {"saved": False, "error": f"写入关键词缓存失败: {exc}"}


# 将问答模型返回结果写入知识库，便于后续直接命中。
def cache_answer_from_qa(
    question: str,
    answer: str,
    collection_name: str = SETTINGS.qdrant_collection,
    *,
    extra_payload: dict[str, Any] | None = None,
    stable_point_id: bool = True,
) -> dict[str, Any]:
    clean_question = question.strip()
    normalized_question = normalize_for_keyword(clean_question)
    clean_answer = answer.strip()
    if not normalized_question or not clean_answer:
        return {"saved": False, "reason": "question_or_answer_empty"}

    try:
        query_vector = build_query_embedding(clean_question)
        ensure_collection_ready(
            len(query_vector),
            collection_name=collection_name,
        )
    except HTTPException as exc:
        return {"saved": False, "error": str(exc.detail)}

    point_id = (
        _keyword_cache_point_id(clean_question, collection_name=collection_name)
        if stable_point_id
        else str(uuid.uuid4())
    )
    upsert_url = (
        f"{SETTINGS.qdrant_url}/collections/{collection_name}/points?wait=true"
    )
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
                "id": point_id,
                "vector": query_vector,
                "payload": payload,
            }
        ]
    }

    try:
        result = request_json(
            url=upsert_url,
            body=body,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="PUT",
        )
        return {
            "saved": True,
            "id": point_id,
            "collection": collection_name,
            "result": result.get("result"),
        }
    except HTTPException as exc:
        return {"saved": False, "error": str(exc.detail)}
    except HTTPError as exc:
        return {"saved": False, "error": http_error_detail("写入问答结果失败", exc)}
    except (URLError, TimeoutError) as exc:
        return {"saved": False, "error": f"写入问答结果失败: {exc}"}


# 当关闭自动写主知识库时，把LLM问答结果写入待审核集合。
def cache_answer_to_pending(question: str, answer: str) -> dict[str, Any]:
    clean_question = question.strip()
    normalized_question = normalize_for_keyword(clean_question)
    clean_answer = answer.strip()
    if not normalized_question or not clean_answer:
        return {"saved": False, "reason": "question_or_answer_empty"}

    try:
        vector_size = _resolve_pending_vector_size()
        ensure_collection_ready(
            vector_size,
            collection_name=PENDING_COLLECTION,
        )
    except HTTPException as exc:
        return {"saved": False, "error": str(exc.detail)}

    point_id = str(uuid.uuid4())
    upsert_url = f"{SETTINGS.qdrant_url}/collections/{PENDING_COLLECTION}/points?wait=true"
    body = {
        "points": [
            {
                "id": point_id,
                "vector": [0.0] * vector_size,
                "payload": {
                    "question": clean_question,
                    "normalized_question": normalized_question,
                    "answer": clean_answer,
                    "status": "pending",
                    "cache_type": "qa_pending_review",
                    "pending_vector_type": "placeholder_zero",
                },
            }
        ]
    }

    try:
        result = request_json(
            url=upsert_url,
            body=body,
            timeout=SETTINGS.qdrant_timeout_seconds,
            method="PUT",
        )
        return {
            "saved": True,
            "id": point_id,
            "collection": PENDING_COLLECTION,
            "result": result.get("result"),
        }
    except HTTPError as exc:
        return {"saved": False, "error": http_error_detail("写入待审核结果失败", exc)}
    except (URLError, TimeoutError) as exc:
        return {"saved": False, "error": f"写入待审核结果失败: {exc}"}
