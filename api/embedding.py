from __future__ import annotations

import os

from fastapi import HTTPException

from config import SETTINGS


# 调用配置的Embedding模型，把输入文本转换为浮点向量并返回。
def build_query_embedding(text: str) -> list[float]:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise HTTPException(
            status_code=500,
            detail="缺少依赖 openai，请在当前运行环境执行: pip install openai",
        ) from exc

    api_key = os.getenv(SETTINGS.embedding_api_key_env, "").strip()
    if not api_key:
        raise HTTPException(
            status_code=500,
            detail=(
                f"缺少Embedding API Key，请设置环境变量: {SETTINGS.embedding_api_key_env}"
            ),
        )

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=SETTINGS.embedding_base_url,
        )
        response = client.embeddings.create(
            model=SETTINGS.embedding_model,
            input=text,
            timeout=SETTINGS.embedding_timeout_seconds,
        )
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Embedding请求失败: {exc}") from exc

    data = getattr(response, "data", None)
    if not isinstance(data, list) or not data:
        raise HTTPException(status_code=502, detail="Embedding响应格式异常: 缺少data")

    first = data[0]
    vector = getattr(first, "embedding", None)
    if not isinstance(vector, list) or not vector:
        raise HTTPException(status_code=502, detail="Embedding响应格式异常: 缺少embedding")

    try:
        return [float(item) for item in vector]
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="Embedding响应格式异常: embedding含非法值") from exc
