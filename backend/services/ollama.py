import asyncio
import requests
import json
import re
import os
from models.schemas import PromptDefinition, PromptResult

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL      = os.getenv("OLLAMA_MODEL", "minicpm-v")
TIMEOUT    = int(os.getenv("OLLAMA_TIMEOUT", "600"))

# Standard lab acronyms we extract server-side from all pages
STANDARD_ACRONYMS = frozenset({
    "WBC", "RBC", "Platelets", "HGB", "NA", "Creat", "K", "AST", "ALT",
    "PT", "PTT", "INR", "Glucose", "HbA1C", "T3", "T4", "TSH", "HIV",
    "CD4", "BHCG", "HepC",
})
_NOT_FOUND = frozenset({
    "not_found", "not found", "not provided", "n/a", "none", "", "null", "not available",
})

# Maps verbose/alias test names → standard acronym
_NAME_TO_ACRONYM: dict[str, str] = {
    "wbc": "WBC", "white blood cell": "WBC", "white blood count": "WBC",
    "rbc": "RBC", "red blood cell": "RBC", "red blood count": "RBC",
    "platelets": "Platelets", "platelet": "Platelets",
    "hemoglobin": "HGB", "hgb": "HGB", "haemoglobin": "HGB",
    "sodium": "NA", "na": "NA",
    "creatinine": "Creat", "creat": "Creat",
    "potassium": "K",
    "ast": "AST", "ast (sgot)": "AST", "sgot": "AST", "aspartate aminotransferase": "AST",
    "alt": "ALT", "alt (sgpt)": "ALT", "sgpt": "ALT", "alanine aminotransferase": "ALT",
    "pt": "PT", "prothrombin time": "PT",
    "ptt": "PTT", "partial thromboplastin time": "PTT",
    "inr": "INR",
    "glucose": "Glucose",
    "hba1c": "HbA1C", "hemoglobin a1c": "HbA1C", "haemoglobin a1c": "HbA1C",
    "t3": "T3", "t4": "T4", "tsh": "TSH",
    "hiv": "HIV",
    "cd4": "CD4",
    "bhcg": "BHCG", "hcg": "BHCG", "beta hcg": "BHCG",
    "hepc": "HepC", "hep c": "HepC", "hepatitis c": "HepC",
}


def _is_numeric(val) -> bool:
    if val is None:
        return False
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return True
    try:
        float(str(val))
        return True
    except (ValueError, TypeError):
        return False


def _coerce_numeric(val) -> float | None:
    try:
        return float(str(val))
    except (ValueError, TypeError):
        return None


def _build_extraction_prompt(prompts: list[PromptDefinition], doc_type: str) -> str:
    definitions = "\n".join([
        f"{i+1}. key=\"{p.key}\" | type={p.type} | required={p.required} | question: {p.question}"
        for i, p in enumerate(prompts)
    ])
    return f"""You are a precise data extraction assistant analyzing a {doc_type} document.

Answer every prompt listed below using ONLY information visible in the document.
Return a JSON array - one object per prompt, in the exact same order.

Each object must have:
  "key"        -> copy the key exactly as listed
  "value"      -> extracted value, or null if not found
  "confidence" -> "high", "medium", "low", or "not_found"

Prompts:
{definitions}

Strict rules:
- Dates -> MM/DD/YYYY format
- Arrays -> actual JSON arrays, never a stringified list
- Numbers -> numeric only, no units inside the value
- null + "not_found" when the document does not contain the answer
- Return ONLY the raw JSON array. No markdown fences. No commentary.

[
  {{"key": "example_key", "value": "extracted value", "confidence": "high"}},
  ...
]"""


def _compact_page(raw: str, prompts: list[PromptDefinition]) -> str:
    """
    Extract a compact summary of a page for the normalization model.
    Only use parsed JSON if it contains proper {"key": ..., "value": ...} extraction objects.
    Otherwise fall back to raw text so scalar fields (name, DOB, date) are preserved.
    """
    items = _parse_json_array(raw)
    # Only trust the parsed array if it looks like our extraction format
    if items and isinstance(items[0], dict) and "key" in items[0]:
        return json.dumps(items, separators=(',', ':'))
    # Fall back to raw text — preserves all fields including patient_name / date_of_birth
    return raw[:2000] + ("…" if len(raw) > 2000 else "")


