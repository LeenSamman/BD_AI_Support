from PyPDF2 import PdfReader


def extract_pdf_text(path: str) -> str:
    text = ""
    reader = PdfReader(path)
    for page in reader.pages:
        text += (page.extract_text() or "") + "\n"
    return text.strip()
