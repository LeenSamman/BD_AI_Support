# BD_AI_Support

Perfect, let’s turn everything we discussed into **one master “Source of Truth” plan** — from A to Z.

You can literally paste this into a `TECH_PLAN.md` and work from it step by step.

---

# 🧾 Project: Robust Multi-Modal Extraction Pipeline

**Version:** 1.0
**Target:** Local laptop (CPU / Apple Silicon)
**Core Stack:**

* **Docling** → parsing, layout, OCR
* **Qwen2.5-VL-7B-Instruct (local)** → vision + reasoning + JSON extraction
* **Python** → orchestration, merging, validation, persistence

---

## 0. Scope & Goals

### 0.1 Primary Goal

Build a **local, reliable pipeline** that converts messy documents (PDF, DOCX, PPTX, scanned, charts, tables) into **clean, structured JSON** suitable for a database or downstream apps (e.g. RFP analyzer).

### 0.2 Key Design Principles

* **Accuracy > speed**
* **Modular stages** (each stage has clear input/output)
* **Deterministic merging** (same input → same output)
* **Traceability & debuggability** (logs + intermediate artifacts)
* **Hardware-aware** (safe on a normal laptop)

### 0.3 Out-of-scope (for now)

* Distributed / cluster processing
* Fine-tuning Qwen
* Cloud deployment

---

## 1. High-Level Architecture

Your final pipeline (conceptually):

1. **Ingestion & Format Detection**
2. **Docling Parsing & OCR → Markdown + Layout + Images**
3. **Vision Enrichment for Charts/Visuals** (Qwen Vision)
4. **Sliding Window Chunking with Overlap**
5. **Semantic Extraction to JSON** (Qwen Text)
6. **Deduplication & Merge Across Chunks**
7. **Validation, Quality Checks & Confidence**
8. **Persistence (JSON files / DB rows)**
9. **Logging, Error Handling & Progress Reporting**

---

## 2. Project Structure (Recommended)

```text
bd_doc_pipeline/
│
├─ README.md
├─ TECH_PLAN.md                # This spec
├─ pyproject.toml / requirements.txt
│
├─ config/
│   ├─ pipeline_config.yaml    # batch size, overlap, model URLs, etc.
│   └─ schema_rfp.json         # strict JSON schema for extraction
│
├─ data/
│   ├─ input/                  # input documents
│   ├─ intermediate/           # markdown, crops, enriched_md
│   └─ output/                 # final JSON files
│
├─ src/
│   ├─ main.py                 # CLI entry point
│   ├─ config_loader.py
│   ├─ models/
│   │   ├─ qwen_client.py      # HTTP client to local Qwen server
│   │   └─ schema_types.py     # Pydantic models for outputs
│   ├─ pipeline/
│   │   ├─ ingestion.py        # format detection
│   │   ├─ docling_reader.py   # markdown + layout + images
│   │   ├─ vision_enrich.py    # charts → descriptions (Qwen vision)
│   │   ├─ chunking.py         # sliding window logic
│   │   ├─ extract_text.py     # Qwen text JSON extraction
│   │   ├─ merge_results.py    # dedup, conflict resolution
│   │   ├─ validation.py       # JSON validation, sanity checks
│   │   └─ persist.py          # save final outputs
│   ├─ utils/
│   │   ├─ logging_utils.py
│   │   ├─ progress.py
│   │   └─ errors.py
│   └─ tests/
│       ├─ test_small_docs.py
│       ├─ test_scanned_docs.py
│       └─ test_evil_pdfs.py   # badly formatted docs
```

---

## 3. Environment & Dependencies

### 3.1 Python & Core Libs

* Python 3.10+
* Core packages:

  * `docling`
  * `requests` or `httpx`
  * `pydantic` (for schemas)
  * `tqdm` (progress bar)
  * `pyyaml`
  * `rich` (optional, for pretty logging)
  * `orjson` or `ujson` (fast JSON)

