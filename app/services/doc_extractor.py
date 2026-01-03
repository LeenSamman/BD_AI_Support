from __future__ import annotations

from typing import Dict


def extract_rfp(file_path: str) -> Dict[str, object]:
    """Extract RFP text using Docling and return a minimal payload."""
    from docling.document_converter import DocumentConverter

    converter = DocumentConverter()
    result = converter.convert(file_path)
    doc = getattr(result, "document", None)
    if doc is None:
        raise RuntimeError("Docling returned no document")

    text = ""
    export = getattr(doc, "export_to_markdown", None)
    if callable(export):
        text = export() or ""
    else:
        text_attr = getattr(doc, "text", "")
        text = text_attr or ""

    if not text:
        raise RuntimeError("Docling produced empty text")

    return {
        "text": str(text),
        "text_length": len(text),
        "source_file": file_path,
        "engine": "docling",
        "format": "markdown",
    }
