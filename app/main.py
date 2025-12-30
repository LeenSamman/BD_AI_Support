from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, RedirectResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import sqlite3
import os
import csv
import io
import uuid
import subprocess
from app.services.rfp_model import call_local_rfp_model
from app.services.pdf_extract import extract_pdf_text
from app.services.docling_extract import extract_with_docling
from app.services.word_extract import extract_text_from_word

app = FastAPI(title="Staffing Admin")

templates = Jinja2Templates(directory="app/templates")
UPLOADS_DIR = "uploads"
os.makedirs(UPLOADS_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "DB", "staffing.db")

RFP_ORIGINAL_DIR = os.path.join("uploads", "rfp_original_uploaded")
RFP_ORIGINAL_DIR_LEGACY = os.path.join("uploads", "rfp")
RFP_EXTRACTED_MD_DIR = os.path.join("uploads", "rfp_extracted_md")
RFP_EXTRACTED_MD_DIR_LEGACY = os.path.join("uploads", "rfp_extracted")
RFP_EXTRACTED_RAW_DIR = os.path.join("uploads", "rfp_extracted_txt")
RFP_EXTRACTED_RAW_DIR_LEGACY = os.path.join("uploads", "rfp_extracted_raw")
RFP_MODEL_RAW_DIR = os.path.join("uploads", "rfp_model_raw_response")
RFP_MODEL_RAW_DIR_LEGACY = os.path.join("uploads", "rfp_model_raw")


def resolve_legacy_path(preferred_path: str, legacy_path: str) -> str:
    if os.path.exists(preferred_path):
        return preferred_path
    if os.path.exists(legacy_path):
        print(f"RFP extract: using legacy path {legacy_path}")
        return legacy_path
    return preferred_path

