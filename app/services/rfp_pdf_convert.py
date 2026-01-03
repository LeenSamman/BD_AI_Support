from __future__ import annotations

import os
import subprocess


def convert_to_pdf(input_path: str, out_dir: str) -> str:
    """Convert a document to PDF using LibreOffice headless."""
    if not input_path or not os.path.isfile(input_path):
        raise RuntimeError(f"Input file not found: {input_path}")
    if not out_dir:
        raise RuntimeError("Output directory is required")
    os.makedirs(out_dir, exist_ok=True)

    soffice_path = r"C:\Program Files\LibreOffice\program\soffice.exe"
    binary = soffice_path if os.path.exists(soffice_path) else "soffice"
    command = [
        binary,
        "--headless",
        "--nologo",
        "--nolockcheck",
        "--nodefault",
        "--nofirststartwizard",
        "--convert-to",
        "pdf",
        "--outdir",
        out_dir,
        input_path,
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"LibreOffice conversion failed: {stderr or 'unknown error'}")

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(out_dir, f"{base_name}.pdf")
    if not os.path.exists(pdf_path):
        raise RuntimeError("PDF conversion did not produce an output file")
    return pdf_path
