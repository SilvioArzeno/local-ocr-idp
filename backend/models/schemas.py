from pydantic import BaseModel
from typing import Any


class PromptDefinition(BaseModel):
    key: str
    question: str
    type: str = "string"       # string | number | date | array | boolean
    required: bool = False


class PromptResult(BaseModel):
    key: str
    question: str
    value: Any
    confidence: str            # high | medium | low | not_found


class ExtractionResponse(BaseModel):
    results: list[PromptResult]
    document_type: str
    total_pages: int
    total_prompts: int
    successful_extractions: int
