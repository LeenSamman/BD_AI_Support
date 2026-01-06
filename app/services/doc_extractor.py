from __future__ import annotations

from typing import Dict
import gc


def extract_rfp(file_path: str) -> Dict[str, object]:
    """Extract RFP text using Docling and return a minimal payload."""
    from app.services.mem_debug import log_mem
    from app.services.perf_debug import now_ms, elapsed_ms, log_perf
    from docling.document_converter import DocumentConverter

    start_ms = now_ms()
    log_mem("extract_rfp:start")
    log_perf("extract_rfp:start", {"file": file_path, "elapsed_ms": 0.0})

    log_mem("extract_rfp:before_document_converter")
    log_perf("extract_rfp:before_document_converter", {"elapsed_ms": elapsed_ms(start_ms)})
    converter = DocumentConverter()
    log_mem("extract_rfp:after_document_converter")
    log_perf("extract_rfp:after_document_converter", {"elapsed_ms": elapsed_ms(start_ms)})

    log_mem("extract_rfp:before_convert")
    log_perf("extract_rfp:before_convert", {"elapsed_ms": elapsed_ms(start_ms)})
    result = converter.convert(file_path)
    log_mem("extract_rfp:after_convert")
    log_perf("extract_rfp:after_convert", {"elapsed_ms": elapsed_ms(start_ms)})
    doc = getattr(result, "document", None)
    if doc is None:
        raise RuntimeError("Docling returned no document")

    text = ""
    log_mem("extract_rfp:before_export_to_markdown")
    log_perf("extract_rfp:before_export_to_markdown", {"elapsed_ms": elapsed_ms(start_ms)})
    export = getattr(doc, "export_to_markdown", None)
    if callable(export):
        text = export() or ""
    else:
        text_attr = getattr(doc, "text", "")
        text = text_attr or ""
    log_mem("extract_rfp:after_export_to_markdown")
    log_perf("extract_rfp:after_export_to_markdown", {"elapsed_ms": elapsed_ms(start_ms)})

    # Diagnostic only: check if RSS returns after a forced collection.
    gc.collect()
    log_mem("extract_rfp:after_gc_collect")

    if not text:
        raise RuntimeError("Docling produced empty text")

    log_mem("extract_rfp:end")
    log_perf("extract_rfp:end", {"elapsed_ms": elapsed_ms(start_ms)})

    return {
        "text": str(text),
        "text_length": len(text),
        "source_file": file_path,
        "engine": "docling",
        "format": "markdown",
    }