def get_countries(search=None, page=1, per_page=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    query = "SELECT name, iso_code, region FROM Country"
    params = []
    if search:
        query += " WHERE name LIKE ? OR iso_code LIKE ?"
        params = [f"%{search}%", f"%{search}%"]
    query += " ORDER BY name LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    countries = cursor.fetchall()
    # Get total count for pagination
    count_query = "SELECT COUNT(*) FROM Country"
    count_params = []
    if search:
        count_query += " WHERE name LIKE ? OR iso_code LIKE ?"
        count_params = [f"%{search}%", f"%{search}%"]
    cursor.execute(count_query, count_params)
    total = cursor.fetchone()[0]
    conn.close()
    return countries, total

def get_departments(search=None, page=1, per_page=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    query = "SELECT department_id, name FROM Department"
    params = []
    if search:
        query += " WHERE name LIKE ?"
        params = [f"%{search}%"]
    query += " ORDER BY name LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    departments = cursor.fetchall()
    # Get total count
    count_query = "SELECT COUNT(*) FROM Department"
    count_params = []
    if search:
        count_query += " WHERE name LIKE ?"
        count_params = [f"%{search}%"]
    cursor.execute(count_query, count_params)
    total = cursor.fetchone()[0]
    conn.close()
    return departments, total

def add_department(name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Department (name) VALUES (?)", (name,))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Department name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_department(department_id, name):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Department SET name = ? WHERE department_id = ?", (name, department_id))
        if cursor.rowcount == 0:
            return False, "Department not found."
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Department name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_department(department_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Check if referenced
        cursor.execute("SELECT COUNT(*) FROM Employee WHERE department_id = ?", (department_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            return False, f"Cannot delete department: {count} employee(s) are assigned to it."
        cursor.execute("DELETE FROM Department WHERE department_id = ?", (department_id,))
        if cursor.rowcount == 0:
            return False, "Department not found."
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_department(department_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT department_id, name FROM Department WHERE department_id = ?", (department_id,))
    dept = cursor.fetchone()
    conn.close()
    return dept

def get_sectors(search=None, page=1, per_page=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    query = "SELECT sector_id, name, description FROM Sector"
    params = []
    if search:
        query += " WHERE name LIKE ?"
        params = [f"%{search}%"]
    query += " ORDER BY name LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    sectors = cursor.fetchall()
    # Get total count
    count_query = "SELECT COUNT(*) FROM Sector"
    count_params = []
    if search:
        count_query += " WHERE name LIKE ?"
        count_params = [f"%{search}%"]
    cursor.execute(count_query, count_params)
    total = cursor.fetchone()[0]
    conn.close()
    return sectors, total

def add_sector(name, description):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Sector (name, description) VALUES (?, ?)", (name, description))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Sector name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_sector(sector_id, name, description):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Sector SET name = ?, description = ? WHERE sector_id = ?", (name, description, sector_id))
        if cursor.rowcount == 0:
            return False, "Sector not found."
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Sector name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_sector(sector_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Check if referenced
        cursor.execute("SELECT COUNT(*) FROM ClientSector WHERE sector_id = ?", (sector_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            return False, f"Cannot delete sector: {count} client(s) are assigned to it."
        cursor.execute("DELETE FROM Sector WHERE sector_id = ?", (sector_id,))
        if cursor.rowcount == 0:
            return False, "Sector not found."
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_sector(sector_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT sector_id, name, description FROM Sector WHERE sector_id = ?", (sector_id,))
    sector = cursor.fetchone()
    conn.close()
    return sector

def get_business_lines(search=None, page=1, per_page=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    query = "SELECT business_line_id, name, description FROM BusinessLine"
    params = []
    if search:
        query += " WHERE name LIKE ?"
        params = [f"%{search}%"]
    query += " ORDER BY name LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    business_lines = cursor.fetchall()
    # Get total count
    count_query = "SELECT COUNT(*) FROM BusinessLine"
    count_params = []
    if search:
        count_query += " WHERE name LIKE ?"
        count_params = [f"%{search}%"]
    cursor.execute(count_query, count_params)
    total = cursor.fetchone()[0]
    conn.close()
    return business_lines, total

def add_business_line(name, description):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO BusinessLine (name, description) VALUES (?, ?)", (name, description))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Business Line name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_business_line(business_line_id, name, description):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE BusinessLine SET name = ?, description = ? WHERE business_line_id = ?", (name, description, business_line_id))
        if cursor.rowcount == 0:
            return False, "Business Line not found."
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Business Line name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_business_line(business_line_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Check if referenced
        cursor.execute("SELECT COUNT(*) FROM ProjectBusinessLine WHERE business_line_id = ?", (business_line_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            return False, f"Cannot delete business line: {count} project(s) are assigned to it."
        cursor.execute("DELETE FROM BusinessLine WHERE business_line_id = ?", (business_line_id,))
        if cursor.rowcount == 0:
            return False, "Business Line not found."
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_business_line(business_line_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT business_line_id, name, description FROM BusinessLine WHERE business_line_id = ?", (business_line_id,))
    bl = cursor.fetchone()
    conn.close()
    return bl

def seed_languages():
    known_languages = [
        ('Arabic', 'ar'),
        ('English', 'en'),
        ('French', 'fr'),
        ('German', 'de'),
        ('Spanish', 'es'),
        ('Chinese', 'zh'),
        ('Turkish', 'tr'),
        ('Portuguese', 'pt')
    ]
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    for name, iso in known_languages:
        cursor.execute("SELECT COUNT(*) FROM Language WHERE name = ?", (name,))
        if cursor.fetchone()[0] == 0:
            cursor.execute("INSERT INTO Language (name, iso_code) VALUES (?, ?)", (name, iso))
    conn.commit()
    conn.close()

def get_languages(search=None, page=1, per_page=10):
    seed_languages()  # Ensure seeded
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    query = "SELECT language_id, name, iso_code FROM Language"
    params = []
    if search:
        query += " WHERE name LIKE ?"
        params = [f"%{search}%"]
    query += " ORDER BY name LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    languages = cursor.fetchall()
    # Get total count
    count_query = "SELECT COUNT(*) FROM Language"
    count_params = []
    if search:
        count_query += " WHERE name LIKE ?"
        count_params = [f"%{search}%"]
    cursor.execute(count_query, count_params)
    total = cursor.fetchone()[0]
    conn.close()
    return languages, total

def add_language(name, iso_code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Language (name, iso_code) VALUES (?, ?)", (name, iso_code))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Language name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_language(language_id, name, iso_code):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Language SET name = ?, iso_code = ? WHERE language_id = ?", (name, iso_code, language_id))
        if cursor.rowcount == 0:
            return False, "Language not found."
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Language name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_language(language_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Check if referenced
        cursor.execute("SELECT COUNT(*) FROM ResourceLanguage WHERE language_id = ?", (language_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            return False, f"Cannot delete language: {count} resource(s) are assigned to it."
        cursor.execute("DELETE FROM Language WHERE language_id = ?", (language_id,))
        if cursor.rowcount == 0:
            return False, "Language not found."
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_language(language_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT language_id, name, iso_code FROM Language WHERE language_id = ?", (language_id,))
    lang = cursor.fetchone()
    conn.close()
    return lang

def get_certifications(search=None, page=1, per_page=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    query = "SELECT certification_id, name, issuing_body FROM Certification"
    params = []
    if search:
        query += " WHERE name LIKE ?"
        params = [f"%{search}%"]
    query += " ORDER BY name LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    certifications = cursor.fetchall()
    # Get total count
    count_query = "SELECT COUNT(*) FROM Certification"
    count_params = []
    if search:
        count_query += " WHERE name LIKE ?"
        count_params = [f"%{search}%"]
    cursor.execute(count_query, count_params)
    total = cursor.fetchone()[0]
    conn.close()
    return certifications, total

def add_certification(name, issuing_body):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO Certification (name, issuing_body) VALUES (?, ?)", (name, issuing_body))
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Certification name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def update_certification(certification_id, name, issuing_body):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE Certification SET name = ?, issuing_body = ? WHERE certification_id = ?", (name, issuing_body, certification_id))
        if cursor.rowcount == 0:
            return False, "Certification not found."
        conn.commit()
        return True, None
    except sqlite3.IntegrityError:
        return False, "Certification name must be unique."
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def delete_certification(certification_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        # Check if referenced
        cursor.execute("SELECT COUNT(*) FROM ResourceCertification WHERE certification_id = ?", (certification_id,))
        count = cursor.fetchone()[0]
        if count > 0:
            return False, f"Cannot delete certification: {count} resource(s) have this certification."
        cursor.execute("DELETE FROM Certification WHERE certification_id = ?", (certification_id,))
        if cursor.rowcount == 0:
            return False, "Certification not found."
        conn.commit()
        return True, None
    except Exception as e:
        return False, str(e)
    finally:
        conn.close()

def get_certification(certification_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT certification_id, name, issuing_body FROM Certification WHERE certification_id = ?", (certification_id,))
    cert = cursor.fetchone()
    conn.close()
    return cert

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request, "active": "dashboard"})

@app.get("/rfp", response_class=HTMLResponse)
async def rfp_get(request: Request):
    return templates.TemplateResponse("rfp.html", {
        "request": request,
        "active": "rfp",
        "result": None,
        "extracted_text": "",
        "extracted_text_truncated": False,
        "file_name": None,
        "file_url": None,
        "file_ext": None,
        "preview_url": None,
        "preview_note": None,
        "error": None
    })

def convert_word_to_pdf(input_path, output_dir):
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
        output_dir,
        input_path
    ]
    subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(output_dir, f"{base_name}.pdf")
    if not os.path.exists(pdf_path):
        raise RuntimeError("PDF preview was not generated.")
    return pdf_path

@app.post("/rfp/preview")
async def rfp_preview(file: UploadFile = File(...)):
    original_name = file.filename or ""
    ext = os.path.splitext(original_name)[1].lower().lstrip(".")
    if ext not in {"pdf", "doc", "docx"}:
        return JSONResponse({
            "ok": False,
            "preview_url": None,
            "file_url": None,
            "file_name": original_name,
            "file_ext": ext,
            "preview_note": None,
            "error": "Unsupported file type. Please upload a PDF or Word document.",
        }, status_code=400)

    upload_dir = os.path.join("uploads", "rfp")
    os.makedirs(upload_dir, exist_ok=True)
    base_id = str(uuid.uuid4())
    stored_name = f"{base_id}.{ext}"
    stored_path = os.path.join(upload_dir, stored_name)
    with open(stored_path, "wb") as f:
        f.write(await file.read())

    file_url = f"/uploads/rfp/{stored_name}"
    if ext == "pdf":
        return {
            "ok": True,
            "preview_url": file_url,
            "file_url": file_url,
            "file_name": original_name,
            "file_ext": ext,
            "preview_note": "Preview: Original PDF",
            "error": None,
        }

    try:
        pdf_path = convert_word_to_pdf(stored_path, upload_dir)
        preview_url = f"/uploads/rfp/{os.path.basename(pdf_path)}"
        return {
            "ok": True,
            "preview_url": preview_url,
            "file_url": file_url,
            "file_name": original_name,
            "file_ext": ext,
            "preview_note": "PDF generated for preview only",
            "error": None,
        }
    except Exception as exc:
        return JSONResponse({
            "ok": False,
            "preview_url": None,
            "file_url": file_url,
            "file_name": original_name,
            "file_ext": ext,
            "preview_note": None,
            "error": f"Word preview conversion failed: {exc}",
        }, status_code=500)

@app.post("/rfp/upload", response_class=HTMLResponse)
async def rfp_upload(request: Request, file: UploadFile = File(None)):
    # Analyze button now processes document first
    print("🚀 Upload route triggered")
    form = await request.form()
    rfp_text = (form.get("rfp_text") or "").strip()
    extracted_text = ""
    extracted_text_truncated = False

    # If `file` is None or has no filename, this branch is skipped and the model won't run.
    if file and file.filename:
        print("📄 File uploaded:", file.filename)
        original_name = file.filename or ""
        ext = os.path.splitext(original_name)[1].lower().lstrip(".")
        print("🔍 File type:", ext)
        if ext not in {"pdf", "doc", "docx"}:
            return templates.TemplateResponse("rfp.html", {
                "request": request,
                "active": "rfp",
                "result": None,
                "extracted_text": extracted_text,
                "extracted_text_truncated": extracted_text_truncated,
                "file_name": None,
                "file_url": None,
                "file_ext": None,
                "preview_url": None,
                "preview_note": None,
                "error": "Unsupported file type. Please upload a PDF or Word document."
            })

        upload_dir = RFP_ORIGINAL_DIR
        os.makedirs(upload_dir, exist_ok=True)
        base_id = str(uuid.uuid4())
        stored_name = f"{base_id}.{ext}"
        stored_path = os.path.join(upload_dir, stored_name)
        with open(stored_path, "wb") as f:
            f.write(await file.read())

        legacy_stored_path = os.path.join(RFP_ORIGINAL_DIR_LEGACY, stored_name)
        stored_path_for_read = resolve_legacy_path(stored_path, legacy_stored_path)
        file_url = f"/uploads/rfp_original_uploaded/{stored_name}"
        preview_url = file_url
        preview_note = "Preview: Original PDF"
        text_source_path = stored_path_for_read
        if ext in {"doc", "docx"}:
            try:
                pdf_path = convert_word_to_pdf(stored_path_for_read, upload_dir)
                preview_url = f"/uploads/rfp_original_uploaded/{os.path.basename(pdf_path)}"
                preview_note = "Preview: Converted to PDF for preview only (original Word file preserved)."
                text_source_path = pdf_path
            except Exception:
                return templates.TemplateResponse("rfp.html", {
                    "request": request,
                    "active": "rfp",
                    "result": None,
                    "extracted_text": extracted_text,
                    "extracted_text_truncated": extracted_text_truncated,
                    "file_name": original_name,
                    "file_url": file_url,
                    "file_ext": ext,
                    "preview_url": None,
                    "preview_note": None,
                    "error": "Word preview conversion failed. Please verify LibreOffice is installed."
                })

        try:
            try:
                docling_result = extract_with_docling(stored_path_for_read)
                extracted_text = (docling_result.get("text") or "").strip()
                artifacts_dir = docling_result.get("artifacts_dir")
                pages = docling_result.get("pages") or []
                pages_count = len(pages) if isinstance(pages, list) else 0
                print(
                    f"RFP extract: docling (text_len={len(extracted_text)}, pages_count={pages_count}, artifacts_dir={artifacts_dir})"
                )
            except Exception as exc:
                print(f"RFP extract: docling failed ({exc}); falling back")
                if ext in {"doc", "docx"}:
                    extracted_text = extract_text_from_word(stored_path)
                    print(f"RFP extract: word (len={len(extracted_text)})")
                else:
                    extracted_text = extract_pdf_text(text_source_path)
                    print(f"RFP extract: pypdf2 (len={len(extracted_text)})")
            extracted_raw_dir = RFP_EXTRACTED_RAW_DIR
            os.makedirs(extracted_raw_dir, exist_ok=True)
            extracted_raw_path = os.path.join(extracted_raw_dir, f"{base_id}.txt")
            with open(extracted_raw_path, "w", encoding="utf-8") as f:
                f.write(extracted_text)
            print(f"RFP extract: saved extracted_raw -> {extracted_raw_path}")
            if len(extracted_text) > 50000:
                extracted_text = extracted_text[:50000]
                extracted_text_truncated = True
        except Exception as exc:
            return templates.TemplateResponse("rfp.html", {
                "request": request,
                "active": "rfp",
                "result": None,
                "extracted_text": extracted_text,
                "extracted_text_truncated": extracted_text_truncated,
                "file_name": original_name,
                "file_url": file_url,
                "file_ext": ext,
                "preview_url": preview_url,
                "preview_note": preview_note,
                "error": f"Failed to extract text from document: {exc}"
            })

        extracted_dir = RFP_EXTRACTED_MD_DIR
        os.makedirs(extracted_dir, exist_ok=True)
        extracted_path = os.path.join(extracted_dir, f"{base_id}.md")
        with open(extracted_path, "w", encoding="utf-8") as f:
            f.write(extracted_text)
        print(f"RFP extract: saved extracted_text -> {extracted_path}")

        print("🧠 Sending extracted text to model...")
        raw_result = call_local_rfp_model(extracted_text)
        print("✔ Model returned response successfully")
        raw_dir = RFP_MODEL_RAW_DIR
        os.makedirs(raw_dir, exist_ok=True)
        raw_path = os.path.join(raw_dir, f"{base_id}.txt")
        with open(raw_path, "w", encoding="utf-8") as f:
            f.write(str(raw_result))
        print(f"RFP extract: saved model raw -> {raw_path}")
        result = normalize_rfp_result(raw_result)
        return templates.TemplateResponse("rfp.html", {
            "request": request,
            "active": "rfp",
            "result": result,
            "extracted_text": extracted_text,
            "extracted_text_truncated": extracted_text_truncated,
            "file_name": original_name,
            "file_url": file_url,
            "file_ext": ext,
            "preview_url": preview_url,
            "preview_note": preview_note,
            "error": None
        })

    if rfp_text:
        print("📝 Using manual text analysis — no file uploaded")
        raw_result = call_local_rfp_model(rfp_text)
        print("✔ Model returned response successfully")
        result = normalize_rfp_result(raw_result)
        return templates.TemplateResponse("rfp.html", {
            "request": request,
            "active": "rfp",
            "result": result,
            "extracted_text": extracted_text,
            "extracted_text_truncated": extracted_text_truncated,
            "file_name": None,
            "file_url": None,
            "file_ext": None,
            "preview_url": None,
            "preview_note": None,
            "error": None
        })

    return templates.TemplateResponse("rfp.html", {
        "request": request,
        "active": "rfp",
        "result": None,
        "extracted_text": "",
        "extracted_text_truncated": False,
        "file_name": None,
        "file_url": None,
        "file_ext": None,
        "preview_url": None,
        "preview_note": None,
        "error": "No input provided. Please upload a file or paste text to analyze."
    })
def format_rfp_section(value):
    if isinstance(value, list):
        return "; ".join(str(item) for item in value if item is not None)
    return value

def normalize_rfp_result(data):
    requirements = (
        data.get("requirements")
        or data.get("requirements_checklist")
        or data.get("requirements_grouped")
    )
    if isinstance(requirements, dict):
        company = requirements.get("company")
        team = requirements.get("team")
        technical = requirements.get("technical")
        financial = requirements.get("financial")
        submission = requirements.get("submission")
        deliverables = requirements.get("deliverables")
        evaluation = requirements.get("evaluation")
    else:
        company = data.get("company_requirements")
        team = data.get("team_requirements")
        technical = data.get("technical_requirements")
        financial = data.get("financial_requirements")
        submission = data.get("submission_requirements")
        deliverables = data.get("deliverables_timeline")
        evaluation = data.get("evaluation_criteria")

    return {
        "summary": format_rfp_section(data.get("summary")),
        "company_requirements": format_rfp_section(company),
        "team_requirements": format_rfp_section(team),
        "technical_requirements": format_rfp_section(technical),
        "financial_requirements": format_rfp_section(financial),
        "submission_requirements": format_rfp_section(submission),
        "deliverables_timeline": format_rfp_section(deliverables),
        "evaluation_criteria": format_rfp_section(evaluation),
        "risks": format_rfp_section(data.get("risks_red_flags") or data.get("risks")),
        "questions_for_client": format_rfp_section(data.get("questions_for_client")),
        "missing_information": format_rfp_section(data.get("missing_information")),
    }

@app.post("/rfp/analyze-text", response_class=HTMLResponse)
async def rfp_analyze_text(request: Request):
    form = await request.form()
    rfp_text = (form.get("rfp_text") or "").strip()
    if not rfp_text:
        return templates.TemplateResponse("rfp.html", {
            "request": request,
            "active": "rfp",
            "result": None,
            "file_name": None,
            "file_url": None,
            "file_ext": None,
            "preview_url": None,
            "preview_note": None,
            "error": "Please paste some RFP text before analyzing."
        })

    raw_result = call_local_rfp_model(rfp_text)
    result = normalize_rfp_result(raw_result)
    return templates.TemplateResponse("rfp.html", {
        "request": request,
        "active": "rfp",
        "result": result,
        "file_name": None,
        "file_url": None,
        "file_ext": None,
        "preview_url": None,
        "preview_note": None,
        "error": None
    })

@app.get("/employees", response_class=HTMLResponse)
async def employees(request: Request, employee_id: int = None, mode: str = None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        # Reference data (unchanged)
        cursor.execute("SELECT department_id, name FROM Department ORDER BY name")
        departments = cursor.fetchall()

        cursor.execute("SELECT country_id, name FROM Country ORDER BY name")
        countries = cursor.fetchall()

        cursor.execute("SELECT language_id, name FROM Language ORDER BY name")
        languages = cursor.fetchall()

        cursor.execute("SELECT certification_id, name FROM Certification ORDER BY name")
        certifications = cursor.fetchall()
        
        cursor.execute("SELECT language_id, name FROM Language ORDER BY name")
        languages = cursor.fetchall()

        cursor.execute("SELECT language_id, name FROM Language ORDER BY name")
        languages = cursor.fetchall()

        # Employees list
        employee_query = """
            SELECT
                e.employee_id,
                e.first_name,
                e.last_name,
                e.email,
                e.phone,
                e.hire_date,
                e.birth_date,
                e.title,
                e.years_experience,
                d.name AS department_name,
                c.name AS country_name,
                r.resource_id,
                r.status AS resource_status
            FROM Employee e
            LEFT JOIN Department d ON e.department_id = d.department_id
            LEFT JOIN Country c ON e.residence_country_id = c.country_id
            LEFT JOIN Resource r
                ON r.employee_id = e.employee_id
               AND r.resource_type = 'Employee'
            ORDER BY e.last_name, e.first_name
        """
        cursor.execute(employee_query)
        rows = cursor.fetchall()

        # ---- NEW: edit-mode data ----
        employee_languages = []
        employee_certifications = []
        employee_row = None
        employee = None

        if employee_id:
            # Load employee + resource id
            cursor.execute("""
                SELECT
                    e.employee_id,
                    e.first_name,
                    e.last_name,
                    e.email,
                    e.phone,
                    e.hire_date,
                    e.birth_date,
                    e.department_id,
                    e.residence_country_id,
                    e.title,
                    e.years_experience,
                    r.resource_id,
                    r.status,
                    r.is_willing_to_travel,
                    r.bio_text,
                    r.cv_text
                FROM Employee e
                LEFT JOIN Resource r
                  ON r.employee_id = e.employee_id
                 AND r.resource_type = 'Employee'
                WHERE e.employee_id = ?
            """, (employee_id,))
            employee_row = cursor.fetchone()

            if employee_row:
                employee = {
                    "employee_id": employee_row[0],
                    "first_name": employee_row[1],
                    "last_name": employee_row[2],
                    "email": employee_row[3],
                    "phone": employee_row[4],
                    "hire_date": employee_row[5],
                    "birth_date": employee_row[6],
                    "department_id": employee_row[7],
                    "residence_country_id": employee_row[8],
                    "title": employee_row[9],
                    "years_experience": employee_row[10],
                    "resource_id": employee_row[11],
                    "resource_status": employee_row[12],
                    "is_willing_to_travel": employee_row[13],
                    "bio_text": employee_row[14],
                    "cv_text": employee_row[15],
                }
                resource_id = employee["resource_id"]

                # Languages linked to resource
                if resource_id:
                    cursor.execute("""
                        SELECT
                            rl.language_id,
                            l.name,
                            rl.proficiency_level
                        FROM ResourceLanguage rl
                        JOIN Language l ON rl.language_id = l.language_id
                        WHERE rl.resource_id = ?
                        ORDER BY l.name
                    """, (resource_id,))
                    employee_languages = cursor.fetchall()

                # Certifications linked to resource
                if resource_id:
                    cursor.execute("""
                    SELECT
                        rc.certification_id,
                        c.name,
                        rc.obtained_date,
                        rc.expiry_date,
                        rc.issuing_body
                    FROM ResourceCertification rc
                    JOIN Certification c ON rc.certification_id = c.certification_id
                    WHERE rc.resource_id = ?
                    ORDER BY c.name
                    """, (resource_id,))
                    employee_certifications = cursor.fetchall()

    finally:
        conn.close()

    from collections import namedtuple

    EmployeeRow = namedtuple(
        "EmployeeRow",
        [
            "employee_id",
            "first_name",
            "last_name",
            "email",
            "phone",
            "hire_date",
            "birth_date",
            "title",
            "years_experience",
            "department_name",
            "country_name",
            "resource_id",
            "resource_status",
            "full_name",
        ],
    )

    employees = [
        EmployeeRow(
            employee_id,
            first_name,
            last_name,
            email,
            phone,
            hire_date,
            birth_date,
            title,
            years_experience,
            department_name,
            country_name,
            resource_id,
            resource_status,
            f"{first_name} {last_name}".strip(),
        )
        for (
            employee_id,
            first_name,
            last_name,
            email,
            phone,
            hire_date,
            birth_date,
            title,
            years_experience,
            department_name,
            country_name,
            resource_id,
            resource_status,
        ) in rows
    ]

    return templates.TemplateResponse("employees.html", {
        "request": request,
        "active": "employees",
        "departments": departments,
        "countries": countries,
        "languages": languages,
        "certifications": certifications,
        "employees": employees,

        # ---- NEW context ----
        "employee": employee,
        "employee_languages": employee_languages,
        "employee_certifications": employee_certifications,
        "view_mode": (mode == "view")
    })

@app.get("/employees/export")
async def employees_export():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                e.first_name,
                e.last_name,
                d.name AS department_name,
                e.title,
                e.years_experience,
                r.status AS resource_status
            FROM Employee e
            LEFT JOIN Department d ON e.department_id = d.department_id
            LEFT JOIN Resource r
                ON r.employee_id = e.employee_id
               AND r.resource_type = 'Employee'
            ORDER BY e.last_name, e.first_name
        """)
        rows = cursor.fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Employee Name", "Department", "Title", "Years of Experience", "Status"])
    for first_name, last_name, department_name, title, years_experience, resource_status in rows:
        full_name = f"{first_name} {last_name}".strip()
        writer.writerow([
            full_name,
            department_name or "",
            title or "",
            "" if years_experience is None else years_experience,
            resource_status or "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=employees_export.csv"},
    )

@app.post("/employees")
async def employees_post(request: Request):
    form = await request.form()

    def to_int(value):
        if value is None or value == "":
            return None
        return int(value)

    employee_id = to_int(form.get("employee_id"))
    first_name = form.get("first_name", "").strip()
    last_name = form.get("last_name", "").strip()
    email = form.get("email", "").strip()
    phone = form.get("phone", "").strip() or None
    department_id = to_int(form.get("department_id"))
    residence_country_id = to_int(form.get("residence_country_id"))
    hire_date = form.get("hire_date") or None
    title = form.get("title", "").strip() or None
    years_experience = to_int(form.get("years_experience"))
    resource_status = form.get("resource_status") or "Active"
    is_willing_to_travel = 1 if form.get("is_willing_to_travel") else 0
    bio_text = form.get("bio_text") or None
    cv_text = form.get("cv_text") or None
    language_ids = form.getlist("language_id[]")
    language_proficiencies = form.getlist("language_proficiency[]")
    certification_ids = form.getlist("certification_id[]")
    obtained_dates = form.getlist("certification_obtained_date[]")
    expiry_dates = form.getlist("certification_expiry_date[]")
    issuing_bodies = form.getlist("certification_issuing_body[]")
    if certification_ids and not issuing_bodies:
        issuing_bodies = [""] * len(certification_ids)
    add_cert_name = form.get("add_certification_name", "").strip()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN")
        if employee_id:
            cursor.execute("""
                UPDATE Employee
                SET first_name = ?, last_name = ?, email = ?, phone = ?,
                    department_id = ?, residence_country_id = ?, hire_date = ?,
                    title = ?, years_experience = ?
                WHERE employee_id = ?
            """, (first_name, last_name, email, phone, department_id, residence_country_id, hire_date, title, years_experience, employee_id))
            if cursor.rowcount == 0:
                conn.rollback()
                return RedirectResponse(url="/employees", status_code=303)
        else:
            cursor.execute("""
                INSERT INTO Employee
                (first_name, last_name, email, phone, department_id, residence_country_id, hire_date, title, years_experience)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (first_name, last_name, email, phone, department_id, residence_country_id, hire_date, title, years_experience))
            employee_id = cursor.lastrowid

        cursor.execute("""
            SELECT resource_id
            FROM Resource
            WHERE employee_id = ? AND resource_type = 'Employee'
        """, (employee_id,))
        resource_row = cursor.fetchone()

        if resource_row:
            resource_id = resource_row[0]
            cursor.execute("""
                UPDATE Resource
                SET status = ?, is_willing_to_travel = ?, bio_text = ?, cv_text = ?
                WHERE resource_id = ?
            """, (resource_status, is_willing_to_travel, bio_text, cv_text, resource_id))
        else:
            cursor.execute("""
                INSERT INTO Resource
                (resource_type, employee_id, status, is_willing_to_travel, bio_text, cv_text)
                VALUES ('Employee', ?, ?, ?, ?, ?)
            """, (employee_id, resource_status, is_willing_to_travel, bio_text, cv_text))
            resource_id = cursor.lastrowid

        if language_ids:
            cursor.execute("DELETE FROM ResourceLanguage WHERE resource_id = ?", (resource_id,))
            for language_id, proficiency in zip(language_ids, language_proficiencies):
                cursor.execute("""
                    INSERT INTO ResourceLanguage (resource_id, language_id, proficiency_level)
                    VALUES (?, ?, ?)
                """, (resource_id, int(language_id), proficiency))

        if certification_ids:
            cursor.execute("DELETE FROM ResourceCertification WHERE resource_id = ?", (resource_id,))
            for cert_id, obtained_date, expiry_date, issuing_body in zip(
                certification_ids,
                obtained_dates,
                expiry_dates,
                issuing_bodies,
            ):
                cursor.execute("""
                    INSERT INTO ResourceCertification
                    (resource_id, certification_id, obtained_date, expiry_date, issuing_body)
                    VALUES (?, ?, ?, ?, ?)
                """, (resource_id, int(cert_id), obtained_date or None, expiry_date or None, issuing_body or None))

        if add_cert_name:
            cursor.execute("SELECT certification_id FROM Certification WHERE name = ?", (add_cert_name,))
            cert_row = cursor.fetchone()
            if cert_row:
                add_cert_id = cert_row[0]
            else:
                cursor.execute("INSERT INTO Certification (name) VALUES (?)", (add_cert_name,))
                add_cert_id = cursor.lastrowid

            add_obtained_date = form.get("add_certification_obtained_date") or None
            add_expiry_date = form.get("add_certification_expiry_date") or None
            add_issuing_body = form.get("add_certification_issuing_body") or None
            cursor.execute("""
                INSERT OR IGNORE INTO ResourceCertification
                (resource_id, certification_id, obtained_date, expiry_date, issuing_body)
                VALUES (?, ?, ?, ?, ?)
            """, (resource_id, add_cert_id, add_obtained_date, add_expiry_date, add_issuing_body))

        conn.commit()
    except sqlite3.IntegrityError as e:
        conn.rollback()
        message = "Unable to save employee due to a data constraint."
        if "Employee.email" in str(e):
            message = "An employee with this email already exists."

        cursor.execute("SELECT department_id, name FROM Department ORDER BY name")
        departments = cursor.fetchall()
        cursor.execute("SELECT country_id, name FROM Country ORDER BY name")
        countries = cursor.fetchall()
        cursor.execute("SELECT language_id, name FROM Language ORDER BY name")
        languages = cursor.fetchall()
        cursor.execute("SELECT certification_id, name FROM Certification ORDER BY name")
        certifications = cursor.fetchall()
        cursor.execute("""
            SELECT
                e.employee_id,
                e.first_name,
                e.last_name,
                e.email,
                e.phone,
                e.hire_date,
                e.birth_date,
                e.title,
                e.years_experience,
                d.name AS department_name,
                c.name AS country_name,
                r.resource_id,
                r.status AS resource_status
            FROM Employee e
            LEFT JOIN Department d ON e.department_id = d.department_id
            LEFT JOIN Country c ON e.residence_country_id = c.country_id
            LEFT JOIN Resource r
                ON r.employee_id = e.employee_id
               AND r.resource_type = 'Employee'
            ORDER BY e.last_name, e.first_name
        """)
        rows = cursor.fetchall()

        from collections import namedtuple

        EmployeeRow = namedtuple(
            "EmployeeRow",
            [
                "employee_id",
                "first_name",
                "last_name",
                "email",
                "phone",
                "hire_date",
                "birth_date",
                "title",
                "years_experience",
                "department_name",
                "country_name",
                "resource_id",
                "resource_status",
                "full_name",
            ],
        )

        employees = [
            EmployeeRow(
                emp_id,
                first,
                last,
                emp_email,
                emp_phone,
                emp_hire_date,
                emp_birth_date,
                emp_title,
                emp_years,
                dept_name,
                country_name,
                res_id,
                res_status,
                f"{first} {last}".strip(),
            )
            for (
                emp_id,
                first,
                last,
                emp_email,
                emp_phone,
                emp_hire_date,
                emp_birth_date,
                emp_title,
                emp_years,
                dept_name,
                country_name,
                res_id,
                res_status,
            ) in rows
        ]

        language_map = {lang[0]: lang[1] for lang in languages}
        employee_languages = []
        for language_id, proficiency in zip(language_ids, language_proficiencies):
            if language_id:
                employee_languages.append((int(language_id), language_map.get(int(language_id), ""), proficiency))

        cert_map = {cert[0]: cert[1] for cert in certifications}
        employee_certifications = []
        for cert_id, obtained_date, expiry_date, issuing_body in zip(
            certification_ids,
            obtained_dates,
            expiry_dates,
            issuing_bodies,
        ):
            if cert_id:
                employee_certifications.append((
                    int(cert_id),
                    cert_map.get(int(cert_id), ""),
                    obtained_date or None,
                    expiry_date or None,
                    issuing_body or None,
                ))

        employee = {
            "employee_id": employee_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "hire_date": hire_date,
            "birth_date": form.get("birth_date") or None,
            "department_id": department_id,
            "residence_country_id": residence_country_id,
            "title": title,
            "years_experience": years_experience,
            "resource_id": to_int(form.get("resource_id")),
            "resource_status": resource_status,
            "is_willing_to_travel": is_willing_to_travel,
            "bio_text": bio_text,
            "cv_text": cv_text,
        }

        return templates.TemplateResponse("employees.html", {
            "request": request,
            "active": "employees",
            "departments": departments,
            "countries": countries,
            "languages": languages,
            "certifications": certifications,
            "employees": employees,
            "employee": employee,
            "employee_languages": employee_languages,
            "employee_certifications": employee_certifications,
            "view_mode": False,
            "error": message,
        })
    except Exception:
        conn.rollback()
        cursor.execute("SELECT department_id, name FROM Department ORDER BY name")
        departments = cursor.fetchall()
        cursor.execute("SELECT country_id, name FROM Country ORDER BY name")
        countries = cursor.fetchall()
        cursor.execute("SELECT language_id, name FROM Language ORDER BY name")
        languages = cursor.fetchall()
        cursor.execute("SELECT certification_id, name FROM Certification ORDER BY name")
        certifications = cursor.fetchall()
        cursor.execute("""
            SELECT
                e.employee_id,
                e.first_name,
                e.last_name,
                e.email,
                e.phone,
                e.hire_date,
                e.birth_date,
                e.title,
                e.years_experience,
                d.name AS department_name,
                c.name AS country_name,
                r.resource_id,
                r.status AS resource_status
            FROM Employee e
            LEFT JOIN Department d ON e.department_id = d.department_id
            LEFT JOIN Country c ON e.residence_country_id = c.country_id
            LEFT JOIN Resource r
                ON r.employee_id = e.employee_id
               AND r.resource_type = 'Employee'
            ORDER BY e.last_name, e.first_name
        """)
        rows = cursor.fetchall()

        from collections import namedtuple

        EmployeeRow = namedtuple(
            "EmployeeRow",
            [
                "employee_id",
                "first_name",
                "last_name",
                "email",
                "phone",
                "hire_date",
                "birth_date",
                "title",
                "years_experience",
                "department_name",
                "country_name",
                "resource_id",
                "resource_status",
                "full_name",
            ],
        )

        employees = [
            EmployeeRow(
                emp_id,
                first,
                last,
                emp_email,
                emp_phone,
                emp_hire_date,
                emp_birth_date,
                emp_title,
                emp_years,
                dept_name,
                country_name,
                res_id,
                res_status,
                f"{first} {last}".strip(),
            )
            for (
                emp_id,
                first,
                last,
                emp_email,
                emp_phone,
                emp_hire_date,
                emp_birth_date,
                emp_title,
                emp_years,
                dept_name,
                country_name,
                res_id,
                res_status,
            ) in rows
        ]

        employee = {
            "employee_id": employee_id,
            "first_name": first_name,
            "last_name": last_name,
            "email": email,
            "phone": phone,
            "hire_date": hire_date,
            "birth_date": form.get("birth_date") or None,
            "department_id": department_id,
            "residence_country_id": residence_country_id,
            "title": title,
            "years_experience": years_experience,
            "resource_id": to_int(form.get("resource_id")),
            "resource_status": resource_status,
            "is_willing_to_travel": is_willing_to_travel,
            "bio_text": bio_text,
            "cv_text": cv_text,
        }

        return templates.TemplateResponse("employees.html", {
            "request": request,
            "active": "employees",
            "departments": departments,
            "countries": countries,
            "languages": languages,
            "certifications": certifications,
            "employees": employees,
            "employee": employee,
            "employee_languages": [],
            "employee_certifications": [],
            "view_mode": False,
            "error": "Unable to save employee. Please try again.",
        })
    finally:
        conn.close()

    return RedirectResponse(url=f"/employees?employee_id={employee_id}", status_code=303)

@app.post("/employees/delete")
async def employees_delete(request: Request):
    form = await request.form()

    def to_int(value):
        if value is None or value == "":
            return None
        return int(value)

    employee_id = to_int(form.get("employee_id"))
    if not employee_id:
        return RedirectResponse(url="/employees", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    def render_error(message):
        cursor.execute("SELECT department_id, name FROM Department ORDER BY name")
        departments = cursor.fetchall()
        cursor.execute("SELECT country_id, name FROM Country ORDER BY name")
        countries = cursor.fetchall()
        cursor.execute("SELECT language_id, name FROM Language ORDER BY name")
        languages = cursor.fetchall()
        cursor.execute("SELECT certification_id, name FROM Certification ORDER BY name")
        certifications = cursor.fetchall()
        cursor.execute("""
            SELECT
                e.employee_id,
                e.first_name,
                e.last_name,
                e.email,
                e.phone,
                e.hire_date,
                e.birth_date,
                e.title,
                e.years_experience,
                d.name AS department_name,
                c.name AS country_name,
                r.resource_id,
                r.status AS resource_status
            FROM Employee e
            LEFT JOIN Department d ON e.department_id = d.department_id
            LEFT JOIN Country c ON e.residence_country_id = c.country_id
            LEFT JOIN Resource r
                ON r.employee_id = e.employee_id
               AND r.resource_type = 'Employee'
            ORDER BY e.last_name, e.first_name
        """)
        rows = cursor.fetchall()

        from collections import namedtuple

        EmployeeRow = namedtuple(
            "EmployeeRow",
            [
                "employee_id",
                "first_name",
                "last_name",
                "email",
                "phone",
                "hire_date",
                "birth_date",
                "title",
                "years_experience",
                "department_name",
                "country_name",
                "resource_id",
                "resource_status",
                "full_name",
            ],
        )

        employees = [
            EmployeeRow(
                emp_id,
                first,
                last,
                emp_email,
                emp_phone,
                emp_hire_date,
                emp_birth_date,
                emp_title,
                emp_years,
                dept_name,
                country_name,
                res_id,
                res_status,
                f"{first} {last}".strip(),
            )
            for (
                emp_id,
                first,
                last,
                emp_email,
                emp_phone,
                emp_hire_date,
                emp_birth_date,
                emp_title,
                emp_years,
                dept_name,
                country_name,
                res_id,
                res_status,
            ) in rows
        ]

        return templates.TemplateResponse("employees.html", {
            "request": request,
            "active": "employees",
            "departments": departments,
            "countries": countries,
            "languages": languages,
            "certifications": certifications,
            "employees": employees,
            "employee": None,
            "employee_languages": [],
            "employee_certifications": [],
            "view_mode": False,
            "error": message,
        })

    try:
        conn.execute("BEGIN")
        cursor.execute("""
            SELECT resource_id
            FROM Resource
            WHERE employee_id = ? AND resource_type = 'Employee'
        """, (employee_id,))
        resource_row = cursor.fetchone()
        resource_id = resource_row[0] if resource_row else None

        if resource_id:
            cursor.execute("SELECT COUNT(*) FROM Assignment WHERE resource_id = ?", (resource_id,))
            if cursor.fetchone()[0] > 0:
                conn.rollback()
                return render_error("Employee cannot be deleted because they have assignments.")

            cursor.execute("DELETE FROM ResourceLanguage WHERE resource_id = ?", (resource_id,))
            cursor.execute("DELETE FROM ResourceCertification WHERE resource_id = ?", (resource_id,))
            cursor.execute("DELETE FROM Resource WHERE resource_id = ?", (resource_id,))

        cursor.execute("DELETE FROM Employee WHERE employee_id = ?", (employee_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        return render_error("Unable to delete employee. Please try again.")
    finally:
        conn.close()

    return RedirectResponse(url="/employees", status_code=303)

@app.post("/employees/deactivate")
async def employees_deactivate(request: Request):
    form = await request.form()

    def to_int(value):
        if value is None or value == "":
            return None
        return int(value)

    employee_id = to_int(form.get("employee_id"))
    if not employee_id:
        return RedirectResponse(url="/employees", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT resource_id
            FROM Resource
            WHERE employee_id = ? AND resource_type = 'Employee'
        """, (employee_id,))
        resource_row = cursor.fetchone()
        if resource_row:
            cursor.execute("""
                UPDATE Resource
                SET status = 'Inactive'
                WHERE resource_id = ?
            """, (resource_row[0],))
        else:
            cursor.execute("""
                INSERT INTO Resource (resource_type, employee_id, status)
                VALUES ('Employee', ?, 'Inactive')
            """, (employee_id,))
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url=f"/employees?employee_id={employee_id}", status_code=303)


@app.get("/subcontractors", response_class=HTMLResponse)
async def subcontractors(request: Request, subcontractor_id: int = None, mode: str = None, error: str = None):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT country_id, name FROM Country ORDER BY name")
        countries = cursor.fetchall()

        cursor.execute("SELECT certification_id, name FROM Certification ORDER BY name")
        certifications = cursor.fetchall()
        
        cursor.execute("SELECT language_id, name FROM Language ORDER BY name")
        languages = cursor.fetchall()

        subcontractor_query = """
            SELECT
                s.subcontractor_id,
                s.company_name,
                s.contact_name,
                s.email,
                s.phone,
                s.birth_date,
                s.title,
                s.years_experience,
                c.name AS country_name,
                r.resource_id,
                r.status AS resource_status
            FROM Subcontractor s
            LEFT JOIN Country c ON s.residence_country_id = c.country_id
            LEFT JOIN Resource r
                ON r.subcontractor_id = s.subcontractor_id
               AND r.resource_type = 'Subcontractor'
            ORDER BY s.company_name, s.contact_name
        """
        cursor.execute(subcontractor_query)
        rows = cursor.fetchall()

        subcontractor = None
        subcontractor_certifications = []
        subcontractor_languages = []
        if subcontractor_id:
            cursor.execute("""
                SELECT
                    s.subcontractor_id,
                    s.company_name,
                    s.contact_name,
                    s.email,
                    s.phone,
                    s.birth_date,
                    s.title,
                    s.years_experience,
                    s.residence_country_id,
                    r.resource_id,
                    r.status,
                    r.is_willing_to_travel,
                    r.bio_text,
                    r.cv_text
                FROM Subcontractor s
                LEFT JOIN Resource r
                  ON r.subcontractor_id = s.subcontractor_id
                 AND r.resource_type = 'Subcontractor'
                WHERE s.subcontractor_id = ?
            """, (subcontractor_id,))
            row = cursor.fetchone()
            if row:
                subcontractor = {
                    "subcontractor_id": row[0],
                    "company_name": row[1],
                    "contact_name": row[2],
                    "email": row[3],
                    "phone": row[4],
                    "birth_date": row[5],
                    "title": row[6],
                    "years_experience": row[7],
                    "residence_country_id": row[8],
                    "resource_id": row[9],
                    "resource_status": row[10],
                    "is_willing_to_travel": row[11],
                    "bio_text": row[12],
                    "cv_text": row[13],
                }

                if subcontractor["resource_id"]:
                    cursor.execute("""
                        SELECT
                            rl.language_id,
                            l.name,
                            rl.proficiency_level
                        FROM ResourceLanguage rl
                        JOIN Language l ON rl.language_id = l.language_id
                        WHERE rl.resource_id = ?
                        ORDER BY l.name
                    """, (subcontractor["resource_id"],))
                    subcontractor_languages = cursor.fetchall()

                    cursor.execute("""
                        SELECT
                            rc.certification_id,
                            c.name,
                            rc.obtained_date,
                            rc.expiry_date,
                            rc.issuing_body
                        FROM ResourceCertification rc
                        JOIN Certification c ON rc.certification_id = c.certification_id
                        WHERE rc.resource_id = ?
                        ORDER BY c.name
                    """, (subcontractor["resource_id"],))
                    subcontractor_certifications = cursor.fetchall()
    finally:
        conn.close()

    from collections import namedtuple

    SubcontractorRow = namedtuple(
        "SubcontractorRow",
        [
            "subcontractor_id",
            "company_name",
            "contact_name",
            "email",
            "phone",
            "birth_date",
            "title",
            "years_experience",
            "country_name",
            "resource_id",
            "resource_status",
        ],
    )

    subcontractors = [
        SubcontractorRow(
            subcontractor_id,
            company_name,
            contact_name,
            email,
            phone,
            birth_date,
            title,
            years_experience,
            country_name,
            resource_id,
            resource_status,
        )
        for (
            subcontractor_id,
            company_name,
            contact_name,
            email,
            phone,
            birth_date,
            title,
            years_experience,
            country_name,
            resource_id,
            resource_status,
        ) in rows
    ]

    return templates.TemplateResponse("subcontractors.html", {
        "request": request,
        "active": "subcontractors",
        "countries": countries,
        "certifications": certifications,
        "languages": languages,
        "subcontractors": subcontractors,
        "subcontractor": subcontractor,
        "subcontractor_languages": subcontractor_languages,
        "subcontractor_certifications": subcontractor_certifications,
        "view_mode": (mode == "view"),
        "error": error,
    })

@app.get("/subcontractors/export")
async def subcontractors_export():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                s.company_name,
                s.contact_name,
                s.title,
                s.years_experience,
                c.name AS country_name,
                r.status AS resource_status
            FROM Subcontractor s
            LEFT JOIN Country c ON s.residence_country_id = c.country_id
            LEFT JOIN Resource r
                ON r.subcontractor_id = s.subcontractor_id
               AND r.resource_type = 'Subcontractor'
            ORDER BY s.company_name, s.contact_name
        """)
        rows = cursor.fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Company Name",
        "Contact Name",
        "Title",
        "Years of Experience",
        "Residence Country",
        "Status",
    ])
    for company_name, contact_name, title, years_experience, country_name, resource_status in rows:
        writer.writerow([
            company_name or "",
            contact_name or "",
            title or "",
            "" if years_experience is None else years_experience,
            country_name or "",
            resource_status or "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=subcontractors_export.csv"},
    )

@app.post("/subcontractors")
async def subcontractors_post(request: Request):
    form = await request.form()

    def to_int(value):
        if value is None or value == "":
            return None
        return int(value)

    subcontractor_id = to_int(form.get("subcontractor_id"))
    company_name = form.get("company_name", "").strip()
    contact_name = form.get("contact_name", "").strip()
    email = form.get("email", "").strip()
    phone = form.get("phone", "").strip() or None
    birth_date = form.get("birth_date") or None
    title = form.get("title", "").strip() or None
    years_experience = to_int(form.get("years_experience"))
    residence_country_id = to_int(form.get("residence_country_id"))
    resource_status = form.get("resource_status") or "Active"
    is_willing_to_travel = 1 if form.get("is_willing_to_travel") else 0
    bio_text = form.get("bio_text") or None
    cv_text = form.get("cv_text") or None

    language_ids = form.getlist("language_id[]")
    language_proficiencies = form.getlist("language_proficiency[]")
    certification_ids = form.getlist("certification_id[]")
    obtained_dates = form.getlist("certification_obtained_date[]")
    expiry_dates = form.getlist("certification_expiry_date[]")
    issuing_bodies = form.getlist("certification_issuing_body[]")
    if certification_ids and not issuing_bodies:
        issuing_bodies = [""] * len(certification_ids)
    add_cert_name = form.get("add_certification_name", "").strip()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    def render_error(message):
        cursor.execute("SELECT country_id, name FROM Country ORDER BY name")
        countries = cursor.fetchall()
        cursor.execute("SELECT certification_id, name FROM Certification ORDER BY name")
        certifications = cursor.fetchall()
        cursor.execute("SELECT language_id, name FROM Language ORDER BY name")
        languages = cursor.fetchall()
        cursor.execute("""
            SELECT
                s.subcontractor_id,
                s.company_name,
                s.contact_name,
                s.email,
                s.phone,
                s.birth_date,
                s.title,
                s.years_experience,
                c.name AS country_name,
                r.resource_id,
                r.status AS resource_status
            FROM Subcontractor s
            LEFT JOIN Country c ON s.residence_country_id = c.country_id
            LEFT JOIN Resource r
                ON r.subcontractor_id = s.subcontractor_id
               AND r.resource_type = 'Subcontractor'
            ORDER BY s.company_name, s.contact_name
        """)
        rows = cursor.fetchall()

        from collections import namedtuple

        SubcontractorRow = namedtuple(
            "SubcontractorRow",
            [
                "subcontractor_id",
                "company_name",
                "contact_name",
                "email",
                "phone",
                "birth_date",
                "title",
                "years_experience",
                "country_name",
                "resource_id",
                "resource_status",
            ],
        )

        subcontractors = [
            SubcontractorRow(
                sc_id,
                sc_company,
                sc_contact,
                sc_email,
                sc_phone,
                sc_birth,
                sc_title,
                sc_years,
                sc_country,
                sc_resource_id,
                sc_status,
            )
            for (
                sc_id,
                sc_company,
                sc_contact,
                sc_email,
                sc_phone,
                sc_birth,
                sc_title,
                sc_years,
                sc_country,
                sc_resource_id,
                sc_status,
            ) in rows
        ]

        language_map = {lang[0]: lang[1] for lang in languages}
        subcontractor_languages = []
        for language_id, proficiency in zip(language_ids, language_proficiencies):
            if language_id:
                subcontractor_languages.append((int(language_id), language_map.get(int(language_id), ""), proficiency))

        cert_map = {cert[0]: cert[1] for cert in certifications}
        subcontractor_certifications = []
        for cert_id, obtained_date, expiry_date, issuing_body in zip(
            certification_ids,
            obtained_dates,
            expiry_dates,
            issuing_bodies,
        ):
            if cert_id:
                subcontractor_certifications.append((
                    int(cert_id),
                    cert_map.get(int(cert_id), ""),
                    obtained_date or None,
                    expiry_date or None,
                    issuing_body or None,
                ))

        subcontractor = {
            "subcontractor_id": subcontractor_id,
            "company_name": company_name,
            "contact_name": contact_name,
            "email": email,
            "phone": phone,
            "birth_date": birth_date,
            "title": title,
            "years_experience": years_experience,
            "residence_country_id": residence_country_id,
            "resource_id": to_int(form.get("resource_id")),
            "resource_status": resource_status,
            "is_willing_to_travel": is_willing_to_travel,
            "bio_text": bio_text,
            "cv_text": cv_text,
        }

        return templates.TemplateResponse("subcontractors.html", {
            "request": request,
            "active": "subcontractors",
            "countries": countries,
            "certifications": certifications,
            "languages": languages,
            "subcontractors": subcontractors,
            "subcontractor": subcontractor,
            "subcontractor_languages": subcontractor_languages,
            "subcontractor_certifications": subcontractor_certifications,
            "view_mode": False,
            "error": message,
        })

    try:
        conn.execute("BEGIN")
        if subcontractor_id:
            cursor.execute("""
                UPDATE Subcontractor
                SET company_name = ?, contact_name = ?, email = ?, phone = ?,
                    birth_date = ?, title = ?, years_experience = ?, residence_country_id = ?
                WHERE subcontractor_id = ?
            """, (
                company_name,
                contact_name,
                email,
                phone,
                birth_date,
                title,
                years_experience,
                residence_country_id,
                subcontractor_id,
            ))
            if cursor.rowcount == 0:
                conn.rollback()
                return RedirectResponse(url="/subcontractors", status_code=303)
        else:
            cursor.execute("""
                INSERT INTO Subcontractor
                (company_name, contact_name, email, phone, birth_date, title, years_experience, residence_country_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                company_name,
                contact_name,
                email,
                phone,
                birth_date,
                title,
                years_experience,
                residence_country_id,
            ))
            subcontractor_id = cursor.lastrowid

        cursor.execute("""
            SELECT resource_id
            FROM Resource
            WHERE subcontractor_id = ? AND resource_type = 'Subcontractor'
        """, (subcontractor_id,))
        resource_row = cursor.fetchone()

        if resource_row:
            resource_id = resource_row[0]
            cursor.execute("""
                UPDATE Resource
                SET status = ?, is_willing_to_travel = ?, bio_text = ?, cv_text = ?
                WHERE resource_id = ?
            """, (resource_status, is_willing_to_travel, bio_text, cv_text, resource_id))
        else:
            cursor.execute("""
                INSERT INTO Resource
                (resource_type, subcontractor_id, status, is_willing_to_travel, bio_text, cv_text)
                VALUES ('Subcontractor', ?, ?, ?, ?, ?)
            """, (subcontractor_id, resource_status, is_willing_to_travel, bio_text, cv_text))
            resource_id = cursor.lastrowid

        if language_ids:
            cursor.execute("DELETE FROM ResourceLanguage WHERE resource_id = ?", (resource_id,))
            for language_id, proficiency in zip(language_ids, language_proficiencies):
                if language_id:
                    cursor.execute("""
                        INSERT INTO ResourceLanguage (resource_id, language_id, proficiency_level)
                        VALUES (?, ?, ?)
                    """, (resource_id, int(language_id), proficiency))

        if certification_ids:
            cursor.execute("DELETE FROM ResourceCertification WHERE resource_id = ?", (resource_id,))
            for cert_id, obtained_date, expiry_date, issuing_body in zip(
                certification_ids,
                obtained_dates,
                expiry_dates,
                issuing_bodies,
            ):
                cursor.execute("""
                    INSERT INTO ResourceCertification
                    (resource_id, certification_id, obtained_date, expiry_date, issuing_body)
                    VALUES (?, ?, ?, ?, ?)
                """, (resource_id, int(cert_id), obtained_date or None, expiry_date or None, issuing_body or None))

        if add_cert_name:
            cursor.execute("SELECT certification_id FROM Certification WHERE name = ?", (add_cert_name,))
            cert_row = cursor.fetchone()
            if cert_row:
                add_cert_id = cert_row[0]
            else:
                cursor.execute("INSERT INTO Certification (name) VALUES (?)", (add_cert_name,))
                add_cert_id = cursor.lastrowid

            add_obtained_date = form.get("add_certification_obtained_date") or None
            add_expiry_date = form.get("add_certification_expiry_date") or None
            add_issuing_body = form.get("add_certification_issuing_body") or None
            cursor.execute("""
                INSERT OR IGNORE INTO ResourceCertification
                (resource_id, certification_id, obtained_date, expiry_date, issuing_body)
                VALUES (?, ?, ?, ?, ?)
            """, (resource_id, add_cert_id, add_obtained_date, add_expiry_date, add_issuing_body))

        conn.commit()
    except Exception:
        conn.rollback()
        return render_error("Unable to save subcontractor. Please try again.")
    finally:
        conn.close()

    return RedirectResponse(url=f"/subcontractors?subcontractor_id={subcontractor_id}", status_code=303)

@app.post("/subcontractors/deactivate")
async def subcontractors_deactivate(request: Request):
    form = await request.form()

    def to_int(value):
        if value is None or value == "":
            return None
        return int(value)

    subcontractor_id = to_int(form.get("subcontractor_id"))
    if not subcontractor_id:
        return RedirectResponse(url="/subcontractors", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT resource_id
            FROM Resource
            WHERE subcontractor_id = ? AND resource_type = 'Subcontractor'
        """, (subcontractor_id,))
        resource_row = cursor.fetchone()
        if resource_row:
            cursor.execute("""
                UPDATE Resource
                SET status = 'Inactive'
                WHERE resource_id = ?
            """, (resource_row[0],))
        else:
            cursor.execute("""
                INSERT INTO Resource (resource_type, subcontractor_id, status)
                VALUES ('Subcontractor', ?, 'Inactive')
            """, (subcontractor_id,))
        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url=f"/subcontractors?subcontractor_id={subcontractor_id}", status_code=303)

@app.post("/subcontractors/delete")
async def subcontractors_delete(request: Request):
    form = await request.form()

    def to_int(value):
        if value is None or value == "":
            return None
        return int(value)

    subcontractor_id = to_int(form.get("subcontractor_id"))
    if not subcontractor_id:
        return RedirectResponse(url="/subcontractors", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    def render_error(message):
        cursor.execute("SELECT country_id, name FROM Country ORDER BY name")
        countries = cursor.fetchall()
        cursor.execute("SELECT certification_id, name FROM Certification ORDER BY name")
        certifications = cursor.fetchall()
        cursor.execute("SELECT language_id, name FROM Language ORDER BY name")
        languages = cursor.fetchall()
        cursor.execute("""
            SELECT
                s.subcontractor_id,
                s.company_name,
                s.contact_name,
                s.email,
                s.phone,
                s.birth_date,
                s.title,
                s.years_experience,
                c.name AS country_name,
                r.resource_id,
                r.status AS resource_status
            FROM Subcontractor s
            LEFT JOIN Country c ON s.residence_country_id = c.country_id
            LEFT JOIN Resource r
                ON r.subcontractor_id = s.subcontractor_id
               AND r.resource_type = 'Subcontractor'
            ORDER BY s.company_name, s.contact_name
        """)
        rows = cursor.fetchall()

        from collections import namedtuple

        SubcontractorRow = namedtuple(
            "SubcontractorRow",
            [
                "subcontractor_id",
                "company_name",
                "contact_name",
                "email",
                "phone",
                "birth_date",
                "title",
                "years_experience",
                "country_name",
                "resource_id",
                "resource_status",
            ],
        )

        subcontractors = [
            SubcontractorRow(
                sc_id,
                sc_company,
                sc_contact,
                sc_email,
                sc_phone,
                sc_birth,
                sc_title,
                sc_years,
                sc_country,
                sc_resource_id,
                sc_status,
            )
            for (
                sc_id,
                sc_company,
                sc_contact,
                sc_email,
                sc_phone,
                sc_birth,
                sc_title,
                sc_years,
                sc_country,
                sc_resource_id,
                sc_status,
            ) in rows
        ]

        return templates.TemplateResponse("subcontractors.html", {
            "request": request,
            "active": "subcontractors",
            "countries": countries,
            "certifications": certifications,
            "languages": languages,
            "subcontractors": subcontractors,
            "subcontractor": None,
            "subcontractor_languages": [],
            "subcontractor_certifications": [],
            "view_mode": False,
            "error": message,
        })

    try:
        conn.execute("BEGIN")
        cursor.execute("""
            SELECT resource_id
            FROM Resource
            WHERE subcontractor_id = ? AND resource_type = 'Subcontractor'
        """, (subcontractor_id,))
        resource_row = cursor.fetchone()
        resource_id = resource_row[0] if resource_row else None

        if resource_id:
            cursor.execute("SELECT COUNT(*) FROM Assignment WHERE resource_id = ?", (resource_id,))
            if cursor.fetchone()[0] > 0:
                conn.rollback()
                return render_error("Subcontractor cannot be deleted because they have assignments.")

            cursor.execute("DELETE FROM ResourceLanguage WHERE resource_id = ?", (resource_id,))
            cursor.execute("DELETE FROM ResourceCertification WHERE resource_id = ?", (resource_id,))
            cursor.execute("DELETE FROM Resource WHERE resource_id = ?", (resource_id,))

        cursor.execute("DELETE FROM Subcontractor WHERE subcontractor_id = ?", (subcontractor_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        return render_error("Unable to delete subcontractor. Please try again.")
    finally:
        conn.close()

    return RedirectResponse(url="/subcontractors", status_code=303)

@app.get("/projects", response_class=HTMLResponse)
async def projects(request: Request, project_id: int = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT client_id, name FROM Client ORDER BY name")
        clients = cursor.fetchall()

        cursor.execute("SELECT country_id, name FROM Country ORDER BY name")
        countries = cursor.fetchall()

        cursor.execute("SELECT business_line_id, name FROM BusinessLine ORDER BY name")
        business_lines = cursor.fetchall()

        cursor.execute("""
            SELECT
                p.project_id,
                p.name,
                cl.name AS client_name,
                co.name AS country_name,
                bl.name AS business_line_name,
                p.status,
                p.start_date,
                p.end_date
            FROM Project p
            LEFT JOIN Client cl ON p.client_id = cl.client_id
            LEFT JOIN Country co ON p.country_id = co.country_id
            LEFT JOIN ProjectBusinessLine pbl
              ON pbl.project_id = p.project_id
             AND pbl.primary_flag = 1
            LEFT JOIN BusinessLine bl ON bl.business_line_id = pbl.business_line_id
            ORDER BY p.name
        """)
        rows = cursor.fetchall()

        project = None
        project_business_lines = []
        if project_id:
            cursor.execute("""
                SELECT
                    project_id,
                    name,
                    client_id,
                    country_id,
                    description,
                    status,
                    start_date,
                    end_date
                FROM Project
                WHERE project_id = ?
            """, (project_id,))
            row = cursor.fetchone()
            if row:
                project = {
                    "project_id": row[0],
                    "name": row[1],
                    "client_id": row[2],
                    "country_id": row[3],
                    "description": row[4],
                    "status": row[5],
                    "start_date": row[6],
                    "end_date": row[7],
                }

                cursor.execute("""
                    SELECT
                        bl.business_line_id,
                        bl.name
                    FROM ProjectBusinessLine pbl
                    JOIN BusinessLine bl ON bl.business_line_id = pbl.business_line_id
                    WHERE pbl.project_id = ?
                    ORDER BY pbl.primary_flag DESC, bl.name
                """, (project_id,))
                project_business_lines = cursor.fetchall()
    finally:
        conn.close()

    from collections import namedtuple

    ProjectRow = namedtuple(
        "ProjectRow",
        [
            "project_id",
            "name",
            "client_name",
            "country_name",
            "business_line_name",
            "status",
            "start_date",
            "end_date",
        ],
    )

    projects = [
        ProjectRow(
            project_id,
            name,
            client_name,
            country_name,
            business_line_name,
            status,
            start_date,
            end_date,
        )
        for (
            project_id,
            name,
            client_name,
            country_name,
            business_line_name,
            status,
            start_date,
            end_date,
        ) in rows
    ]

    return templates.TemplateResponse("projects.html", {
        "request": request,
        "active": "projects",
        "projects": projects,
        "clients": clients,
        "countries": countries,
        "business_lines": business_lines,
        "project": project,
        "project_business_lines": project_business_lines,
    })

@app.get("/projects/export")
async def projects_export():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                p.name,
                cl.name AS client_name,
                co.name AS country_name,
                bl.name AS business_line_name,
                p.status,
                p.start_date,
                p.end_date
            FROM Project p
            LEFT JOIN Client cl ON p.client_id = cl.client_id
            LEFT JOIN Country co ON p.country_id = co.country_id
            LEFT JOIN ProjectBusinessLine pbl
              ON pbl.project_id = p.project_id
             AND pbl.primary_flag = 1
            LEFT JOIN BusinessLine bl ON bl.business_line_id = pbl.business_line_id
            ORDER BY p.name
        """)
        rows = cursor.fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Project Name",
        "Client Name",
        "Country",
        "Primary Business Line",
        "Status",
        "Start Date",
        "End Date",
    ])
    for name, client_name, country_name, business_line_name, status, start_date, end_date in rows:
        writer.writerow([
            name or "",
            client_name or "",
            country_name or "",
            business_line_name or "Not assigned",
            status or "Planned",
            start_date or "",
            end_date or "",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=projects_export.csv"},
    )

@app.get("/clients", response_class=HTMLResponse)
async def clients(request: Request, client_id: int = None, mode: str = None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT sector_id, name FROM Sector ORDER BY name")
        sectors = cursor.fetchall()

        cursor.execute("""
            SELECT
                c.client_id,
                c.name,
                cs.sector_id,
                s.name AS sector_name
            FROM Client c
            LEFT JOIN ClientSector cs
              ON cs.client_id = c.client_id
             AND cs.primary_flag = 1
            LEFT JOIN Sector s
              ON s.sector_id = cs.sector_id
            ORDER BY c.name
        """)
        rows = cursor.fetchall()
    finally:
        conn.close()

    from collections import namedtuple

    ClientRow = namedtuple(
        "ClientRow",
        [
            "client_id",
            "name",
            "sector_id",
            "sector_name",
        ],
    )

    clients = [
        ClientRow(client_id, name, sector_id, sector_name)
        for (client_id, name, sector_id, sector_name) in rows
    ]

    return templates.TemplateResponse("clients.html", {
        "request": request,
        "active": "clients",
        "clients": clients,
        "client_id": client_id,
        "sectors": sectors,
        "view_mode": (mode == "view"),
    })

@app.get("/clients/export")
async def clients_export():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                c.name,
                s.name AS sector_name
            FROM Client c
            LEFT JOIN ClientSector cs
              ON cs.client_id = c.client_id
             AND cs.primary_flag = 1
            LEFT JOIN Sector s
              ON s.sector_id = cs.sector_id
            ORDER BY c.name
        """)
        rows = cursor.fetchall()
    finally:
        conn.close()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Client Name", "Sector", "Country"])
    for name, sector_name in rows:
        writer.writerow([
            name or "",
            sector_name or "Not assigned",
            "Not available",
        ])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=clients_export.csv"},
    )

@app.post("/clients")
async def clients_post(request: Request):
    form = await request.form()

    def to_int(value):
        if value is None or value == "":
            return None
        return int(value)

    client_id = to_int(form.get("client_id"))
    name = form.get("name", "").strip()
    contact_email = form.get("contact_email", "").strip() or None
    contact_phone = form.get("contact_phone", "").strip() or None
    sector_id = to_int(form.get("sector_id"))

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        conn.execute("BEGIN")
        if client_id:
            cursor.execute("""
                UPDATE Client
                SET name = ?, contact_email = ?, contact_phone = ?
                WHERE client_id = ?
            """, (name, contact_email, contact_phone, client_id))
        else:
            cursor.execute("""
                INSERT INTO Client (name, contact_email, contact_phone)
                VALUES (?, ?, ?)
            """, (name, contact_email, contact_phone))
            client_id = cursor.lastrowid

        cursor.execute("DELETE FROM ClientSector WHERE client_id = ?", (client_id,))
        if sector_id:
            cursor.execute("""
                INSERT INTO ClientSector (client_id, sector_id, primary_flag)
                VALUES (?, ?, 1)
            """, (client_id, sector_id))

        conn.commit()
    finally:
        conn.close()

    return RedirectResponse(url=f"/clients?client_id={client_id}", status_code=303)

@app.post("/clients/delete")
async def clients_delete(request: Request):
    form = await request.form()

    def to_int(value):
        if value is None or value == "":
            return None
        return int(value)

    client_id = to_int(form.get("client_id"))
    if not client_id:
        return RedirectResponse(url="/clients", status_code=303)

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    def render_error(message):
        cursor.execute("SELECT sector_id, name FROM Sector ORDER BY name")
        sectors = cursor.fetchall()
        cursor.execute("""
            SELECT
                c.client_id,
                c.name,
                cs.sector_id,
                s.name AS sector_name
            FROM Client c
            LEFT JOIN ClientSector cs
              ON cs.client_id = c.client_id
             AND cs.primary_flag = 1
            LEFT JOIN Sector s
              ON s.sector_id = cs.sector_id
            ORDER BY c.name
        """)
        rows = cursor.fetchall()

        from collections import namedtuple

        ClientRow = namedtuple(
            "ClientRow",
            [
                "client_id",
                "name",
                "sector_id",
                "sector_name",
            ],
        )

        clients = [
            ClientRow(client_id, name, sector_id, sector_name)
            for (client_id, name, sector_id, sector_name) in rows
        ]

        return templates.TemplateResponse("clients.html", {
            "request": request,
            "active": "clients",
            "clients": clients,
            "client_id": None,
            "sectors": sectors,
            "view_mode": False,
            "error": message,
        })

    try:
        conn.execute("BEGIN")
        cursor.execute("SELECT COUNT(*) FROM Project WHERE client_id = ?", (client_id,))
        if cursor.fetchone()[0] > 0:
            conn.rollback()
            return render_error("Client cannot be deleted because projects reference it.")

        cursor.execute("DELETE FROM ClientSector WHERE client_id = ?", (client_id,))
        cursor.execute("DELETE FROM Client WHERE client_id = ?", (client_id,))
        conn.commit()
    except Exception:
        conn.rollback()
        return render_error("Unable to delete client. Please try again.")
    finally:
        conn.close()

    return RedirectResponse(url="/clients", status_code=303)

@app.get("/assignments", response_class=HTMLResponse)
async def assignments(request: Request):
    return templates.TemplateResponse("assignments.html", {"request": request, "active": "assignments"})

@app.get("/reference-data/countries", response_class=HTMLResponse)
async def countries(request: Request, search: str = None, page: int = 1):
    countries, total = get_countries(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    return templates.TemplateResponse("reference_data.html", {
        "request": request, 
        "active": "reference",
        "countries": countries,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page
    })

@app.get("/reference-data", response_class=HTMLResponse)
async def reference_data(request: Request, search: str = None, page: int = 1):
    countries, total = get_countries(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    return templates.TemplateResponse("reference_data.html", {
        "request": request, 
        "active": "reference",
        "countries": countries,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page
    })

@app.get("/reference-data/departments", response_class=HTMLResponse)
async def departments_get(request: Request, search: str = None, page: int = 1, edit: int = None, message: str = None, error: str = None):
    departments, total = get_departments(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_dept = None
    if edit:
        editing_dept = get_department(edit)
    return templates.TemplateResponse("departments.html", {
        "request": request, 
        "active": "reference",
        "departments": departments,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_dept": editing_dept,
        "message": message,
        "error": error
    })

@app.post("/reference-data/departments")
async def departments_post(request: Request):
    form = await request.form()
    action = form.get("action")
    search = form.get("search", "")
    page = int(form.get("page", 1))
    
    if action == "add":
        name = form.get("name", "").strip()
        if not name:
            ctx = get_departments_context(search, page, error="Department name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("departments.html", ctx)
        success, msg = add_department(name)
        if success:
            ctx = get_departments_context(search, page, message="Department added successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("departments.html", ctx)
        else:
            ctx = get_departments_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("departments.html", ctx)
    
    elif action == "update":
        department_id = int(form.get("department_id"))
        name = form.get("name", "").strip()
        if not name:
            ctx = get_departments_context(search, page, edit=department_id, error="Department name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("departments.html", ctx)
        success, msg = update_department(department_id, name)
        if success:
            ctx = get_departments_context(search, page, message="Department updated successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("departments.html", ctx)
        else:
            ctx = get_departments_context(search, page, edit=department_id, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("departments.html", ctx)
    
    elif action == "delete":
        department_id = int(form.get("department_id"))
        success, msg = delete_department(department_id)
        if success:
            ctx = get_departments_context(search, page, message="Department deleted successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("departments.html", ctx)
        else:
            ctx = get_departments_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("departments.html", ctx)
    
    ctx = get_departments_context(search, page, error="Invalid action.")
    ctx["request"] = request
    return templates.TemplateResponse("departments.html", ctx)

def get_departments_context(search, page, edit=None, message=None, error=None):
    departments, total = get_departments(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_dept = None
    if edit:
        editing_dept = get_department(edit)
    return {
        "active": "reference",
        "departments": departments,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_dept": editing_dept,
        "message": message,
        "error": error
    }

@app.get("/reference-data/sectors", response_class=HTMLResponse)
async def sectors_get(request: Request, search: str = None, page: int = 1, edit: int = None, message: str = None, error: str = None):
    sectors, total = get_sectors(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_sector = None
    if edit:
        editing_sector = get_sector(edit)
    return templates.TemplateResponse("sectors.html", {
        "request": request, 
        "active": "reference",
        "sectors": sectors,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_sector": editing_sector,
        "message": message,
        "error": error
    })

@app.post("/reference-data/sectors")
async def sectors_post(request: Request):
    form = await request.form()
    action = form.get("action")
    search = form.get("search", "")
    page = int(form.get("page", 1))
    
    if action == "add":
        name = form.get("name", "").strip()
        description = form.get("description", "").strip()
        if not name:
            ctx = get_sectors_context(search, page, error="Sector name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("sectors.html", ctx)
        success, msg = add_sector(name, description)
        if success:
            ctx = get_sectors_context(search, page, message="Sector added successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("sectors.html", ctx)
        else:
            ctx = get_sectors_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("sectors.html", ctx)
    
    elif action == "update":
        sector_id = int(form.get("sector_id"))
        name = form.get("name", "").strip()
        description = form.get("description", "").strip()
        if not name:
            ctx = get_sectors_context(search, page, edit=sector_id, error="Sector name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("sectors.html", ctx)
        success, msg = update_sector(sector_id, name, description)
        if success:
            ctx = get_sectors_context(search, page, message="Sector updated successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("sectors.html", ctx)
        else:
            ctx = get_sectors_context(search, page, edit=sector_id, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("sectors.html", ctx)
    
    elif action == "delete":
        sector_id = int(form.get("sector_id"))
        success, msg = delete_sector(sector_id)
        if success:
            ctx = get_sectors_context(search, page, message="Sector deleted successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("sectors.html", ctx)
        else:
            ctx = get_sectors_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("sectors.html", ctx)
    
    ctx = get_sectors_context(search, page, error="Invalid action.")
    ctx["request"] = request
    return templates.TemplateResponse("sectors.html", ctx)

def get_sectors_context(search, page, edit=None, message=None, error=None):
    sectors, total = get_sectors(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_sector = None
    if edit:
        editing_sector = get_sector(edit)
    return {
        "active": "reference",
        "sectors": sectors,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_sector": editing_sector,
        "message": message,
        "error": error
    }

@app.get("/reference-data/business-lines", response_class=HTMLResponse)
async def business_lines_get(request: Request, search: str = None, page: int = 1, edit: int = None, message: str = None, error: str = None):
    business_lines, total = get_business_lines(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_bl = None
    if edit:
        editing_bl = get_business_line(edit)
    return templates.TemplateResponse("business_lines.html", {
        "request": request, 
        "active": "reference",
        "business_lines": business_lines,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_bl": editing_bl,
        "message": message,
        "error": error
    })

@app.post("/reference-data/business-lines")
async def business_lines_post(request: Request):
    form = await request.form()
    action = form.get("action")
    search = form.get("search", "")
    page = int(form.get("page", 1))
    
    if action == "add":
        name = form.get("name", "").strip()
        description = form.get("description", "").strip()
        if not name:
            ctx = get_business_lines_context(search, page, error="Business Line name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("business_lines.html", ctx)
        success, msg = add_business_line(name, description)
        if success:
            ctx = get_business_lines_context(search, page, message="Business Line added successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("business_lines.html", ctx)
        else:
            ctx = get_business_lines_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("business_lines.html", ctx)
    
    elif action == "update":
        business_line_id = int(form.get("business_line_id"))
        name = form.get("name", "").strip()
        description = form.get("description", "").strip()
        if not name:
            ctx = get_business_lines_context(search, page, edit=business_line_id, error="Business Line name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("business_lines.html", ctx)
        success, msg = update_business_line(business_line_id, name, description)
        if success:
            ctx = get_business_lines_context(search, page, message="Business Line updated successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("business_lines.html", ctx)
        else:
            ctx = get_business_lines_context(search, page, edit=business_line_id, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("business_lines.html", ctx)
    
    elif action == "delete":
        business_line_id = int(form.get("business_line_id"))
        success, msg = delete_business_line(business_line_id)
        if success:
            ctx = get_business_lines_context(search, page, message="Business Line deleted successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("business_lines.html", ctx)
        else:
            ctx = get_business_lines_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("business_lines.html", ctx)
    
    ctx = get_business_lines_context(search, page, error="Invalid action.")
    ctx["request"] = request
    return templates.TemplateResponse("business_lines.html", ctx)

def get_business_lines_context(search, page, edit=None, message=None, error=None):
    business_lines, total = get_business_lines(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_bl = None
    if edit:
        editing_bl = get_business_line(edit)
    return {
        "active": "reference",
        "business_lines": business_lines,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_bl": editing_bl,
        "message": message,
        "error": error
    }

@app.get("/reference-data/languages", response_class=HTMLResponse)
async def languages_get(request: Request, search: str = None, page: int = 1, edit: int = None, message: str = None, error: str = None):
    languages, total = get_languages(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_lang = None
    if edit:
        editing_lang = get_language(edit)
    return templates.TemplateResponse("languages.html", {
        "request": request, 
        "active": "reference",
        "languages": languages,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_lang": editing_lang,
        "message": message,
        "error": error
    })

@app.post("/reference-data/languages")
async def languages_post(request: Request):
    form = await request.form()
    action = form.get("action")
    search = form.get("search", "")
    page = int(form.get("page", 1))
    
    if action == "add":
        name = form.get("name", "").strip()
        iso_code = form.get("iso_code", "").strip()
        if not name:
            ctx = get_languages_context(search, page, error="Language name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("languages.html", ctx)
        # Auto-fill iso_code if matches known
        known = {'Arabic': 'ar', 'English': 'en', 'French': 'fr', 'German': 'de', 'Spanish': 'es', 'Chinese': 'zh', 'Turkish': 'tr', 'Portuguese': 'pt'}
        if name in known and not iso_code:
            iso_code = known[name]
        success, msg = add_language(name, iso_code)
        if success:
            ctx = get_languages_context(search, page, message="Language added successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("languages.html", ctx)
        else:
            ctx = get_languages_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("languages.html", ctx)
    
    elif action == "update":
        language_id = int(form.get("language_id"))
        name = form.get("name", "").strip()
        iso_code = form.get("iso_code", "").strip()
        if not name:
            ctx = get_languages_context(search, page, edit=language_id, error="Language name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("languages.html", ctx)
        success, msg = update_language(language_id, name, iso_code)
        if success:
            ctx = get_languages_context(search, page, message="Language updated successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("languages.html", ctx)
        else:
            ctx = get_languages_context(search, page, edit=language_id, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("languages.html", ctx)
    
    elif action == "delete":
        language_id = int(form.get("language_id"))
        success, msg = delete_language(language_id)
        if success:
            ctx = get_languages_context(search, page, message="Language deleted successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("languages.html", ctx)
        else:
            ctx = get_languages_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("languages.html", ctx)
    
    ctx = get_languages_context(search, page, error="Invalid action.")
    ctx["request"] = request
    return templates.TemplateResponse("languages.html", ctx)

def get_languages_context(search, page, edit=None, message=None, error=None):
    languages, total = get_languages(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_lang = None
    if edit:
        editing_lang = get_language(edit)
    return {
        "active": "reference",
        "languages": languages,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_lang": editing_lang,
        "message": message,
        "error": error
    }

@app.get("/reference-data/certifications", response_class=HTMLResponse)
async def certifications_get(request: Request, search: str = None, page: int = 1, edit: int = None, message: str = None, error: str = None):
    certifications, total = get_certifications(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_cert = None
    if edit:
        editing_cert = get_certification(edit)
    return templates.TemplateResponse("certifications.html", {
        "request": request, 
        "active": "reference",
        "certifications": certifications,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_cert": editing_cert,
        "message": message,
        "error": error
    })

@app.post("/reference-data/certifications")
async def certifications_post(request: Request):
    form = await request.form()
    action = form.get("action")
    search = form.get("search", "")
    page = int(form.get("page", 1))
    
    if action == "add":
        name = form.get("name", "").strip()
        issuing_body = form.get("issuing_body", "").strip()
        if not name:
            ctx = get_certifications_context(search, page, error="Certification name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("certifications.html", ctx)
        success, msg = add_certification(name, issuing_body)
        if success:
            ctx = get_certifications_context(search, page, message="Certification added successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("certifications.html", ctx)
        else:
            ctx = get_certifications_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("certifications.html", ctx)
    
    elif action == "update":
        certification_id = int(form.get("certification_id"))
        name = form.get("name", "").strip()
        issuing_body = form.get("issuing_body", "").strip()
        if not name:
            ctx = get_certifications_context(search, page, edit=certification_id, error="Certification name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("certifications.html", ctx)
        success, msg = update_certification(certification_id, name, issuing_body)
        if success:
            ctx = get_certifications_context(search, page, message="Certification updated successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("certifications.html", ctx)
        else:
            ctx = get_certifications_context(search, page, edit=certification_id, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("certifications.html", ctx)
    
    elif action == "delete":
        certification_id = int(form.get("certification_id"))
        success, msg = delete_certification(certification_id)
        if success:
            ctx = get_certifications_context(search, page, message="Certification deleted successfully.")
            ctx["request"] = request
            return templates.TemplateResponse("certifications.html", ctx)
        else:
            ctx = get_certifications_context(search, page, error=msg)
            ctx["request"] = request
            return templates.TemplateResponse("certifications.html", ctx)
    
    ctx = get_certifications_context(search, page, error="Invalid action.")
    ctx["request"] = request
    return templates.TemplateResponse("certifications.html", ctx)

def get_certifications_context(search, page, edit=None, message=None, error=None):
    certifications, total = get_certifications(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_cert = None
    if edit:
        editing_cert = get_certification(edit)
    return {
        "active": "reference",
        "certifications": certifications,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_cert": editing_cert,
        "message": message,
        "error": error
    }

# Roles functions
def seed_roles():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Role")
    if cursor.fetchone()[0] == 0:
        roles = [
            ("Manager", "Responsible for team management and oversight"),
            ("Developer", "Software development and coding"),
            ("Analyst", "Data analysis and reporting"),
            ("Consultant", "Advisory and consulting services"),
            ("Administrator", "System administration and maintenance")
        ]
        cursor.executemany("INSERT INTO Role (name, description) VALUES (?, ?)", roles)
        conn.commit()
    conn.close()

def get_roles(search=None, page=1, per_page=10):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    offset = (page - 1) * per_page
    query = "SELECT role_id, name, description FROM Role"
    params = []
    if search:
        query += " WHERE name LIKE ?"
        params.append(f"%{search}%")
    query += " ORDER BY name LIMIT ? OFFSET ?"
    params.extend([per_page, offset])
    cursor.execute(query, params)
    roles = cursor.fetchall()
    cursor.execute(f"SELECT COUNT(*) FROM Role{' WHERE name LIKE ?' if search else ''}", params[:1] if search else [])
    total = cursor.fetchone()[0]
    conn.close()
    return roles, total

def add_role(name, description):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Role WHERE name = ?", (name,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False, "Role name already exists."
    cursor.execute("INSERT INTO Role (name, description) VALUES (?, ?)", (name, description or None))
    conn.commit()
    conn.close()
    return True, None

def update_role(role_id, name, description):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM Role WHERE name = ? AND role_id != ?", (name, role_id))
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False, "Role name already exists."
    cursor.execute("UPDATE Role SET name = ?, description = ? WHERE role_id = ?", (name, description or None, role_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated, None

def delete_role(role_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # Check if role is referenced in Assignment table
    cursor.execute("SELECT COUNT(*) FROM Assignment WHERE role_id = ?", (role_id,))
    if cursor.fetchone()[0] > 0:
        conn.close()
        return False, "Cannot delete role as it is assigned to assignments."
    cursor.execute("DELETE FROM Role WHERE role_id = ?", (role_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted, None

def get_role(role_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT role_id, name, description FROM Role WHERE role_id = ?", (role_id,))
    role = cursor.fetchone()
    conn.close()
    return role

@app.get("/reference-data/roles", response_class=HTMLResponse)
async def roles_page(request: Request, search: str = None, page: int = 1, edit: int = None):
    seed_roles()
    ctx = get_roles_context(search, page, edit)
    ctx["request"] = request
    return templates.TemplateResponse("roles.html", ctx)

@app.post("/reference-data/roles", response_class=HTMLResponse)
async def roles_post(request: Request):
    form = await request.form()
    action = form.get("action")
    search = form.get("search", "")
    page = int(form.get("page", 1))
    
    if action == "add":
        name = form.get("name")
        description = form.get("description")
        if not name:
            ctx = get_roles_context(search, page, error="Role name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("roles.html", ctx)
        success, error = add_role(name, description)
        if success:
            ctx = get_roles_context(search, page, message="Role added successfully.")
        else:
            ctx = get_roles_context(search, page, error=error)
        ctx["request"] = request
        return templates.TemplateResponse("roles.html", ctx)
    
    elif action == "update":
        role_id = form.get("role_id")
        name = form.get("name")
        description = form.get("description")
        if not name:
            ctx = get_roles_context(search, page, edit=role_id, error="Role name is required.")
            ctx["request"] = request
            return templates.TemplateResponse("roles.html", ctx)
        success, error = update_role(role_id, name, description)
        if success:
            ctx = get_roles_context(search, page, message="Role updated successfully.")
        else:
            ctx = get_roles_context(search, page, edit=role_id, error=error)
        ctx["request"] = request
        return templates.TemplateResponse("roles.html", ctx)
    
    elif action == "delete":
        role_id = form.get("role_id")
        success, error = delete_role(role_id)
        if success:
            ctx = get_roles_context(search, page, message="Role deleted successfully.")
        else:
            ctx = get_roles_context(search, page, error=error)
        ctx["request"] = request
        return templates.TemplateResponse("roles.html", ctx)
    
    ctx = get_roles_context(search, page, error="Invalid action.")
    ctx["request"] = request
    return templates.TemplateResponse("roles.html", ctx)

def get_roles_context(search, page, edit=None, message=None, error=None):
    roles, total = get_roles(search, page)
    per_page = 10
    total_pages = (total + per_page - 1) // per_page
    start_page = max(1, page - 2)
    end_page = min(total_pages, page + 2)
    editing_role = None
    if edit:
        editing_role = get_role(edit)
    return {
        "active": "reference",
        "roles": roles,
        "search": search or "",
        "page": page,
        "total_pages": total_pages,
        "total": total,
        "start_page": start_page,
        "end_page": end_page,
        "editing_role": editing_role,
        "message": message,
        "error": error
    }
