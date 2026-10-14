from __future__ import annotations

from pydantic import BaseModel, Field


class KnowledgeIngestResponse(BaseModel):
    knowledge_base_id: str
    filename: str
    chunks_indexed: int = Field(ge=0)
    version: str
