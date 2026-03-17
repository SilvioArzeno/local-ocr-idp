import asyncio
import requests
import json
import re
import os
from models.schemas import PromptDefinition, PromptResult

OLLAMA_URL  = os.getenv("OLLAMA_URL", "http://localhost:11434")
MODEL       = os.getenv("OLLAMA_MODEL", "qwen2.5:7b")      # structured field extraction
OCR_MODEL   = os.getenv("OLLAMA_OCR_MODEL", "gemma3:4b")    # vision OCR pass only
TIMEOUT     = int(os.getenv("OLLAMA_TIMEOUT", "600"))

# Standard lab acronyms we extract server-side from all pages
STANDARD_ACRONYMS = frozenset({
    "WBC", "RBC", "Platelets", "HGB", "NA", "Creat", "K", "AST", "ALT",
    "PT", "PTT", "INR", "Glucose", "HbA1C", "T3", "T4", "TSH", "HIV",
    "CD4", "BHCG", "HepC",
})
_NOT_FOUND = frozenset({
    "not_found", "not found", "not provided", "n/a", "none", "", "null", "not available",
})

# Physiologically plausible ranges — values outside these are order codes or unit errors.
# Platelets auto-converted from cells/µL (>1500) to x10³/µL.
_LAB_RANGES: dict[str, tuple[float, float]] = {
    "WBC":      (0.1,   100),
    "RBC":      (0.5,   10),
    "Platelets":(10,    1500),
    "HGB":      (2,     25),
    "NA":       (100,   180),
    "Creat":    (0.1,   20),
    "K":        (1.0,   9.0),
    "AST":      (1,     5000),
    "ALT":      (1,     5000),
    "PT":       (5,     100),
    "PTT":      (5,     200),
    "INR":      (0.5,   15),
    "Glucose":  (20,    800),
    "HbA1C":    (3,     20),
    "T3":       (0.1,   20),
    "T4":       (0.1,   30),
    "TSH":      (0.001, 100),
    "CD4":      (0,     2000),
    "BHCG":     (0,     1_000_000),
}

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
    "ptt": "PTT", "partial thromboplastin time": "PTT", "aptt": "PTT", "a ptt": "PTT",
    "inr": "INR",
    "glucose": "Glucose",
    "hba1c": "HbA1C", "hemoglobin a1c": "HbA1C", "haemoglobin a1c": "HbA1C",
    "t3": "T3", "t4": "T4", "tsh": "TSH",
    "hiv": "HIV",
    "cd4": "CD4",
    "bhcg": "BHCG", "hcg": "BHCG", "beta hcg": "BHCG",
    "hepc": "HepC", "hep c": "HepC", "hepatitis c": "HepC",
}


def _merge_lab_entry(lab_key: str, lab_val, merged: dict) -> None:
    """Add a single lab key/value pair to merged after normalisation and validation."""
    if lab_val is None:
        return
    if str(lab_val).strip().lower() in _NOT_FOUND:
        return
    if not _is_numeric(lab_val):
        return
    num = _coerce_numeric(lab_val)
    if num is None:
        return
    canon = _NAME_TO_ACRONYM.get(lab_key.lower().strip(), lab_key)
    validated = _validate_lab(canon, num)
    if validated is not None:
        merged[canon] = validated
    elif canon not in _LAB_RANGES:
        merged[canon] = num


def _validate_lab(acronym: str, num: float) -> float | None:
    """
    Return the (possibly unit-corrected) value if physiologically plausible, else None.
    Platelets reported as cells/µL (e.g. 280000) are converted to x10³/µL (280).
    """
    if acronym == "Platelets" and num > 1500:
        num = round(num / 1000, 1)
    r = _LAB_RANGES.get(acronym)
    if r is not None and not (r[0] <= num <= r[1]):
        return None   # outside plausible range — likely an order code or wrong units
    return num


def _coerce_numeric(val) -> float | None:
    """Parse numeric value, stripping lab flags like 'H', 'L', '*' (e.g. '5.5 H' → 5.5)."""
    try:
        s = str(val).strip().lstrip('<>')  # handle <0.01, >1000
        s = s.split()[0]                  # "5.5 H" → "5.5"
        s = re.sub(r'[^0-9.\-]', '', s)  # strip stray chars
        return float(s) if s else None
    except (ValueError, TypeError):
        return None


def _is_numeric(val) -> bool:
    if val is None:
        return False
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return True
    return _coerce_numeric(val) is not None