### 3.2 Qwen2.5-VL-7B-Instruct Setup

* Run Qwen locally behind an HTTP API (e.g. `http://localhost:1234/v1/chat/completions`)
* Same endpoint used for:

  * **Vision mode:** pass `image` in messages
  * **Text mode:** pass Markdown text only
* Configuration fields:

  * `model_name: "qwen2.5-vl-7b-instruct"`
  * `temperature: 0.1–0.3`
  * `max_tokens` tuned per use case
* `qwen_client.py` should:

  * implement `call_vision(prompt, image_bytes)`
  * implement `call_text(prompt, text)`
  * handle retries, timeouts, logging of raw responses

---

## 4. Data Models & Internal Representations

### 4.1 Core Internal Types (Pydantic or dataclasses)

* `DocumentMeta`

  * `id`, `filename`, `num_pages`, `created_at`
* `PageInfo`

  * `page_number`, `markdown_segment`, `images`, `tables`
* `Chunk`

  * `chunk_id`, `start_page`, `end_page`, `text`
* `ExtractionItem`

  * `key_fields` (for dedup)
  * `raw_json` (from Qwen)
  * `page_refs`
  * `confidence`
* `FinalResult`

  * `status` (`success/partial/error`)
  * `data` (list of structured items)
  * `errors` (list of issues)
  * `meta` (timings, pages processed, etc.)

### 4.2 Domain Schema (e.g. RFP style)

For example (you can refine later):

```json
{
  "rfp_summary": {
    "title": "string|null",
    "client_name": "string|null",
    "country": "string|null",
    "issue_date": "string|null",
    "due_date": "string|null"
  },
  "requirements": {
    "company_qualification": [...],
    "team_qualification": [...],
    "technical": [...],
    "financial": [...],
    "submission": [...],
    "evaluation_criteria": [...],
    "risks": [...]
  }
}
```

This schema lives in `config/schema_rfp.json` and is passed into the Qwen prompt.

---

## 5. Pipeline Stages (A–Z)

### 5.1 Stage A – Ingestion & Format Detection

**File:** `pipeline/ingestion.py`
**Input:** file path
**Output:** `DocumentMeta`, raw bytes, format enum (`pdf/docx/pptx/image`)

Tasks:

* Detect extension, maybe use `python-magic` for MIME sniffing.
* Validate path, handle missing/corrupt files.
* Count pages (for PDFs via Docling or fallback if needed).

---

### 5.2 Stage B – Docling Parsing & OCR

**File:** `pipeline/docling_reader.py`
**Input:** `DocumentMeta`, file content
**Output:**

* `markdown_full` (entire doc as MD)
* `page_markdown_list` (`[{"page":1,"text":...}, ...]`)
* `image_crops` with metadata:

  ```json
  {
    "id": "fig_1",
    "page": 3,
    "crop_path": "data/intermediate/doc1/fig_1.png",
    "type": "chart|diagram|table_image|unknown"
  }
  ```

Settings (in config):

* `max_pages_per_call: 20`
* `pipeline_options.generate_picture_images = True`
* `pipeline_options.images_scale = 1.0` (2.0 if OCR too weak)
* Explicit GC:

  * `del intermediate; gc.collect()` after each 20-page block

---

### 5.3 Stage C – Vision Enrichment (Charts & Visuals)

**File:** `pipeline/vision_enrich.py`
**Input:** `page_markdown_list`, `image_crops`
**Output:** `markdown_enriched` per page

Logic:

1. For each page:

   * Find occurrences of `![Figure...](...)` or `[Picture: ...]`.
   * Map them to `image_crops` based on page + index.

2. For each mapped image:

   * Call `Qwen Vision` with prompt like:

     > "You are a data extraction assistant. Analyze this chart and return **only JSON** with:
     >
     > * `chart_title`
     > * `x_axis_label`
     > * `y_axis_label`
     > * `data_points` (list of `{x_label, value}`)
     >   Also include a `summary` field with 2–3 sentences."

