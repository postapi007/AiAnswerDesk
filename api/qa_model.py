from __future__ import annotations

import os
from time import monotonic

from fastapi import HTTPException

from .embedding import build_query_embedding
from .qdrant import retrieve_from_qdrant
from config.settings import AppSettings


def _render_qa_prompt(template: str, content: str, fragmented_data: str = "") -> str:
    base_template = (template or "").strip()
    if not base_template:
        base_template = "请基于已知信息回答用户问题：{content}"
    if "{content}" in base_template:
        prompt = base_template.replace("{content}", content)
    else:
        prompt = f"{base_template}\n\n用户提问：{content}"
    if "{fragmenteddata}" in prompt:
        return prompt.replace("{fragmenteddata}", fragmented_data)
    return prompt


def _format_fragmented_data(hits: list[dict[str, object]]) -> str:
    lines: list[str] = []
    for idx, hit in enumerate(hits, start=1):
        answer_text = str(hit.get("answer", "")).strip()
        if not answer_text:
            continue
        if len(answer_text) > 1200:
            answer_text = f"{answer_text[:1200]}..."
        lines.append(f"{idx}. {answer_text}")
    return "\n".join(lines)


def _build_fragmented_data(content: str, runtime: AppSettings) -> str:
    query = content.strip()
    if not query:
        return ""

    try:
        query_vector = build_query_embedding(query)
        raw_hits = retrieve_from_qdrant(
            query_vector=query_vector,
            limit=runtime.fragment_read_limit,
            collection_name=runtime.qdrant_docs_collection,
        )
    except Exception as exc:
        print(f"[qa_model] fragmenteddata retrieve failed: {type(exc).__name__}: {exc}", flush=True)
        return ""

    filtered_hits: list[dict[str, object]] = []
    for hit in raw_hits:
        try:
            score = float(hit.get("score", 0.0))
        except (TypeError, ValueError):
            score = 0.0
        if score < runtime.fragment_read_similarity_threshold:
            continue
        filtered_hits.append(hit)
        if len(filtered_hits) >= runtime.fragment_read_limit:
            break

    fragmented_data = _format_fragmented_data(filtered_hits)
    # print(
    #     "[qa_model] fragmenteddata "
    #     f"hits={len(filtered_hits)} "
    #     f"threshold={runtime.fragment_read_similarity_threshold} "
    #     f"limit={runtime.fragment_read_limit}",
    #     flush=True,
    # )
    return fragmented_data


def _extract_text_from_response(response: object) -> str:
    choices = getattr(response, "choices", None)
    if not isinstance(choices, list) or not choices:
        return ""

    first_choice = choices[0]
    message = getattr(first_choice, "message", None)
    if message is None:
        return ""

    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
                continue
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts).strip()

    return ""


# 调用问答模型，把模板与{content}渲染后提交给模型并返回文本结果。
def ask_qa_model(content: str, runtime: AppSettings) -> str:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="缺少依赖 openai，请在当前运行环境执行: pip install openai",
        ) from exc

    api_key = os.getenv(runtime.qa_api_key_env, "").strip()
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=f"缺少问答模型 API Key，请设置环境变量: {runtime.qa_api_key_env}",
        )

    base_template = runtime.qa_prompt_template or ""
    fragmented_data = ""
    if "{fragmenteddata}" in base_template:
        fragmented_data = _build_fragmented_data(content, runtime)
    prompt = _render_qa_prompt(base_template, content, fragmented_data)
    # print(f"[qa_model] request model={runtime.qa_model} base_url={runtime.qa_base_url}", flush=True)
    # print(f"[qa_model] request_prompt_start\n{prompt}\n[qa_model] request_prompt_end", flush=True)
    start_time = monotonic()

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=runtime.qa_base_url,
            timeout=runtime.qa_timeout_seconds,
            max_retries=0,
        )
        response = client.chat.completions.create(
            model=runtime.qa_model,
            messages=[{"role": "user", "content": prompt}],
            timeout=runtime.qa_timeout_seconds,
        )
    except Exception as exc:
        elapsed = monotonic() - start_time
        raise HTTPException(
            status_code=503,
            detail=f"问答模型请求失败[{type(exc).__name__}]({elapsed:.2f}s): {exc}",
        ) from exc

    answer = _extract_text_from_response(response)
    if not answer:
        raise HTTPException(status_code=502, detail="问答模型响应格式异常: 缺少有效文本")
    elapsed = monotonic() - start_time
    print(f"[qa_model] success elapsed={elapsed:.2f}s answer_chars={len(answer)}", flush=True)
    return answer