def _build_normalization_prompt(
    prompts: list[PromptDefinition],
    doc_type: str,
    page_summaries: list[str],
) -> str:
    definitions = "\n".join([
        f"{i+1}. key=\"{p.key}\" | type={p.type} | question: {p.question}"
        for i, p in enumerate(prompts)
    ])
    pages_text = "\n\n".join([
        f"=== PAGE {i+1} ===\n{text}" for i, text in enumerate(page_summaries)
    ])
    keys_list = ", ".join(f'"{p.key}"' for p in prompts)
    example = json.dumps([
        {"key": p.key, "value": "best value found across ALL pages", "confidence": "high"}
        for p in prompts
    ], indent=2)
    TEST_ACRONYMS = "WBC, RBC, Platelets, HGB, NA, Creat, K, AST, ALT, PT, PTT, INR, Glucose, HbA1C, T3, T4, TSH, HIV, CD4, BHCG, HepC"
    return f"""You are a data consolidation assistant. A {doc_type} was split into {len(page_summaries)} pages and each page was scanned independently. Your job is to consolidate ALL pages into ONE final answer per field.

Fields to extract:
{definitions}

Per-page extractions (ALL pages — read every single one):
{pages_text}

CRITICAL OUTPUT RULES:
- Return a JSON ARRAY (starts with [ ends with ]) with exactly {len(prompts)} objects
- Each object must have exactly: "key", "value", "confidence"
- Keys must be exactly: {keys_list} — in that order
- confidence -> "high", "medium", "low", or "not_found"
- NO markdown fences, NO comments, NO extra text — output ONLY the JSON array

FIELD-SPECIFIC RULES:
- patient_name: Find the name repeated most consistently across pages. Strip IDs, DOBs, and encounter info. Convert "LASTNAME, Firstname" → "Firstname Lastname".
- date_of_birth: MM/DD/YYYY. Fix malformed dates (e.g. "1/05/1971" → "01/05/1971").
- collected_date: MM/DD/YYYY. Use the specimen collected date (not signed/reviewed date).
- test_results: Merge numeric lab values from ALL pages into ONE flat JSON object using ONLY these acronyms as keys: {TEST_ACRONYMS}. Only include a key if an actual numeric value was found (not null, not "not found"). Example: {{"WBC": 5.5, "RBC": 4.73, "HGB": 11.7, "HbA1C": 6.2}}

Required output format:
{example}"""


def _merge_test_results(raw_page_responses: list[str]) -> dict:
    """
    Scan all raw page responses and merge numeric lab values for standard acronyms.
    Handles:
      - Direct dicts:    [{"WBC": 5.5}, {"NA": "20.3", "confidence": "high"}]
      - Verbose CBC:     [{"Test": "WBC", "Current Result and Flag": "5.5", ...}]
      - Plain text:      "NA": "20.3"
    """
    merged: dict = {}

    for raw in raw_page_responses:
        cleaned = re.sub(r"```json|```", "", raw).strip()
        # Fix missing "value": before inline arrays so we can find test_results arrays
        fixed = re.sub(r'("key"\s*:\s*"[^"]+"\s*,\s*)(\[)', r'\1"value": \2', cleaned)

        arr_match = re.search(r"\[.*\]", fixed, re.DOTALL)
        if arr_match:
            try:
                data = json.loads(arr_match.group(0))
                if isinstance(data, list):
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        # Verbose CBC: {"Test": "WBC", "Current Result and Flag": "5.5"}
                        if "Test" in item and "Current Result and Flag" in item:
                            test_name = str(item["Test"]).split("^")[0].strip().upper()
                            raw_val = item["Current Result and Flag"]
                            for acronym in STANDARD_ACRONYMS:
                                if acronym.upper() == test_name and acronym not in merged:
                                    if _is_numeric(raw_val):
                                        num = _coerce_numeric(raw_val)
                                        if num is not None:
                                            merged[acronym] = num
                                    break
                        elif "name" in item or "acronym" in item:
                            # CMP format: {"name": "AST (SGOT)", "acronym": "AST", "value": "17"}
                            raw_acronym = str(item.get("acronym", "")).strip()
                            raw_name = str(item.get("name", "")).lower().strip()
                            acronym = None
                            for std in STANDARD_ACRONYMS:
                                if raw_acronym.upper() == std.upper():
                                    acronym = std
                                    break
                            if not acronym:
                                acronym = _NAME_TO_ACRONYM.get(raw_name)
                            if acronym and acronym not in merged:
                                val = item.get("value")
                                if _is_numeric(val):
                                    num = _coerce_numeric(val)
                                    if num is not None:
                                        merged[acronym] = num
                        else:
                            # Direct: {"WBC": 5.5} or {"NA": "20.3", "confidence": "high"}
                            for key, val in item.items():
                                if key in ("confidence", "units", "flag"):
                                    continue
                                if key in STANDARD_ACRONYMS and key not in merged:
                                    str_val = str(val).strip().lower() if val is not None else ""
                                    if str_val not in _NOT_FOUND and _is_numeric(val):
                                        num = _coerce_numeric(val)
                                        if num is not None:
                                            merged[key] = num
            except (json.JSONDecodeError, ValueError):
                pass

        # Regex scan for any remaining acronyms in raw text
        for acronym in STANDARD_ACRONYMS:
            if acronym in merged:
                continue
            m = re.search(rf'"{re.escape(acronym)}"\s*:\s*"?(-?\d+\.?\d*)"?', raw)
            if m:
                try:
                    merged[acronym] = float(m.group(1))
                except ValueError:
                    pass

    return merged


