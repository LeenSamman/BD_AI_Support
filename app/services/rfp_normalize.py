from __future__ import annotations

from typing import Dict, List

EMPTY_STRINGS = {"", "none", "n/a", "na"}
STRENGTH_VALUES = {"mandatory", "preferred", "informational"}
MANDATORY_VALUES = {"mandatory", "optional", "unknown"}


def _clean_str(value: object) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u00A0", " ").strip()
    if text.lower() in EMPTY_STRINGS:
        return ""
    return text


def _single_paragraph(text: str) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.replace("\r", " ").replace("\n", " ").split())
    if cleaned.startswith("- "):
        cleaned = cleaned[2:].lstrip()
    return cleaned


def _valid_strength(value: str) -> str:
    return value if value in STRENGTH_VALUES else ""


def _valid_mandatory(value: str) -> str:
    return value if value in MANDATORY_VALUES else "unknown"


def _evidence_ok(value: str) -> bool:
    if not value:
        return True
    word_count = len(value.split())
    return 6 <= word_count <= 20


def _dedupe(items: List[dict], key_fn) -> List[dict]:
    seen = set()
    result = []
    for item in items:
        key = key_fn(item)
        if not key or key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _drop_empty_items(items: List[dict]) -> List[dict]:
    return [item for item in items if any(v != "" for v in item.values())]


def _normalize_checklist(items: object, use_risk_key: bool = False) -> List[dict]:
    if not isinstance(items, list):
        return []
    key_field = "risk" if use_risk_key else "requirement"
    normalized: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized_item = {
            key_field: _clean_str(item.get(key_field, "")),
            "strength": _clean_str(item.get("strength", "")),
            "why": _clean_str(item.get("why", "")),
            "evidence": _clean_str(item.get("evidence", "")),
            "page_hint": _clean_str(item.get("page_hint", "")),
        }
        normalized_item["strength"] = _valid_strength(normalized_item["strength"])
        if not normalized_item["strength"] and normalized_item[key_field]:
            normalized_item["strength"] = "informational"
        if not _evidence_ok(normalized_item["evidence"]):
            normalized_item["evidence"] = ""
        normalized.append(normalized_item)
    normalized = _drop_empty_items(normalized)
    return _dedupe(normalized, lambda x: f"{x.get(key_field,'').lower()}|{x.get('strength','')}")


def _normalize_pre_bid(items: object) -> List[dict]:
    if not isinstance(items, list):
        return []
    normalized: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized_item = {
            "title": _clean_str(item.get("title", "")),
            "date": _clean_str(item.get("date", "")),
            "time": _clean_str(item.get("time", "")),
            "timezone": _clean_str(item.get("timezone", "")),
            "location": _clean_str(item.get("location", "")),
            "mandatory": _valid_mandatory(_clean_str(item.get("mandatory", ""))),
        }
        normalized.append(normalized_item)
    normalized = _drop_empty_items(normalized)
    return _dedupe(
        normalized,
        lambda x: "|".join(
            [
                x.get("title", "").lower(),
                x.get("date", "").lower(),
                x.get("time", "").lower(),
                x.get("location", "").lower(),
            ]
        ),
    )


def _normalize_questions(items: object) -> List[dict]:
    if not isinstance(items, list):
        return []
    normalized: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized_item = {
            "question": _clean_str(item.get("question", "")),
            "why_it_matters": _clean_str(item.get("why_it_matters", "")),
        }
        normalized.append(normalized_item)
    normalized = _drop_empty_items(normalized)
    return _dedupe(normalized, lambda x: x.get("question", "").lower())


def _normalize_missing(items: object) -> List[dict]:
    if not isinstance(items, list):
        return []
    normalized: List[dict] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        normalized_item = {
            "item": _clean_str(item.get("item", "")),
            "why_missing": _clean_str(item.get("why_missing", "")),
        }
        normalized.append(normalized_item)
    normalized = _drop_empty_items(normalized)
    return _dedupe(normalized, lambda x: x.get("item", "").lower())


def ensure_schema(data: dict) -> Dict[str, object]:
    source = data if isinstance(data, dict) else {}
    summary = _single_paragraph(_clean_str(source.get("summary_paragraph", "")))
    rfp_quick_facts = source.get("rfp_quick_facts", {}) if isinstance(source.get("rfp_quick_facts", {}), dict) else {}
    deadlines = rfp_quick_facts.get("deadlines", {}) if isinstance(rfp_quick_facts.get("deadlines", {}), dict) else {}
    questions_deadline = deadlines.get("questions_deadline", {}) if isinstance(deadlines.get("questions_deadline", {}), dict) else {}
    proposal_due = deadlines.get("proposal_due", {}) if isinstance(deadlines.get("proposal_due", {}), dict) else {}

    requirements = source.get("requirements_checklist", {}) if isinstance(source.get("requirements_checklist", {}), dict) else {}

    normalized = {
        "rfp_title": _clean_str(source.get("rfp_title", "")),
        "issuing_organization": _clean_str(source.get("issuing_organization", "")),
        "summary_paragraph": summary,
        "rfp_quick_facts": {
            "deadlines": {
                "questions_deadline": {
                    "date": _clean_str(questions_deadline.get("date", "")),
                    "time": _clean_str(questions_deadline.get("time", "")),
                    "timezone": _clean_str(questions_deadline.get("timezone", "")),
                    "contact_email": _clean_str(questions_deadline.get("contact_email", "")),
                },
                "proposal_due": {
                    "date": _clean_str(proposal_due.get("date", "")),
                    "time": _clean_str(proposal_due.get("time", "")),
                    "timezone": _clean_str(proposal_due.get("timezone", "")),
                },
            },
            "pre_bid_presentations": _normalize_pre_bid(rfp_quick_facts.get("pre_bid_presentations", [])),
        },
        "requirements_checklist": {
            "company": _normalize_checklist(requirements.get("company", [])),
            "team": _normalize_checklist(requirements.get("team", [])),
            "technical": _normalize_checklist(requirements.get("technical", [])),
            "financial": _normalize_checklist(requirements.get("financial", [])),
            "submission": _normalize_checklist(requirements.get("submission", [])),
            "deliverables_timeline": _normalize_checklist(requirements.get("deliverables_timeline", [])),
            "evaluation_criteria": _normalize_checklist(requirements.get("evaluation_criteria", [])),
            "risks_red_flags": _normalize_checklist(requirements.get("risks_red_flags", []), use_risk_key=True),
        },
        "questions_for_client": _normalize_questions(source.get("questions_for_client", [])),
        "missing_information": _normalize_missing(source.get("missing_information", [])),
    }
    return normalized


def normalize_rfp_result(data: dict) -> Dict[str, object]:
    return ensure_schema(data)
