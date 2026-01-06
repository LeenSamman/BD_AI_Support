from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from typing import Dict


def extract_rfp(file_path: str) -> Dict[str, object]:
    """Run Docling extraction in a subprocess and return the same payload."""
    script_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "scripts", "extract_worker.py")
    script_path = os.path.normpath(script_path)
    proc = subprocess.Popen(
        [sys.executable, script_path, "--file", file_path],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    logging.getLogger("rfp").info(
        "SUBPROCESS_EXTRACTOR=ON launching worker pid=%s",
        proc.pid,
    )
    stdout, stderr = proc.communicate()

    if proc.returncode != 0:
        raise RuntimeError(f"extract_worker failed: {stderr.strip()}")

    stdout = (stdout or "").strip()
    if not stdout:
        raise RuntimeError("extract_worker returned no output")

    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"extract_worker returned invalid JSON: {exc}") from exc

    return payload
