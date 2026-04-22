from __future__ import annotations

from time import monotonic
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query

from config.settings import load_settings

from .embedding import build_query_embedding
from .hit_chain_log import get_log_file_path, write_hit_chain_log
from .qa_model import ask_qa_model
from .qdrant import (
    cache_answer_from_qa,
    cache_answer_to_pending,
    cache_keyword_from_embedding,
    retrieve_by_keyword,
    retrieve_from_qdrant,
)
from .text_normalize import normalize_for_keyword


router = APIRouter()


def _elapsed_ms(start_time: float) -> float:
    return round((monotonic() - start_time) * 1000, 2)


def _append_step(trace: dict[str, Any], step: str, start_time: float, **extra: Any) -> None:
    item: dict[str, Any] = {
        "step": step,
        "elapsed_ms": _elapsed_ms(start_time),
    }
    item.update(extra)
    trace["steps"].append(item)


def _log_hit_chain(
    trace: dict[str, Any],
    *,
    final_source: str,
    matched: bool,
    response: dict[str, object] | None = None,
    score: float | None = None,
    error: str | None = None,
) -> None:
    log_payload = {
        "request_id": trace["request_id"],
        "path": trace["path"],
        "content": trace["content"],
        "normalized_content": trace.get("normalized_content", ""),
        "steps": trace["steps"],
        "llm_called": trace.get("llm_called", False),
        "final_source": final_source,
        "matched": matched,
        "score": score,
        "total_elapsed_ms": _elapsed_ms(trace["started_at"]),
        "log_file": str(get_log_file_path()),
    }
    if response is not None:
        answer = str(response.get("answer", ""))
        log_payload["vector_hit"] = bool(response.get("vector_hit", False))
        log_payload["answer_preview"] = answer[:200]
    if error:
        log_payload["error"] = error
    write_hit_chain_log(log_payload)


def _reply_by_qa_or_fallback(
    content: str,
    runtime,
    vector_hit: bool,
    trace: dict[str, Any],
) -> tuple[dict[str, object], str]:
    if runtime.enable_qa_model:
        trace["llm_called"] = True
        qa_start = monotonic()
        try:
            qa_answer = ask_qa_model(content, runtime)
        except HTTPException as exc:
            _append_step(
                trace,
                "qa_model_answer",
                qa_start,
                ok=False,
                error=str(exc.detail),
            )
        else:
            _append_step(
                trace,
                "qa_model_answer",
                qa_start,
                ok=True,
                answer_chars=len(qa_answer),
            )


            cache_start = monotonic()
            if runtime.auto_cache_qa_answer:
                cache_result = cache_answer_from_qa(content, qa_answer)
                cache_mode = "faq_direct"
            else:
                cache_result = cache_answer_to_pending(content, qa_answer)
                cache_mode = "pending_review"
            cache_saved = bool(cache_result.get("saved", False))
            _append_step(
                trace,
                "qa_answer_cache_write",
                cache_start,
                mode=cache_mode,
                collection=cache_result.get("collection"),
                saved=cache_saved,
                point_id=cache_result.get("id"),
                error=cache_result.get("error"),
            )
            if not cache_saved:
                return {
                    "content": content,
                    "vector_hit": vector_hit,
                    "answer": runtime.not_configured_answer,
                }, "fallback"

            return {
                "content": content,
                "vector_hit": vector_hit,
                "answer": qa_answer,
            }, "llm"

    return {
        "content": content,
        "vector_hit": vector_hit,
        "answer": runtime.not_configured_answer,
    }, "fallback"