def _extract_balanced_array(text: str) -> str | None:
    """
    Extract the first balanced [...] JSON array from text.
    Uses bracket counting so it isn't fooled by trailing ] outside the array
    (which causes greedy regex to capture invalid content like `]\\n}\\n]`).
    """
    start = text.find('[')
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i, ch in enumerate(text[start:], start):
        if escape_next:
            escape_next = False
            continue
        if ch == '\\' and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return None


def _deloop_ocr(text: str) -> str:
    """
    Truncate OCR output at the point a hallucination loop is detected.
    A loop is flagged when the same 20-char line stem (min 4 chars) repeats more than 3 times.
    Short stems like '%', 'g/dL', '0.3' repeat naturally in lab tables and are ignored.
    """
    lines = text.split('\n')
    stem_counts: dict[str, int] = {}
    result = []
    for line in lines:
        stem = line.strip()[:20]
        if len(stem) >= 4:
            stem_counts[stem] = stem_counts.get(stem, 0) + 1
            if stem_counts[stem] > 3:
                break
        result.append(line)
    return '\n'.join(result)


def _normalize_date(val: str) -> str:
    """Convert any recognised date format to MM/DD/YYYY."""
    t = _parse_date_tuple(val.strip())
    if t is None:
        return val
    year, month, day = t
    return f"{month:02d}/{day:02d}/{year}"


def _build_ocr_prompt(doc_type: str) -> str:
    return "Transcribe all text visible in this image exactly as written. Output only the transcribed text."


def _build_text_extraction_prompt(
    prompts: list[PromptDefinition],
    doc_type: str,
    transcribed_text: str,
) -> str:
    definitions = "\n".join([
        f"{i+1}. key=\"{p.key}\" | type={p.type} | required={p.required} | question: {p.question}"
        for i, p in enumerate(prompts)
    ])
    return f"""Extract structured data from this {doc_type} transcription.

DOCUMENT TEXT:
{transcribed_text}

Extract the following fields using ONLY the text above:
{definitions}

Return a JSON array — one object per field, in the same order.
Each object must have:
  "key"        -> exact key from the list above
  "value"      -> extracted value, or null if not in the text
  "confidence" -> "high", "medium", "low", or "not_found"

Rules:
- Dates -> MM/DD/YYYY
- Numbers -> numeric value only (no units, no flags like H/L/*)
- Arrays -> actual JSON arrays
- null + "not_found" when the text does not contain the answer
- Return ONLY the raw JSON array. No markdown fences. No commentary.
- For lab test_results: extract only PATIENT RESULT values. A range like "4.0-11.0" or
  "150-400" or "180,000-400,000" is a REFERENCE RANGE — set that test to null, not the range number.
  Only set a value if there is a single numeric patient result, not a range.

[
  {{"key": "example_key", "value": "extracted value", "confidence": "high"}},
  ...
]"""




def _try_add(merged: dict, acronym: str, raw_val) -> None:
    """Validate and add a lab value. Uses last-valid-found so later pages overwrite earlier ones."""
    if not _is_numeric(raw_val):
        return
    num = _coerce_numeric(raw_val)
    if num is None:
        return
    validated = _validate_lab(acronym, num)
    if validated is not None:
        merged[acronym] = validated


def _parse_date_tuple(date_str: str) -> tuple | None:
    """
    Parse a date string into (year, month, day) for comparison.
    Handles: MM/DD/YYYY, YYYY-MM-DD, YYYY/MM/DD. Rejects bare years (too ambiguous).
    """
    s = date_str.strip()
    try:
        if '/' in s:
            parts = s.split('/')
            if len(parts) == 3:
                a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
                # MM/DD/YYYY
                if 1900 <= c <= 2100 and 1 <= a <= 12 and 1 <= b <= 31:
                    return (c, a, b)
                # YYYY/MM/DD
                if 1900 <= a <= 2100 and 1 <= b <= 12 and 1 <= c <= 31:
                    return (a, b, c)
        elif '-' in s:
            parts = s.split('-')
            if len(parts) == 3:
                a, b, c = int(parts[0]), int(parts[1]), int(parts[2])
                # YYYY-MM-DD
                if 1900 <= a <= 2100 and 1 <= b <= 12 and 1 <= c <= 31:
                    return (a, b, c)
    except (ValueError, IndexError):
        pass
    return None


