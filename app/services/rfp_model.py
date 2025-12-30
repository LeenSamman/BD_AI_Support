import json
import ast
import re
import requests
from app.services.rfp_chunking import chunk_text

BASE_URL = "http://localhost:1234/v1/chat/completions"
MODEL_NAME = "qwen2.5-vl-7b-instruct"
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


def _parse_model_output(raw_text: str) -> dict:
    parsed = None
    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw_text, flags=re.DOTALL)
        if match:
            try:
                parsed = json.loads(match.group(0))
            except json.JSONDecodeError:
                parsed = None
        if parsed is None and (raw_text.strip().startswith("{'") or "':" in raw_text):
            try:
                parsed = ast.literal_eval(raw_text)
            except (ValueError, SyntaxError):
                parsed = None

    if not isinstance(parsed, dict):
        return {}

    return {
        key: str(parsed.get(key, "")) if parsed.get(key) is not None else ""
        for key in EXPECTED_KEYS
    }


def _call_model_for_chunk(rfp_text: str, chunk_index: int, chunk_total: int) -> dict:
    system_prompt = (
        "You are a system that outputs STRICT JSON ONLY using double quotes. "
        "Return ONLY these exact keys (no extras): summary, company_requirements, "
        "team_requirements, technical_requirements, financial_requirements, "
        "submission_requirements, deliverables_timeline, evaluation_criteria, "
        "risks_red_flags, questions_for_client, missing_information. "
        "Each value must be returned as a single STRING formatted as bullet points, with every item starting on a new line using the exact pattern '\\n- '. Example format: \"- Requirement one\\n- Requirement two\\n- Requirement three\". Do not return lists or arrays -- only a newline-separated bullet string."
        "If a section has no info, return an empty string \"\". "
        "Example: {\"summary\":\"- Brief summary\",\"company_requirements\":\"- Req 1\",\"team_requirements\":\"\"}"
    )
    user_prompt = (
        "Analyze the following RFP text and return structured JSON with these keys: "
        "summary, requirements grouped by company, team, technical, financial, "
        "submission, deliverables, evaluation, risks_red_flags, questions_for_client, "
        "missing_information.\n\n"
        f"RFP Text (chunk {chunk_index} of {chunk_total}):\n{rfp_text}"
    )

    payload = {
        "model": MODEL_NAME,
        "temperature": TEMPERATURE,
        "max_tokens": 1200,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }

    response = requests.post(BASE_URL, json=payload, timeout=180)
    if response.status_code != 200:
        error_detail = response.text
        raise RuntimeError(f"Model request failed: {response.status_code} {error_detail}")

    raw_text = response.json()["choices"][0]["message"]["content"]
    parsed = _parse_model_output(raw_text)
    if not parsed:
        raise RuntimeError("Model response parsing error")
    return parsed


def call_local_rfp_model(rfp_text: str) -> dict:
    chunks = chunk_text(rfp_text)
    print(f"RFP model: {len(chunks)} chunk(s)")
    merged = {key: "" for key in EXPECTED_KEYS}
    failures = 0
    for index, chunk in enumerate(chunks, start=1):
        try:
            result = _call_model_for_chunk(chunk, index, len(chunks))
        except Exception as exc:
            print(f"RFP model: chunk {index} failed ({exc})")
            failures += 1
            continue
        for key in EXPECTED_KEYS:
            merged[key] = _merge_bullets(merged[key], result.get(key, ""))

    if failures == len(chunks):
        return {
            "summary": "Model request failed: all chunks failed",
            "company_requirements": "",
            "team_requirements": "",
            "technical_requirements": "",
            "financial_requirements": "",
            "submission_requirements": "",
            "deliverables_timeline": "",
            "evaluation_criteria": "",
            "risks_red_flags": "",
            "questions_for_client": "",
            "missing_information": "",
        }

    if all(merged[key] == "" for key in EXPECTED_KEYS):
        merged["summary"] = "Model returned empty results"
    return merged
