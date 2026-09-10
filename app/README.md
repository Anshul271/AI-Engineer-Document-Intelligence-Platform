# Document Intelligence Platform

Intelligent extraction, validation and API platform for **Invoices, Balance
Sheets, Profit & Loss statements and Cash Flow statements** (PDF / JPG / PNG,
up to 3 pages).

## 1. Solution Overview & Architecture

```
Browser (frontend/index.html)
        │  multipart upload (document_type + file)
        ▼
FastAPI backend (app/main.py)
        │
        ├─ 1. app/services/validation.py     → file type, size, integrity, page-count checks
        ├─ 2. app/services/ocr_service.py     → native PDF text (PyMuPDF) or OCR (Tesseract)
        ├─ 3. app/services/extraction_service.py → Claude LLM → structured fields + tables + evidence
        ├─ 4. app/services/financial_validation.py → deterministic arithmetic checks (never LLM)
        └─ 5. app/models.py / database.py     → SQLite (or Postgres/MySQL) persistence
        │
        ▼
JSON response ─── stored ─── surfaced on the dashboard (frontend) & GET APIs
```

Design principle: **each concern lives in its own module** (validation, OCR,
extraction, financial validation, persistence, API routing) so failures are
isolated, logged and never crash the whole request.

The LLM is used **only** to read the document and return structured
key/value + table data with evidence (page + source snippet) — it never
performs arithmetic. All financial checks (e.g. `subtotal + tax == total`,
`assets == liabilities + equity`) are computed in plain Python so results are
reproducible and explainable, and unavailable fields resolve to
`NOT_APPLICABLE` rather than a guessed value.

## 2. Technology Stack

| Concern              | Choice                          | Why |
|-----------------------|----------------------------------|-----|
| API framework         | FastAPI                         | Async, automatic Swagger/OpenAPI, Pydantic validation built in |
| Native PDF text       | PyMuPDF (`fitz`)                | Fast, accurate text + page rasterisation for scanned pages |
| OCR                    | Tesseract (`pytesseract`)       | Free, open-source, works fully offline |
| Structured extraction  | Anthropic Claude (`messages` API) | Strong document-understanding + JSON-mode style output |
| Database               | SQLite (SQLAlchemy ORM)         | Zero-config for the assignment; `DATABASE_URL` swaps in Postgres/MySQL for prod |
| Frontend               | Plain HTML/CSS/JS                | No build step; meets "HTML/CSS, JS optional" requirement |

## 3. Local Setup

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Tesseract OCR (required for scanned PDFs / images)
#    Ubuntu/Debian:
sudo apt-get install -y tesseract-ocr
#    macOS:
brew install tesseract
#    Windows: install from https://github.com/UB-Mannheim/tesseract/wiki
#    and set TESSERACT_CMD in .env to the full exe path.

# 4. Configure environment variables
cp .env.example .env
# then edit .env and set ANTHROPIC_API_KEY=<your key>

# 5. Run the server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** for the frontend dashboard and
**http://localhost:8000/docs** for interactive Swagger/OpenAPI docs.

### Running tests

```bash
pytest -q
```

## 4. Environment Variables (`.env.example`)

See `.env.example` in the repo root — includes `DATABASE_URL`, `ANTHROPIC_API_KEY`,
`ANTHROPIC_MODEL`, `MAX_PAGES`, `MAX_FILE_SIZE_MB`, `TESSERACT_CMD`, `OCR_DPI`,
`UPLOAD_DIR`, `NUMERIC_TOLERANCE`. No real secrets are committed — only placeholders.

## 5. Deployed Application URLs

> _Fill these in after deploying (e.g. Render, Railway, Fly.io, or similar free tier):_
- Frontend URL: `<TODO>`
- Backend API base URL: `<TODO>`
- Swagger/OpenAPI URL: `<TODO>/docs`
- Public GitHub repository: `<TODO>`

## 6. API Reference

### `GET /api/health`
Liveness check. Returns `{"status": "ok", ...}`.

### `POST /api/documents/process`
Multipart form:
- `document_type`: one of `invoice`, `balance_sheet`, `profit_and_loss`, `cash_flow`
- `file`: PDF / JPG / PNG, ≤ 3 pages

```bash
curl -X POST http://localhost:8000/api/documents/process \
  -F "document_type=invoice" \
  -F "file=@sample_invoice.pdf"
```

Returns the mandatory structured JSON: `document_name`, `document_type`,
`status`, `file_validation`, `extracted_data` (key-value fields with
`value` / `page` / `source_text`), `tables`, `financial_validations`
(formula, inputs, calculated vs reported value, variance, PASS/FAIL/
NOT_APPLICABLE), and `processing_metadata`.

### `GET /api/documents`
Returns the list of processed documents (id, name, type, status, timestamp)
used to populate the dashboard.

```bash
curl http://localhost:8000/api/documents
```

### `GET /api/documents/{document_name}`
Returns the **latest** stored result for a given document name.

```bash
curl http://localhost:8000/api/documents/sample_invoice.pdf
```

## 7. OCR / Extraction Services Used

- **Native PDF text**: PyMuPDF (embedded text layer).
- **OCR fallback** (scanned PDFs & all JPG/PNG uploads): Tesseract via
  `pytesseract` (free, local, no API key needed).
- **Structured field/table extraction**: Anthropic Claude via the
  `anthropic` Python SDK (`ANTHROPIC_MODEL` in `.env`).

## 8. Financial Validation Rules & Tolerance

All checks are computed in `app/services/financial_validation.py` and are
**NOT_APPLICABLE** whenever a required field wasn't extracted:

| Document type | Check |
|---|---|
| Invoice | `subtotal + tax == total`; `sum(line item totals) == subtotal` |
| Balance Sheet | `total liabilities + total equity == total assets` |
| Profit & Loss | `revenue - cogs == gross profit`; `gross profit - operating expenses == net profit` |
| Cash Flow | `opening + operating + investing + financing == closing balance` |

Numeric tolerance: `max(1% of the reported value, 0.5)` absolute units,
configurable via `NUMERIC_TOLERANCE` in `.env`.

## 9. Database / Persistence

SQLite by default (`docintel.db`, created automatically on startup). Every
processing request inserts a new `processed_documents` row; the
GET-by-name endpoint returns the most recent row for that document name
(prior versions are retained, not overwritten). Swap in Postgres/MySQL by
changing `DATABASE_URL` — no code changes required (SQLAlchemy handles the
dialect).

## 10. Known Limitations

- Confidence scoring is not implemented (optional per the spec) — evidence
  (page + source snippet) is provided instead as the primary trust signal.
- Extraction quality depends on OCR quality for scanned/handwritten inputs.
- Line-item table extraction assumes reasonably well-formed tabular layout;
  extremely dense or multi-column financial statements may need prompt
  tuning per template.
- Single-tenant SQLite is fine for the assignment; concurrent write load in
  production should move to Postgres.

## 11. What I'd Change for Production

- Move to async/queued processing (Celery/RQ) instead of synchronous
  request handling for large documents.
- Add authentication/authorization on the API and per-user document scoping.
- Add a confidence-scoring layer (e.g. cross-checking OCR text against
  extracted values) and human-in-the-loop review for low-confidence fields.
- Move file storage to S3/Blob storage instead of local disk.
- Add structured request tracing (OpenTelemetry) instead of file-based logs.

## 12. AI Coding Assistants Used

Built with Claude (Anthropic) as a pair-programming assistant for
scaffolding the FastAPI service structure, the OCR/extraction pipeline, the
financial-validation module, the frontend dashboard, and the test suite.