3. Replace the original figure tag in Markdown with:

   ```text
   [GRAPH_DESCRIPTION]
   {JSON HERE}
   [/GRAPH_DESCRIPTION]
   ```

   or with a structured text block.

🎯 Goal: **The entire document becomes text+JSON, no “silent” charts.**

---

### 5.4 Stage D – Sliding Window Chunking

**File:** `pipeline/chunking.py`
**Input:** `markdown_enriched` with per-page info
**Output:** list of `Chunk` objects

Config:

* `BATCH_SIZE_PAGES = 10`
* `OVERLAP_PAGES = 2`

Algorithm example for N pages:

* Chunk 0: pages 1–10
* Chunk 1: pages 9–18
* Chunk 2: pages 17–26
* Stop when start > N

Each `Chunk` has:

* `chunk_id`
* `start_page`, `end_page`
* `text` = concatenated Markdown for these pages
* `page_indices`

---

### 5.5 Stage E – Semantic Extraction (Qwen Text Mode)

**File:** `pipeline/extract_text.py`
**Input:** `Chunk.text`, JSON schema
**Output:** list of raw `ExtractionItem` objects

Key elements:

1. Build **system prompt**:

   > "You are a precise data extraction system.
   > Read the following enriched Markdown from an RFP.
   > Return ONLY valid JSON that matches this schema:
   > (insert schema)
   > Rules:
   >
   > * If a field is missing, set it to null.
   > * Do not invent or hallucinate values.
   > * Do not include any explanation or commentary.
   > * Do not wrap JSON in markdown or prose."

2. Wrap in robust parser:

   * Retry 1–2 times if JSON parsing fails.
   * Strip any leading text, parse from first `{` to last `}`.

3. Attach metadata:

   ```python
   ExtractionItem(
       key_fields=...,   # for dedup
       raw_json=...,
       pages=[chunk.start_page, ..., chunk.end_page],
       chunk_id=chunk.chunk_id,
       confidence=initial_conf
   )
   ```

---

### 5.6 Stage F – Deduplication & Merge

**File:** `pipeline/merge_results.py`
**Input:** list of `ExtractionItem` across all chunks
**Output:** `FinalResult.data` (merged domain JSON)

Strategy:

1. **Define item_key** by domain:

   * e.g. for requirements: `"{category}-{normalize(text[:40])}"`
   * for months: `"month-"+month_name`

2. Use structure:

   ```python
   item_versions = defaultdict(list)
   for item in all_items:
       key = build_key(item)
       item_versions[key].append(item)
   ```

3. For each key:

   * Choose **middle chunk version** (best context due to overlap), OR
   * Choose the version with more filled fields / higher confidence.

4. Construct final JSON in target schema shape.

---

### 5.7 Stage G – Validation & Quality Checks

**File:** `pipeline/validation.py`
**Input:** `FinalResult.data`, original `markdown_enriched`
**Output:** possibly adjusted data + warnings

Checks:

1. **Schema validation:** using Pydantic or JSON Schema.

2. **Sanity rules:** e.g.

   * date formats valid?
   * numeric fields not negative where impossible.

3. **Coverage heuristics:**

   * Are there many numbers/dates in text that never appear in JSON? (could indicate missed extraction)

4. **Optional LLM-based cross-check:**

   * Ask Qwen:

     > "Compare this JSON with the source text and list any missing obvious values or mismatches."

5. Create a `validation_report` (could be just a dict).

---

### 5.8 Stage H – Persistence

**File:** `pipeline/persist.py`
**Input:** `FinalResult`
**Output:** `.json` file and/or DB writes

Basic path:

* Save to: `data/output/<document_id>.json`
* Optionally:

  * Insert rows into SQLite/Postgres later using a separate module.

Also store intermediate artifacts (for debugging):

