from __future__ import annotations

from app.services.rfp_config import CHUNK_MAX_CHARS, CHUNK_OVERLAP_CHARS


def chunk_text(
    text: str,
    max_chars: int = CHUNK_MAX_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> list[str]:
    if not text:
        return [""]
    if max_chars <= 0:
        return [text]
    if len(text) <= max_chars:
        return [text]
    if overlap_chars < 0:
        overlap_chars = 0

    chunks: list[str] = []
    text_len = len(text)
    start = 0
    while start < text_len:
        end = min(start + max_chars, text_len)
        chunk = text[start:end]
        chunks.append(chunk)
        if end >= text_len:
            break
        next_start = end - overlap_chars
        if next_start <= start:
            next_start = end
        start = next_start
    return chunks


def chunk_stats(
    text: str,
    max_chars: int = CHUNK_MAX_CHARS,
    overlap_chars: int = CHUNK_OVERLAP_CHARS,
) -> dict:
    chunks = chunk_text(text, max_chars=max_chars, overlap_chars=overlap_chars)
    lengths = [len(chunk) for chunk in chunks]
    count = len(lengths)
    min_len = min(lengths) if lengths else 0
    max_len = max(lengths) if lengths else 0
    total_len = sum(lengths)
    return {
        "count": count,
        "min_len": min_len,
        "max_len": max_len,
        "total_len": total_len,
        "lengths": lengths,
        "max_chars": max_chars,
        "overlap_chars": overlap_chars,
    }
