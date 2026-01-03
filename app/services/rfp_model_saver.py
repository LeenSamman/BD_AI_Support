from __future__ import annotations

import json
import os
from typing import Dict

from app.services.rfp_config import RFP_MODEL_RAW_DIR, RFP_MODEL_STRUCTURED_DIR


def save_model_outputs(
    base_id: str,
    original_name: str,
    raw_result: dict,
    normalized_result: dict,
) -> Dict[str, str]:
    """Persist raw and normalized model outputs to disk."""
    os.makedirs(RFP_MODEL_RAW_DIR, exist_ok=True)
    os.makedirs(RFP_MODEL_STRUCTURED_DIR, exist_ok=True)

    raw_path = os.path.join(RFP_MODEL_RAW_DIR, f"{base_id}.json")
    structured_path = os.path.join(RFP_MODEL_STRUCTURED_DIR, f"{base_id}.json")

    raw_payload = {
        "id": base_id,
        "file": original_name,
        "result": raw_result,
    }
    structured_payload = {
        "id": base_id,
        "file": original_name,
        "result": normalized_result,
    }

    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_payload, f, ensure_ascii=False, indent=2)
    with open(structured_path, "w", encoding="utf-8") as f:
        json.dump(structured_payload, f, ensure_ascii=False, indent=2)

    return {"raw_path": raw_path, "structured_path": structured_path}
