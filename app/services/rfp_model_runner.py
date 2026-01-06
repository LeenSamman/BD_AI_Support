import json
import requests
from app.services.rfp_chunking import chunk_text
from app.services.local_llm import get_chat_completions_url, get_default_model_name

CHAT_COMPLETIONS_URL = get_chat_completions_url()
DEFAULT_MODEL_NAME = get_default_model_name()
TEMPERATURE = 0.3

STRING_KEYS = [
    "Title",
    "Issuing_organization",
    "summary",
]

ARRAY_KEYS = [
    "company_requirements",
    "team_requirements",
    "technical_requirements",
    "financial_requirements",
    "submission_requirements",
    "deliverables_timeline",
    "evaluation_criteria",
    "risks_red_flags",
    "questions_for_client",
]


def _empty_result() -> dict:
    result = {key: "" for key in STRING_KEYS}
    result.update({key: [] for key in ARRAY_KEYS})
    return result


def _detect_schema(payload: dict) -> str:
    if any(key in payload for key in ("Title", "company_requirements")):
        return "new"
    return "unknown"


def _flatten_list_item(item: object) -> list[str]:
    if item is None:
        return []
    if isinstance(item, str):
        text = item.strip()
        return [text] if text else []
    if isinstance(item, (int, float, bool)):
        text = str(item).strip()
        return [text] if text else []
    if isinstance(item, list):
        cleaned: list[str] = []
        for entry in item:
            cleaned.extend(_flatten_list_item(entry))
        return cleaned
    if isinstance(item, dict):
        lowered = {str(key).strip().lower(): key for key in item.keys()}

        def _get_value(*candidates: str) -> object | None:
            for candidate in candidates:
                key = lowered.get(candidate)
                if key is not None:
                    return item.get(key)
            return None

        requirements = _get_value("requirements", "requirement_list")
        if requirements is not None:
            return _flatten_list_item(requirements)

        requirement = _get_value("requirement")
        specifications = _get_value("specifications", "specs", "details")
        if requirement is not None or specifications is not None:
            requirement_text = "; ".join(_flatten_list_item(requirement))
            specifications_text = "; ".join(_flatten_list_item(specifications))
            if requirement_text and specifications_text:
                return [f"{requirement_text}: {specifications_text}"]
            if requirement_text:
                return [requirement_text]
            return [specifications_text] if specifications_text else []

        risk = _get_value("risk")
        if risk is not None:
            return _flatten_list_item(risk)

        question = _get_value("question")
        if question is not None:
            return _flatten_list_item(question)

        parts: list[str] = []
        for key, value in item.items():
            value_parts = _flatten_list_item(value)
            if not value_parts:
                continue
            if len(value_parts) == 1:
                parts.append(f"{key}: {value_parts[0]}")
            else:
                parts.append(f"{key}: {', '.join(value_parts)}")
        return ["; ".join(parts)] if parts else []

    text = str(item).strip()
    return [text] if text else []


def _clean_list(items: object) -> list:
    if items is None:
        return []
    if not isinstance(items, list):
        items = [items]
    cleaned: list[str] = []
    for item in items:
        cleaned.extend(_flatten_list_item(item))
    return cleaned


def _coerce_new_schema(payload: dict) -> dict:
    result = _empty_result()
    for key in STRING_KEYS:
        text = payload.get(key, "")
        if text is None:
            text = ""
        result[key] = str(text).strip()
    for key in ARRAY_KEYS:
        result[key] = _clean_list(payload.get(key, []))
    return result


def _coerce_result(value: object) -> tuple[dict, str]:
    result = _empty_result()
    if not isinstance(value, dict):
        return result, "unknown"
    schema = _detect_schema(value)
    if schema == "new":
        return _coerce_new_schema(value), "new"
    return _coerce_new_schema(value), "unknown"


def _has_content(result: dict) -> bool:
    for key in STRING_KEYS:
        if result.get(key):
            return True
    for key in ARRAY_KEYS:
        if result.get(key):
            return True
    return False


