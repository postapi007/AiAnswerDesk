from __future__ import annotations

from pydantic import BaseModel, Field


class FirstKnowledgeRequest(BaseModel):
    question: str = Field(..., min_length=1, description="问题")
    answer: str = Field(..., min_length=1, description="答案")

