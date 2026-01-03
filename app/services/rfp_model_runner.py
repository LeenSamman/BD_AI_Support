import json
import ast
import re
import requests
from app.services.rfp_chunking import chunk_text
from app.services.rfp_normalize import ensure_schema

BASE_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen2.5-vl-7b-instruct"
ALLOWED_MODELS = ["qwen2.5-vl-7b-instruct"]
TEMPERATURE = 0.3

EXPECTED_KEYS = [
    "summary",
    "company_requirements",
    "team_requirements",
    "technical_requirements",
    "financial_requirements",
    "submission_requirements",
    "deliverables_timeline",
    "evaluation_criteria",
    "risks_red_flags",
    "questions_for_client",
    "missing_information",
]


def _merge_bullets(existing: str, incoming: str) -> str:
    existing_lines = [line for line in existing.splitlines() if line.strip()]
    incoming_lines = [line for line in incoming.splitlines() if line.strip()]
    seen = set(existing_lines)
    merged = list(existing_lines)
    for line in incoming_lines:
        if line not in seen:
            merged.append(line)
            seen.add(line)
    return "\n".join(merged)


def _merge_option_a(base: dict, incoming: dict) -> dict:
    merged = ensure_schema(base)
    inc = ensure_schema(incoming)
    for key in ("rfp_title", "issuing_organization", "summary_paragraph"):
        if not merged[key] and inc[key]:
            merged[key] = inc[key]
    for section_key in ("questions_deadline", "proposal_due"):
        section = merged["rfp_quick_facts"]["deadlines"][section_key]
        inc_section = inc["rfp_quick_facts"]["deadlines"][section_key]
        for field in section:
            if not section[field] and inc_section[field]:
                section[field] = inc_section[field]
    merged["rfp_quick_facts"]["pre_bid_presentations"] = (
        merged["rfp_quick_facts"]["pre_bid_presentations"]
        + inc["rfp_quick_facts"]["pre_bid_presentations"]
    )
    for group in (
        "company",
        "team",
        "technical",
        "financial",
        "submission",
        "deliverables_timeline",
        "evaluation_criteria",
        "risks_red_flags",
    ):
        merged["requirements_checklist"][group] = (
            merged["requirements_checklist"][group] + inc["requirements_checklist"][group]
        )
    merged["questions_for_client"] = merged["questions_for_client"] + inc["questions_for_client"]
    merged["missing_information"] = merged["missing_information"] + inc["missing_information"]
    return merged


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
    if model_name in ALLOWED_MODELS:
        return model_name
    return MODEL_NAME


def _call_model_for_chunk(
    rfp_text: str,
    chunk_index: int,
    chunk_total: int,
    model_name: str,
) -> dict:
    system_prompt = (
        "You are an RFP extraction engine. Output ONLY one JSON object (double quotes). No markdown, no code fences. "
        "Return EXACT schema: {rfp_title, issuing_organization, summary_paragraph, rfp_quick_facts:{deadlines:"
        "{questions_deadline:{date,time,timezone,contact_email}, proposal_due:{date,time,timezone}}, "
        "pre_bid_presentations:[{title,date,time,timezone,location,mandatory}]}, requirements_checklist:"
        "{company:[],team:[],technical:[],financial:[],submission:[],deliverables_timeline:[],"
        "evaluation_criteria:[],risks_red_flags:[]}, questions_for_client:[], missing_information:[]}. "
        "All fields are strings. Unknown => \"\" or []. pre_bid_presentations[].mandatory must be "
        "mandatory|optional|unknown (use unknown if unclear; never empty). Checklist items MUST be "
        "{requirement,strength,why,evidence,page_hint}. risks_red_flags items MUST be "
        "{risk,strength,why,evidence,page_hint}. strength must be mandatory|preferred|informational; "
        "if requirement/risk exists, strength cannot be empty. evidence must be an exact quote of 6-20 words "
        "from the provided text, otherwise \"\". Never output {} for deadlines or any object. Never invent facts."
    )
    user_prompt = (
        "Extract ONLY from the text below. Fill the schema. Categorize requirements:\n"
        "- company: eligibility, registrations, org experience, compliance gates\n"
        "- team: key experts, CVs, required experience/certs\n"
        "- technical: scope/tasks/methodology\n"
        "- financial: pricing/payment/fees/taxes\n"
        "- submission: format, channel, deadline, language, required docs\n"
        "- deliverables_timeline: deliverables and due timing\n"
        "- evaluation_criteria: scoring weights/criteria\n"
        "- risks_red_flags: disqualification, penalties, legal/compliance red flags\n"
        "If a field is not explicitly present, leave it \"\" or [].\n"
        "TEXT:\n"
        f"<<<{rfp_text}>>>"
    )

    payload = {
        "model": model_name,
        "temperature": TEMPERATURE,
        "max_tokens": 1200,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    try:
        response = requests.post(BASE_URL, json=payload, timeout=180)
    except Exception as exc:
        print(f"RFP model: chunk {chunk_index} request failed ({exc})")
        return {}
    if response.status_code != 200:
        error_detail = response.text
        print(f"RFP model: chunk {chunk_index} failed ({response.status_code} {error_detail})")
        return {}

    raw_text = response.json()["choices"][0]["message"]["content"]
    print(f"RFP model: chunk {chunk_index} raw_response={raw_text[:2000]}")
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
    merged = ensure_schema({})
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
        normalized = ensure_schema(result)
        if normalized == ensure_schema({}):
            failures += 1
            continue
        merged = ensure_schema(_merge_option_a(merged, normalized))

    merged = ensure_schema(merged)
    meta = {
        "chunk_count": len(chunks),
        "chunk_lengths": chunk_lengths,
        "failures": failures,
    }
    counts = merged["requirements_checklist"]
    print(
        "RFP model: counts company={c} team={t} technical={te} submission={s} "
        "deliverables={d} evaluation={e} risks={r}".format(
            c=len(counts["company"]),
            t=len(counts["team"]),
            te=len(counts["technical"]),
            s=len(counts["submission"]),
            d=len(counts["deliverables_timeline"]),
            e=len(counts["evaluation_criteria"]),
            r=len(counts["risks_red_flags"]),
        )
    )
    return merged, meta


def run_rfp_model(text: str, model_name: str | None = None) -> dict:
    result, _meta = run_rfp_model_with_meta(text, context=None, model_name=model_name)
    return result
