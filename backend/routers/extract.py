from fastapi import APIRouter, File, Form, HTTPException, UploadFile
import asyncio
import json
import os

from models.schemas import ExtractionResponse, PromptDefinition
from services.ollama import extract_from_page, normalize_results
from services.pdf import image_to_base64, pdf_to_base64_pages

router = APIRouter(prefix="/api", tags=["extraction"])

MAX_BYTES    = int(os.getenv("MAX_FILE_MB", 20)) * 1024 * 1024
MAX_CONCURRENCY = int(os.getenv("MAX_PAGE_CONCURRENCY", 4))
ALLOWED_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/webp",
}


@router.post("/extract", response_model=ExtractionResponse)
async def extract(
    file: UploadFile = File(...),
    prompts: str = Form(...),
    document_type: str = Form("document"),
):
    # ── Validate file ──────────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_BYTES:
        raise HTTPException(413, "File exceeds size limit")

    # ── Parse prompts ──────────────────────────────────────────────────────────
    try:
        prompt_list = [PromptDefinition(**p) for p in json.loads(prompts)]
    except Exception:
        raise HTTPException(400, "Invalid prompts JSON")

    if not prompt_list:
        raise HTTPException(400, "At least one prompt is required")

    # ── Convert file to page images ────────────────────────────────────────────
    if file.content_type == "application/pdf":
        pages = pdf_to_base64_pages(file_bytes)
    else:
        pages = image_to_base64(file_bytes)

    # ── Extract per page then merge (bounded concurrency to protect Ollama) ──
    sem = asyncio.Semaphore(MAX_CONCURRENCY)

    async def bounded_extract(page):
        async with sem:
            return await extract_from_page(page, prompt_list, document_type)

    all_page_results = await asyncio.gather(*[bounded_extract(page) for page in pages])
    final_results = await normalize_results(all_page_results, prompt_list, document_type)
    successful    = sum(1 for r in final_results if r.confidence != "not_found")

    return ExtractionResponse(
        results=final_results,
        document_type=document_type,
        total_pages=len(pages),
        total_prompts=len(prompt_list),
        successful_extractions=successful,
    )


@router.get("/health")
async def health():
    return {"status": "ok"}