def _get_page_date(raw: str) -> tuple | None:
    """Extract collected_date from a page extraction JSON and return as (year, month, day)."""
    m = re.search(r'"key"\s*:\s*"collected_date".*?"value"\s*:\s*"([^"]+)"', raw, re.DOTALL)
    if m:
        val = m.group(1).strip()
        if val.lower() not in _NOT_FOUND:
            return _parse_date_tuple(val)
    return None


def _merge_from_raw(raw: str, merged: dict) -> None:
    """Parse one raw page extraction and merge values into merged dict."""
    cleaned = re.sub(r"```json|```", "", raw).strip()
    fixed = re.sub(r'("key"\s*:\s*"[^"]+"\s*,\s*)(\[)', r'\1"value": \2', cleaned)

    segment = _extract_balanced_array(fixed)
    if segment:
        try:
            data = json.loads(segment)
            if isinstance(data, list):
                for item in data:
                    if not isinstance(item, dict):
                        continue
                    # Verbose CBC: {"Test": "WBC", "Current Result and Flag": "5.5"}
                    if "Test" in item and "Current Result and Flag" in item:
                        test_name = str(item["Test"]).split("^")[0].strip()
                        test_name_up = test_name.upper()
                        test_name_lo = test_name.lower()
                        acronym = None
                        for std in STANDARD_ACRONYMS:
                            if std.upper() == test_name_up:
                                acronym = std
                                break
                        if not acronym:
                            acronym = _NAME_TO_ACRONYM.get(test_name_lo)
                        if acronym:
                            _try_add(merged, acronym, item["Current Result and Flag"])
                    elif item.get("key") == "test_results":
                        test_val = item.get("value")
                        if isinstance(test_val, dict):
                            # {"WBC": 3.77, "AST": 17, ...}
                            for k, v in test_val.items():
                                if k not in ("confidence", "units", "flag"):
                                    _merge_lab_entry(k, v, merged)
                        elif isinstance(test_val, list):
                            for entry in test_val:
                                if not isinstance(entry, dict):
                                    continue
                                if "test" in entry and "result" in entry:
                                    # {"test": "AST (SGOT)", "result": 17, "units": "U/L"}
                                    _merge_lab_entry(str(entry["test"]), entry["result"], merged)
                                else:
                                    # {"WBC": 3.77, "confidence": "medium"}
                                    for k, v in entry.items():
                                        if k not in ("confidence", "units", "flag"):
                                            _merge_lab_entry(k, v, merged)
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
                        if acronym:
                            _try_add(merged, acronym, item.get("value"))
                    else:
                        # Direct: {"WBC": 5.5} or {"NA": "20.3", "confidence": "high"}
                        for key, val in item.items():
                            if key in ("confidence", "units", "flag"):
                                continue
                            if key in STANDARD_ACRONYMS:
                                str_val = str(val).strip().lower() if val is not None else ""
                                if str_val not in _NOT_FOUND:
                                    _try_add(merged, key, val)
        except (json.JSONDecodeError, ValueError):
            pass

    # Regex scan for any acronyms missed by JSON parsing
    for acronym in STANDARD_ACRONYMS:
        m = re.search(rf'"{re.escape(acronym)}"\s*:\s*"?(-?\d+\.?\d*)"?', raw)
        if m:
            _try_add(merged, acronym, m.group(1))


