from __future__ import annotations

import os
from typing import Dict, Optional

from app.services.doc_extractor import extract_rfp
from app.services.rfp_config import RFP_CONVERTED_PDF_DIR
from app.services.rfp_pdf_convert import convert_to_pdf
from app.services.rfp_quality_gate import should_fallback


def run_extraction_pipeline(source_path: str, ext: str, base_id: str) -> Dict[str, object]:
    """Run fast-path extraction with optional PDF fallback for office docs."""
    extraction = extract_rfp(source_path)
    fallback_needed, metrics = should_fallback(extraction.get("text", ""))

    fallback_used = False
    fallback_pdf_path: Optional[str] = None
    mode = "fast_path"

    if fallback_needed and ext.lower() in {"doc", "docx", "ppt", "pptx"}:
        os.makedirs(RFP_CONVERTED_PDF_DIR, exist_ok=True)
        fallback_pdf_path = convert_to_pdf(source_path, RFP_CONVERTED_PDF_DIR)
        extraction = extract_rfp(fallback_pdf_path)
        fallback_used = True
        mode = "fallback_pdf"

    return {
        "mode": mode,
        "extraction": extraction,
        "quality_gate": metrics,
        "fallback_used": fallback_used,
        "fallback_pdf_path": fallback_pdf_path,
    }