def _call_ollama(payload: dict) -> dict:
    """Blocking Ollama HTTP call — run via asyncio.to_thread."""
    resp = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def _parse_json_array(raw: str) -> list[dict] | None:
    """Extract and parse a JSON array from a model response."""
    cleaned = re.sub(r"```json|```", "", raw).strip()
    cleaned = re.sub(r"//[^\n]*", "", cleaned)
    cleaned = _repair_json(cleaned)
    # Fix missing "value": before inline array — model often emits "key": "x", [...] instead of "key": "x", "value": [...]
    cleaned = re.sub(r'("key"\s*:\s*"[^"]+"\s*,\s*)(\[)', r'\1"value": \2', cleaned)
    match = re.search(r"\[.*\]", cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _repair_json(text: str) -> str:
    """
    Fix the most common model JSON malformations:
    - Unquoted keys:          confidence: → "confidence":
    - Unquoted bare values:   : not_found → : "not_found"
    Already-quoted keys are safe: lookbehind prevents re-quoting "key":.
    """
    # Quote unquoted keys (not preceded by " or a word char)
    text = re.sub(r'(?<!["\w])([a-zA-Z_]\w*)\s*(?=:)', r'"\1"', text)
    # Quote unquoted bare-word values after colon (skip null/true/false and numbers)
    text = re.sub(
        r'(?<=:)\s*([a-zA-Z_][a-zA-Z0-9_ ]*[a-zA-Z0-9_])\b(?=\s*[,}\]])',
        lambda m: f' "{m.group(1)}"' if m.group(1) not in ('null', 'true', 'false') else f' {m.group(1)}',
        text,
    )
    return text


def _parse_normalization_response(raw: str, prompts: list[PromptDefinition]) -> list[dict] | None:
    """
    Parse normalization output. Handles multiple model response formats:
    1. Expected array:        [{"key": "patient_name", "value": "...", "confidence": "high"}, ...]
    2. Flat object:           {"patient_name": "...", "collected_date": "...", ...}
    3. Array of page objects: [{"patient_name": "...", ...}, {"patient_name": "...", ...}, ...]
       (model echoed per-page summaries instead of consolidating — we consolidate ourselves)
    """
    cleaned = re.sub(r"```json|```", "", raw).strip()
    cleaned = re.sub(r"//[^\n]*", "", cleaned)
    cleaned = _repair_json(cleaned)
    prompt_keys = {p.key for p in prompts}

    # --- Try expected array format first ---
    fixed = re.sub(r'("key"\s*:\s*"[^"]+"\s*,\s*)(\[)', r'\1"value": \2', cleaned)
    arr_match = re.search(r"\[.*\]", fixed, re.DOTALL)
    if arr_match:
        try:
            items = json.loads(arr_match.group(0))
            if isinstance(items, list) and items and isinstance(items[0], dict):
                # Format 1: expected [{key, value, confidence}, ...]
                if "key" in items[0]:
                    return items
                # Format 3: array of per-page objects — consolidate by taking first non-null value
                if prompt_keys & set(items[0].keys()):
                    consolidated: dict = {}
                    for page_obj in items:
                        if not isinstance(page_obj, dict):
                            continue
                        for k, v in page_obj.items():
                            if k not in prompt_keys or k in consolidated:
                                continue
                            if v is not None and str(v).lower().strip() not in _NOT_FOUND:
                                consolidated[k] = v
                    return [
                        {
                            "key": p.key,
                            "value": consolidated.get(p.key),
                            "confidence": "high" if consolidated.get(p.key) is not None else "not_found",
                        }
                        for p in prompts
                    ]
        except json.JSONDecodeError:
            pass

    # --- Fallback: flat object {"patient_name": val, "date_of_birth": val, ...} ---
    obj_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if obj_match:
        try:
            obj = json.loads(obj_match.group(0))
            if isinstance(obj, dict) and prompt_keys & set(obj.keys()):
                return [
                    {
                        "key": p.key,
                        "value": obj.get(p.key),
                        "confidence": "high" if obj.get(p.key) is not None else "not_found",
                    }
                    for p in prompts
                ]
        except json.JSONDecodeError:
            pass

    return None


async def extract_from_page(
    image_b64: str,
    prompts: list[PromptDefinition],
    doc_type: str,
) -> str:
    """Run extraction on a single page. Returns the raw model response text."""
    payload = {
        "model": MODEL,
        "prompt": _build_extraction_prompt(prompts, doc_type),
        "images": [image_b64],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "top_p": 0.9,
            "num_ctx": int(os.getenv("OLLAMA_CTX", "4096")),
        },
    }

    data = await asyncio.to_thread(_call_ollama, payload)
    raw = data.get("response", "")
    print(f"[ollama page response]\n{raw}\n", flush=True)
    return raw