def _merge_test_results(raw_page_responses: list[str]) -> dict:
    """
    Merge numeric lab values from all page extractions.

    Strategy: date-aware grouping.
    1. Parse the collected_date from each page's extraction.
    2. Find the most recent date across all pages.
    3. Merge values from pages with that date first (these are the target results).
    4. Fill in any still-missing values from undated pages.
    5. Pages with an older date are skipped — they contain stale lab values.

    Values outside physiological ranges are rejected by _validate_lab.
    """
    # Phase 1: bucket pages by date
    dated: dict[tuple, list[str]] = {}   # date_tuple → list of raws
    undated: list[str] = []

    for raw in raw_page_responses:
        dt = _get_page_date(raw)
        if dt is not None:
            dated.setdefault(dt, []).append(raw)
        else:
            undated.append(raw)

    # Phase 2: determine processing order — most recent date first, then undated
    if dated:
        most_recent = max(dated.keys())
        ordered_groups = [dated[most_recent]] + [v for k, v in dated.items() if k != most_recent]
        print(f"[date-aware merge] most_recent={most_recent}, "
              f"dated_groups={sorted(dated.keys(), reverse=True)}, undated={len(undated)}", flush=True)
    else:
        ordered_groups = []
        print("[date-aware merge] no dated pages found — using all pages", flush=True)

    # Undated pages go last (supplemental)
    all_ordered: list[str] = []
    for group in ordered_groups:
        all_ordered.extend(group)
    all_ordered.extend(undated)

    # If nothing has dates, fall back to original list
    if not all_ordered:
        all_ordered = raw_page_responses

    # Phase 3: merge — iterate in date-priority order; first-valid-found wins per acronym
    # (most recent date's pages come first, so their values are set first and not overwritten)
    merged: dict = {}
    for raw in all_ordered:
        # Only add an acronym if not already set (first-valid-found for most recent date wins)
        temp: dict = {}
        _merge_from_raw(raw, temp)
        for k, v in temp.items():
            if k not in merged:
                merged[k] = v

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
    # Fix missing "value": before inline array
    cleaned = re.sub(r'("key"\s*:\s*"[^"]+"\s*,\s*)(\[)', r'\1"value": \2', cleaned)
    segment = _extract_balanced_array(cleaned)
    if segment:
        try:
            return json.loads(segment)
        except json.JSONDecodeError:
            pass
    return None


async def ocr_page(image_b64: str, doc_type: str) -> str:
    """Pass 1 — vision model transcribes the page image to text."""
    payload = {
        "model": OCR_MODEL,
        "prompt": _build_ocr_prompt(doc_type),
        "images": [image_b64],
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": int(os.getenv("OLLAMA_CTX", "4096")),
            "num_predict": int(os.getenv("OLLAMA_OCR_MAX_TOKENS", "2048")),
        },
    }
    data = await asyncio.to_thread(_call_ollama, payload)
    transcribed = _deloop_ocr(data.get("response", ""))
    print(f"[ollama OCR]\n{transcribed}\n", flush=True)
    return transcribed


async def extract_from_transcription(
    transcribed: str,
    prompts: list[PromptDefinition],
    doc_type: str,
) -> str:
    """Pass 2 — text model extracts structured fields from transcribed text."""
    payload = {
        "model": MODEL,
        "prompt": _build_text_extraction_prompt(prompts, doc_type, transcribed),
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_ctx": int(os.getenv("OLLAMA_EXTRACT_CTX", "8192")),
        },
    }
    data = await asyncio.to_thread(_call_ollama, payload)
    raw = data.get("response", "")
    print(f"[ollama extraction]\n{raw}\n", flush=True)
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
    candidates = []
    for page_num, raw in enumerate(raw_page_responses):
        # Match: "key": "field_name", ... "value": "scalar_value"
        m = re.search(
            rf'"key"\s*:\s*"{re.escape(key)}".*?"value"\s*:\s*"([^"]+)"',
            raw, re.DOTALL
        )
        if m:
            val = m.group(1).strip()
            if val.lower() not in _NOT_FOUND:
                candidates.append((page_num, val))
                continue
        # Also match plain-text list format: "1. key_name: value"
        m2 = re.search(rf'(?:^|\n)\s*\d+\.\s*{re.escape(key)}\s*:\s*(.+)', raw, re.IGNORECASE)
        if m2:
            val = m2.group(1).strip().rstrip('.,')
            if val.lower() not in _NOT_FOUND:
                candidates.append((page_num, val))

    print(f"[scalar extract] {key}: candidates={candidates}", flush=True)
    if not candidates:
        return None
    return candidates[0][1]


async def normalize_results(
    raw_page_responses: list[str],
    prompts: list[PromptDefinition],
    doc_type: str,
) -> list[PromptResult]:
    """Consolidate per-page extractions using server-side logic only (no LLM call)."""
    merged_tests = _merge_test_results(raw_page_responses)
    print(f"[server-side test_results] {merged_tests}", flush=True)

    result_list = []
    for p in prompts:
        if p.key == "test_results":
            result_list.append(PromptResult(
                key="test_results",
                question=p.question,
                value=merged_tests if merged_tests else None,
                confidence="high" if merged_tests else "not_found",
            ))
        else:
            val = _extract_scalar_from_pages(p.key, raw_page_responses)
            if val and p.key == "patient_name":
                val = _fix_patient_name(val)
            elif val and p.type == "date":
                val = _normalize_date(val)
            result_list.append(PromptResult(
                key=p.key,
                question=p.question,
                value=val,
                confidence="medium" if val else "not_found",
            ))

    return result_list
