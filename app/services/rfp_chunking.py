from __future__ import annotations


def chunk_text(text: str, max_chars: int = 12000, overlap_chars: int = 1500) -> list[str]:
    if not text:
        return [""]
    if max_chars <= 0:
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
