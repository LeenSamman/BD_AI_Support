"""
Central configuration for the RFP pipeline.

Defines folder paths and tuning constants only. No side effects.
"""

RFP_ORIGINAL_DIR = "uploads/rfp_original_uploaded"
RFP_EXTRACTED_MD_DIR = "uploads/rfp_extracted_md"
RFP_EXTRACTED_TXT_DIR = "uploads/rfp_extracted_txt"
RFP_MANIFEST_DIR = "uploads/rfp_docling_manifest"
RFP_MODEL_RAW_DIR = "uploads/rfp_model_raw_response"
RFP_MODEL_STRUCTURED_DIR = "uploads/rfp_model_structured"
RFP_CONVERTED_PDF_DIR = "uploads/rfp_converted_pdf"

MIN_TEXT_CHARS = 800
IMAGE_PLACEHOLDER_TOKEN = "<!-- image -->"
MAX_IMAGE_PLACEHOLDER_RATIO = 0.20

CHUNK_MAX_CHARS = 12000
CHUNK_OVERLAP_CHARS = 2000