def merge_chunk_results(base: dict, incoming: dict) -> dict:
    for key in ("Title", "Issuing_organization"):
        if not base.get(key) and incoming.get(key):
            base[key] = incoming[key]
    if not base.get("summary") and incoming.get("summary"):
        base["summary"] = incoming["summary"]
    for key in ARRAY_KEYS:
        base_items = base.get(key, [])
        seen = {item.strip() for item in base_items if item and item.strip()}
        for item in incoming.get(key, []):
            text = item.strip()
            if not text or text in seen:
                continue
            base_items.append(text)
            seen.add(text)
        base[key] = base_items
    return base


def extract_json_object(raw_text: str, chunk_index: int) -> dict:
    if not raw_text:
        return {}
    cleaned = raw_text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    elif cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    cleaned = cleaned.strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    snippet = cleaned[start:end + 1]
    try:
        parsed = json.loads(snippet)
    except json.JSONDecodeError as exc:
        print(f"RFP model: chunk {chunk_index} json parse failed ({exc})")
        print(f"RFP model: chunk {chunk_index} json snippet={snippet[:500]}")
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _resolve_model_name(model_name: str | None) -> str:
    if model_name and model_name.strip():
        return model_name.strip()
    return DEFAULT_MODEL_NAME


def _call_model_for_chunk(
    rfp_text: str,
    chunk_index: int,
    chunk_total: int,
    model_name: str,
) -> dict:
    """
    Calls the local LLM for ONE chunk of text and returns parsed JSON (dict).

    Notes:
    - We only do prompt engineering here.
    - No normalization / merging here.
    - We enforce strict JSON and extract via extract_json_object().
    """

    system_prompt = (
    "You are an information extraction engine for RFP/ToR documents.\n"
    "Return STRICT JSON ONLY using double quotes.\n"
    "\n"
    "ABSOLUTE OUTPUT CONSTRAINTS (HARD):\n"
    "A) Output MUST start with { and end with }.\n"
    "B) NO markdown, NO code fences, NO commentary, NO trailing text.\n"
    "C) Return EXACTLY the schema below: same keys, same nesting, same types.\n"
    "D) NEVER add extra keys anywhere.\n"
    "E) Use \"\" for missing strings and [] for missing arrays.\n"
    "\n"
    "SCHEMA (copy exactly):\n"
    "{\n"
    "  \"Title\": \"\",\n"
    "  \"Issuing_organization\": \"\",\n"
    "  \"summary\": \"\",\n"
    "  \"company_requirements\": [],\n"
    "  \"team_requirements\": [],\n"
    "  \"technical_requirements\": [],\n"
    "  \"financial_requirements\": [],\n"
    "  \"submission_requirements\": [],\n"
    "  \"deliverables_timeline\": [],\n"
    "  \"evaluation_criteria\": [],\n"
    "  \"risks_red_flags\": [],\n"
    "  \"questions_for_client\": []\n"
    "}\n"
    "\n"
    "EXTRACTION RULES:\n"
    "1) Extract ONLY facts explicitly present in TEXT. Do NOT invent.\n"
    "2) Arrays must contain short, atomic items (one requirement per item).\n"
    "3) Light paraphrase is allowed to shorten an item, but it must stay faithful to TEXT.\n"
    "4) If Title/Issuing_organization/summary are not clearly present in THIS chunk, keep them \"\".\n"
    "5) questions_for_client: include ONLY explicit questions asked by the RFP issuer (e.g., \"Questions must be sent to...\" is NOT a question).\n"
    "6) Do not include duplicates within the same array.\n"
    )


    user_prompt = (
        f"You are processing CHUNK {chunk_index}/{chunk_total}.\n"
        "Extract information ONLY from the TEXT below.\n"
        "\n"
        "IMPORTANT:\n"
        "- If the TEXT contains a header section named 'Context:' followed by '----', ignore everything before '----'.\n"
        "- Do not infer missing details.\n"
        "\n"
        "TEXT:\n"
        f"{rfp_text}"
    )


    payload = {
        "model": model_name,
        "temperature": 0.1,
        "max_tokens": 1200,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        response = requests.post(CHAT_COMPLETIONS_URL, json=payload, timeout=180)
    except Exception as exc:
        print(f"RFP model: chunk {chunk_index} request failed ({exc})")
        return {}

    if response.status_code != 200:
        error_detail = response.text
        print(f"RFP model: chunk {chunk_index} failed ({response.status_code} {error_detail})")
        return {}

    raw_text = response.json()["choices"][0]["message"]["content"]

    print("\n" + "=" * 30 + f" RAW OUTPUT CHUNK {chunk_index} " + "=" * 30)
    print(raw_text)
    print("=" * 80 + "\n")

    parsed = extract_json_object(raw_text, chunk_index)
    return parsed



def run_rfp_model_with_meta(
    text: str,
    context: dict | None = None,
    model_name: str | None = None,
) -> tuple[dict, dict]:
    chunks = chunk_text(text)
    selected_model = _resolve_model_name(model_name)
    print(f"RFP model: selected_model={selected_model}")
    print(f"RFP model: {len(chunks)} chunk(s)")
    merged = _empty_result()
    failures = 0
    chunk_lengths = [len(chunk) for chunk in chunks]
    for index, chunk in enumerate(chunks, start=1):
        chunk_body = chunk
        if context:
            file_name = context.get("file", "")
            mode = context.get("mode", "")
            chunk_body = (
                "Context:\n"
                f"- File: {file_name}\n"
                f"- Mode: {mode}\n"
                "----\n"
                f"{chunk}"
            )
        result = _call_model_for_chunk(chunk_body, index, len(chunks), selected_model)
        normalized, schema = _coerce_result(result)
        print(f"RFP model: chunk {index} schema={schema.upper()}")
        if not _has_content(normalized):
            failures += 1
            continue
        merged = merge_chunk_results(merged, normalized)

    meta = {
        "chunk_count": len(chunks),
        "chunk_lengths": chunk_lengths,
        "failures": failures,
    }
    counts = {key: len(merged[key]) for key in ARRAY_KEYS}
    print(
        "RFP model: counts company={c} team={t} technical={te} submission={s} "
        "deliverables={d} evaluation={e} risks={r} questions={q}".format(
            c=counts["company_requirements"],
            t=counts["team_requirements"],
            te=counts["technical_requirements"],
            s=counts["submission_requirements"],
            d=counts["deliverables_timeline"],
            e=counts["evaluation_criteria"],
            r=counts["risks_red_flags"],
            q=counts["questions_for_client"],
        )
    )
    return merged, meta


def run_rfp_model(text: str, model_name: str | None = None) -> dict:
    result, _meta = run_rfp_model_with_meta(text, context=None, model_name=model_name)
    return result






# Function to test the module independently (in terminal)
def debug_print_raw_llm_per_chunk(text: str, model_name: str | None = None) -> None:
    """
    Prints raw model output for each chunk.
    NO normalization. NO merging. Just raw output.
    """
    chunks = chunk_text(text)
    selected_model = _resolve_model_name(model_name)

    print(f"[DEBUG] model={selected_model}")
    print(f"[DEBUG] chunks={len(chunks)}")
    print("=" * 80)

    for i, chunk in enumerate(chunks, start=1):
        print(f"\n[CHUNK {i}/{len(chunks)}] len={len(chunk)}")
        print("-" * 80)
        print(chunk[:800])  # just show first 800 chars of the chunk
        print("\n[RAW MODEL OUTPUT]")
        print("-" * 80)

        # reuse your existing call
        result = _call_model_for_chunk(chunk, i, len(chunks), selected_model)

        # IMPORTANT: result is already "parsed JSON dict" in your current code.
        # So to see RAW output, we must print raw text before parsing.
        # Therefore: temporarily add raw printing inside _call_model_for_chunk (Step 2 below).

        print(result)
        print("=" * 80)