* `data/intermediate/<doc_id>/markdown_raw.md`
* `data/intermediate/<doc_id>/markdown_enriched.md`
* `data/intermediate/<doc_id>/vision_logs.json`

---

### 5.9 Stage I – Logging, Errors & Progress

**Files:** `utils/logging_utils.py`, `utils/progress.py`, `utils/errors.py`

Add:

* Logging levels: `INFO`, `WARNING`, `ERROR`, `DEBUG`
* Log per stage:

  * start/end time
  * number of pages processed
  * number of items extracted
  * failures/retries
* CLI progress via `tqdm` or simple percentage:

  * `Docling: [#####-----] 50%`
  * `Extraction: Chunk 2/8`

Error handling:

* All I/O and model calls wrapped in try/except.
* Partial success allowed:

  * `status: "partial"` with list of `failed_chunks`.

---

## 6. Implementation Roadmap (Phased)

### Phase 1 – MVP: Text-Only PDFs → JSON

* [ ] Implement ingestion + Docling → Markdown for PDF only
* [ ] Implement basic chunking (no overlap OK for MVP)
* [ ] Implement Qwen text extraction for small docs (≤10 pages)
* [ ] Simple merge (no complex dedup)
* [ ] Write output to JSON file
* [ ] Test on:

  * a small clean PDF (no charts)
  * one simple RFP

**Goal:** end-to-end path working for simple cases.

---

### Phase 2 – Add Overlap & Robust JSON Handling

* [ ] Add overlapping sliding window logic
* [ ] Implement schema-based system prompt
* [ ] Implement `safe_parse_json()` with repair & retry
* [ ] Implement proper dedup using keys + middle-chunk strategy
* [ ] Add basic validation & logging
* [ ] Test on:

  * PDF with tables across page boundaries
  * 30–50 page reports

---

### Phase 3 – Vision Enrichment Layer

* [ ] Enable `generate_picture_images` in Docling
* [ ] Save crops into `data/intermediate/...`
* [ ] Implement `vision_enrich.py`:

  * map figures to crops
  * call Qwen Vision
  * inject `[GRAPH_DESCRIPTION]` blocks
* [ ] Update extraction prompts to consider `[GRAPH_DESCRIPTION]` sections
* [ ] Test on:

  * docs with 1–3 charts
  * verify chart values appear in JSON

---

### Phase 4 – Robustness & Quality

* [ ] Add retry policies for:

  * Qwen Vision
  * Qwen Text
* [ ] Add `confidence` scores by heuristics:

  * number of agreeing chunks
  * completeness of fields
* [ ] Implement coverage heuristic (detect if many numbers are unreferenced)
* [ ] Add progress reporting & structured logs
* [ ] Build a small “evil PDFs” test set:

  * scanned, rotated, complex tables, long files

---

### Phase 5 – Integration & Optional UI

* [ ] Decide on integration target:

  * CLI only
  * FastAPI service (e.g. `POST /extract`)
* [ ] If API:

  * add `api.py` and route that:

    * takes file upload
    * kicks off pipeline
    * returns JSON + optional validation report
* [ ] Optionally add simple UI:

  * HTML page where you upload a file
  * show extraction summary & errors

---

## 7. Acceptance Criteria (When is it “Done”?)

You can consider this pipeline **v1 complete** when:

1. ✅ It processes:

   * PDFs (digital & scanned)
   * DOCX
   * PPTX with charts and images
2. ✅ It never crashes on 100–200 page docs; worst case = partial result + errors logged.
3. ✅ Charts’ numeric content appears in final JSON when clearly readable.
4. ✅ Overlap ensures tables split over pages are not lost.
5. ✅ JSON strictly follows your schema (no random keys).
6. ✅ Logs and intermediate artifacts are enough to debug any bad output.
7. ✅ You can add a **new domain schema** (e.g., “Financial Report” vs “RFP”) by:

   * adding a new JSON schema file
   * changing the system prompt
   * not touching core pipeline code

---
