from __future__ import annotations

from typing import Any, Dict, List, Optional


class DoclingExtractionError(RuntimeError):
    pass


def _build_converter() -> Any:
    from docling.document_converter import DocumentConverter

    try:
        from docling.datamodel.pipeline_options import PipelineOptions, PdfPipelineOptions

        pdf_options = PdfPipelineOptions()
        _enable_true(pdf_options, "do_ocr", "do_table_structure", "do_layout")
        _enable_true(pdf_options, "save_artifacts", "export_artifacts")
        _enable_nested(pdf_options, "ocr_options", "enable")
        _enable_nested(pdf_options, "table_structure_options", "do_table_structure")
        _enable_nested(pdf_options, "table_structure_options", "do_tables")
        _enable_nested(pdf_options, "layout_options", "do_layout")
        _enable_nested(pdf_options, "image_options", "extract_images")
        _enable_nested(pdf_options, "image_options", "do_image_extraction")
        _enable_nested(pdf_options, "picture_options", "extract_images")
        _enable_nested(pdf_options, "picture_options", "do_picture_extraction")

        pipeline_options = PipelineOptions()
        _enable_true(pipeline_options, "extract_tables", "do_table_structure")
        _enable_true(pipeline_options, "extract_layout", "do_layout")
        _enable_true(pipeline_options, "extract_images", "do_image_extraction")
        _enable_true(pipeline_options, "save_artifacts", "export_artifacts")
        if hasattr(pipeline_options, "pdf"):
            pipeline_options.pdf = pdf_options
        elif hasattr(pipeline_options, "pdf_pipeline_options"):
            pipeline_options.pdf_pipeline_options = pdf_options

        return DocumentConverter(pipeline_options=pipeline_options)
    except Exception:
        # Fall back to Docling defaults if option wiring changes.
        return DocumentConverter()


def _export_text(obj: Any) -> str:
    for method_name in ("export_to_markdown", "export_to_text"):
        method = getattr(obj, method_name, None)
        if callable(method):
            text = method()
            if text:
                return str(text)

    text_attr = getattr(obj, "text", None)
    if text_attr:
        return str(text_attr)

    raise RuntimeError("No text export available on Docling object")


def _extract_pages(doc: Any) -> List[Dict[str, str]]:
    pages_attr = getattr(doc, "pages", None)
    if not pages_attr:
        return []

    pages: List[Dict[str, str]] = []
    for index, page in enumerate(pages_attr, start=1):
        try:
            page_text = _export_text(page)
        except Exception:
            continue
        if page_text:
            pages.append({"page": index, "text": page_text})
    return pages


def _extract_artifacts_dir(result: Any) -> Optional[str]:
    for attr_name in ("artifacts_dir", "artifacts"):
        value = getattr(result, attr_name, None)
        if value:
            return str(value)
    return None


def _enable_true(target: Any, *attr_names: str) -> None:
    for attr_name in attr_names:
        if hasattr(target, attr_name):
            try:
                setattr(target, attr_name, True)
            except Exception:
                pass


def _enable_nested(target: Any, nested_attr: str, flag_attr: str) -> None:
    nested = getattr(target, nested_attr, None)
    if nested is None:
        return
    if hasattr(nested, flag_attr):
        try:
            setattr(nested, flag_attr, True)
        except Exception:
            pass


def extract_with_docling(file_path: str) -> Dict[str, Any]:
    try:
        converter = _build_converter()
        result = converter.convert(file_path)
        doc = getattr(result, "document", None)
        if doc is None:
            raise RuntimeError("Docling returned no document")

        payload: Dict[str, Any] = {"text": _export_text(doc), "errors": []}

        pages = _extract_pages(doc)
        if pages:
            payload["pages"] = pages

        artifacts_dir = _extract_artifacts_dir(result)
        if artifacts_dir:
            payload["artifacts_dir"] = artifacts_dir

        return payload
    except Exception as exc:
        raise DoclingExtractionError(f"Docling extraction failed: {exc}") from exc


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m app.services.docling_extract <file_path>")
        raise SystemExit(1)

    output = extract_with_docling(sys.argv[1])
    print(output.get("text", "")[:500])