def _fix_patient_name(name: str | None) -> str | None:
    """Convert 'LASTNAME, Firstname ...' to 'Firstname Lastname', strip IDs/DOBs/duplicates."""
    if not name:
        return name
    # Strip everything after a paren or 'id #' or 'dob:'
    name = re.split(r'\s*[\(\[]|\s+id\s*#|\s+dob:', name, flags=re.IGNORECASE)[0].strip()
    # Convert "LAST, First Middle [Last]" → "First Middle Last"
    if ',' in name:
        parts = [p.strip() for p in name.split(',', 1)]
        last = parts[0]
        rest = parts[1]
        # Remove duplicate trailing last name (model often appends it again)
        rest_words = rest.split()
        if rest_words and rest_words[-1].lower() == last.lower():
            rest = ' '.join(rest_words[:-1])
        name = f"{rest} {last}".strip()
    # Title-case (handles ALL-CAPS names)
    return name.title().strip()


def _extract_scalar_from_pages(key: str, raw_page_responses: list[str]) -> str | None:
    """
    Scan all raw page responses for a scalar field value.
    Returns the first high-confidence non-null value found, or None.
    """
    for raw in raw_page_responses:
        # Match: "key": "field_name", ... "value": "scalar_value"
        m = re.search(
            rf'"key"\s*:\s*"{re.escape(key)}".*?"value"\s*:\s*"([^"]+)"',
            raw, re.DOTALL
        )
        if m:
            val = m.group(1).strip()
            if val.lower() not in _NOT_FOUND:
                return val
        # Also match plain-text list format: "1. key_name: value"
        m2 = re.search(rf'(?:^|\n)\s*\d+\.\s*{re.escape(key)}\s*:\s*(.+)', raw, re.IGNORECASE)
        if m2:
            val = m2.group(1).strip().rstrip('.,')
            if val.lower() not in _NOT_FOUND:
                return val
    return None


async def normalize_results(
    raw_page_responses: list[str],
    prompts: list[PromptDefinition],
    doc_type: str,
) -> list[PromptResult]:
    """Consolidate all raw per-page text extractions into one clean result."""
    page_summaries = [_compact_page(r, prompts) for r in raw_page_responses]

    # Merge test_results server-side — LLM format is unreliable
    merged_tests = _merge_test_results(raw_page_responses)
    print(f"[server-side test_results] {merged_tests}", flush=True)

    payload = {
        "model": MODEL,
        "prompt": _build_normalization_prompt(prompts, doc_type, page_summaries),
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": int(os.getenv("OLLAMA_NORMALIZE_CTX", "16384")),
        },
    }

    data = await asyncio.to_thread(_call_ollama, payload)
    raw = data.get("response", "")
    print(f"[ollama normalization response]\n{raw}\n", flush=True)

    items = _parse_normalization_response(raw, prompts)
    prompt_map = {p.key: p for p in prompts}

    if items is None:
        result_list = [
            PromptResult(key=p.key, question=p.question, value=None, confidence="not_found")
            for p in prompts
        ]
    else:
        result_map: dict[str, PromptResult] = {}
        for item in items:
            key = item.get("key", "")
            prompt_def = prompt_map.get(key)
            if prompt_def:
                value = item.get("value")
                if key == "patient_name":
                    value = _fix_patient_name(value)
                result_map[key] = PromptResult(
                    key=key,
                    question=prompt_def.question,
                    value=value,
                    confidence=item.get("confidence", "low"),
                )
        result_list = [
            result_map.get(p.key, PromptResult(
                key=p.key, question=p.question, value=None, confidence="not_found"
            ))
            for p in prompts
        ]

    # Override test_results with server-side merged values
    test_prompt = next((p for p in prompts if p.key == "test_results"), None)
    if test_prompt and merged_tests:
        for i, r in enumerate(result_list):
            if r.key == "test_results":
                result_list[i] = PromptResult(
                    key="test_results",
                    question=test_prompt.question,
                    value=merged_tests,
                    confidence="high",
                )
                break

    # Fill in any scalar fields the LLM left null using server-side regex scan
    SCALAR_KEYS = {"patient_name", "date_of_birth", "collected_date"}
    for i, r in enumerate(result_list):
        if r.key in SCALAR_KEYS and r.value is None:
            fallback = _extract_scalar_from_pages(r.key, raw_page_responses)
            if fallback:
                value = _fix_patient_name(fallback) if r.key == "patient_name" else fallback
                result_list[i] = PromptResult(
                    key=r.key,
                    question=r.question,
                    value=value,
                    confidence="medium",
                )

    return result_list