@router.get("/api/")
def search_faq(
    content: str = Query(..., description="用户提问"),
):
    trace: dict[str, Any] = {
        "request_id": uuid4().hex,
        "path": "/api/",
        "content": content,
        "steps": [],
        "llm_called": False,
        "started_at": monotonic(),
    }

    try:
        # 步骤0：读取运行时配置（每次请求动态读取，后台改配置后可直接生效）。
        step_start = monotonic()
        runtime = load_settings()
        _append_step(
            trace,
            "load_runtime_config",
            step_start,
            auto_retrieve_knowledge=runtime.auto_retrieve_knowledge,
            enable_qa_model=runtime.enable_qa_model,
            auto_cache_qa_answer=runtime.auto_cache_qa_answer,
            similarity_threshold=runtime.similarity_threshold,
            min_embedding_chars=runtime.min_embedding_chars,
        )

        # 步骤1：先做关键词检索（不调用embedding），命中则直接返回。
        keyword_start = monotonic()
        keyword_hits = retrieve_by_keyword(content, limit=1)
        keyword_hit = keyword_hits[0] if keyword_hits else None
        _append_step(
            trace,
            "keyword_retrieve",
            keyword_start,
            hit=bool(keyword_hit),
            hit_id=keyword_hit.get("id") if keyword_hit else None,
        )
        if keyword_hit:
            best_answer = keyword_hit.get("answer") or runtime.not_configured_answer
            response = {
                "content": content,  # 原始提问
                "vector_hit": True,  # True表示未走向量检索（关键词已命中）
                "answer": best_answer,  # 命中后的答案
            }
            _log_hit_chain(
                trace,
                final_source="keyword",
                matched=True,
                response=response,
                score=1.0,
            )
            return response

        # 步骤2：对输入做归一化，长度过短则不走embedding，直接返回兜底答案。
        normalize_start = monotonic()
        normalized_content = normalize_for_keyword(content)
        trace["normalized_content"] = normalized_content
        is_short_text = len(normalized_content) < runtime.min_embedding_chars
        _append_step(
            trace,
            "normalize_and_short_gate",
            normalize_start,
            normalized_length=len(normalized_content),
            short_text=is_short_text,
        )
        if is_short_text:
            response = {
                "content": content,
                "vector_hit": True,
                "answer": runtime.not_configured_answer,
            }
            _log_hit_chain(
                trace,
                final_source="fallback",
                matched=False,
                response=response,
            )
            return response

        # 步骤2.5：当关闭“自动检索知识库”时，直接跳过步骤3-6并返回问答或兜底。
        if not runtime.auto_retrieve_knowledge:
            gate_start = monotonic()
            _append_step(
                trace,
                "auto_retrieve_gate",
                gate_start,
                enabled=False,
            )
            response, final_source = _reply_by_qa_or_fallback(
                content=content,
                runtime=runtime,
                vector_hit=True,
                trace=trace,
            )
            _log_hit_chain(
                trace,
                final_source=final_source,
                matched=final_source == "llm",
                response=response,
            )
            return response

        # 步骤3：关键词未命中且长度达标，调用embedding把问题转成向量。
        embedding_start = monotonic()
        query_vector = build_query_embedding(content)
        _append_step(
            trace,
            "build_query_embedding",
            embedding_start,
            vector_size=len(query_vector),
        )

        # 步骤4：用向量到知识库检索Top1，并按相似度阈值判断是否有效命中。
        vector_search_start = monotonic()
        hits = retrieve_from_qdrant(query_vector, limit=1)
        best_raw_hit = hits[0] if hits else None
        top_score = None
        if best_raw_hit:
            try:
                top_score = float(best_raw_hit.get("score", 0.0))
            except (TypeError, ValueError):
                top_score = 0.0
        best_hit = None
        if top_score is not None and top_score >= runtime.similarity_threshold:
            best_hit = best_raw_hit
        _append_step(
            trace,
            "vector_retrieve",
            vector_search_start,
            top_score=top_score,
            threshold=runtime.similarity_threshold,
            hit=bool(best_hit),
            hit_id=best_hit.get("id") if best_hit else None,
        )

        # 步骤5：向量检索未达阈值，返回问答或兜底答案。
        if not best_hit:
            response, final_source = _reply_by_qa_or_fallback(
                content=content,
                runtime=runtime,
                vector_hit=False,
                trace=trace,
            )
            _log_hit_chain(
                trace,
                final_source=final_source,
                matched=final_source == "llm",
                response=response,
                score=top_score,
            )
            return response

        # 步骤6：向量命中后返回答案，并把当前问法回写到知识库（便于下次关键词直接命中）。
        cache_start = monotonic()
        cache_result = cache_keyword_from_embedding(content, query_vector, best_hit)
        _append_step(
            trace,
            "vector_hit_cache_write",
            cache_start,
            saved=cache_result.get("saved"),
            point_id=cache_result.get("id"),
            error=cache_result.get("error"),
        )
        best_answer = best_hit.get("answer") or runtime.not_configured_answer
        response = {
            "content": content,  # 原始提问
            "vector_hit": False,  # False表示本次走了向量检索
            "answer": best_answer,  # 向量命中的答案
        }
        _log_hit_chain(
            trace,
            final_source="vector",
            matched=True,
            response=response,
            score=top_score,
        )
        return response
    except HTTPException as exc:
        _log_hit_chain(
            trace,
            final_source="error",
            matched=False,
            error=str(exc.detail),
        )
        raise
    except Exception as exc:
        _log_hit_chain(
            trace,
            final_source="error",
            matched=False,
            error=f"{type(exc).__name__}: {exc}",
        )
        raise
