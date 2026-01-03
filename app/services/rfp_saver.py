from __future__ import annotations

import os
from typing import Dict


def save_extracted_text(base_id: str, text: str) -> Dict[str, object]:
    """Persist extracted text to markdown and plain-text files."""
    extracted_md_dir = os.path.join("uploads", "rfp_extracted_md")
    extracted_txt_dir = os.path.join("uploads", "rfp_extracted_txt")
    os.makedirs(extracted_md_dir, exist_ok=True)
    os.makedirs(extracted_txt_dir, exist_ok=True)

    md_path = os.path.join(extracted_md_dir, f"{base_id}.md")
    txt_path = os.path.join(extracted_txt_dir, f"{base_id}.txt")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(text)
    with open(txt_path, "w", encoding="utf-8") as f:
        f.write(text)

    print(f"RFP Save: MD + TXT saved (len={len(text)})")
    return {
        "md_path": md_path,
        "txt_path": txt_path,
        "length": len(text),
    }
