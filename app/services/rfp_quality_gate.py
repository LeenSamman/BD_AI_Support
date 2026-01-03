from __future__ import annotations

from typing import Dict, Tuple

from app.services.rfp_config import (
    IMAGE_PLACEHOLDER_TOKEN,
    MAX_IMAGE_PLACEHOLDER_RATIO,
    MIN_TEXT_CHARS,
)


def compute_metrics(markdown_text: str) -> Dict[str, float]:
    """Compute quality metrics for extracted markdown text."""
    text = markdown_text or ""
    text_chars = len(text)
    token = IMAGE_PLACEHOLDER_TOKEN
    image_placeholders = text.count(token) if token else 0
    ratio = 0.0
    if text_chars > 0:
        ratio = image_placeholders / text_chars
    return {
        "text_chars": text_chars,
        "image_placeholders": image_placeholders,
        "image_placeholder_ratio": ratio,
    }


def should_fallback(markdown_text: str) -> Tuple[bool, Dict[str, float]]:
    """Decide whether extraction quality requires fallback processing."""
    metrics = compute_metrics(markdown_text)
    if metrics["text_chars"] <= 0:
        return True, metrics
    if metrics["text_chars"] < MIN_TEXT_CHARS:
        return True, metrics
    if metrics["image_placeholder_ratio"] > MAX_IMAGE_PLACEHOLDER_RATIO:
        return True, metrics
    return False, metrics
