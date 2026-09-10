import datetime as dt
import os
import time
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.logging_config import get_logger
from app.models import ProcessedDocument
from app.schemas import (
    DocumentProcessResponse,
    DocumentSummary,
    DocumentType,
    FileValidationResult,
    ProcessingMetadata,
    ProcessingStatus,
)
from app.services.extraction_service import extract_structured_data
from app.services.financial_validation import run_financial_validations
from app.services.ocr_service import extract_pages
from app.services.validation import validate_file

logger = get_logger(__name__)
router = APIRouter()


@router.get("/health", tags=["system"])
def health():
    return {"status": "ok", "service": settings.APP_NAME}


@router.post("/documents/process", response_model=DocumentProcessResponse, tags=["documents"])
async def process_document(
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    start = time.time()
    document_name = file.filename or f"upload-{uuid.uuid4().hex}"
    temp_path = os.path.join(settings.UPLOAD_DIR, f"{uuid.uuid4().hex}_{document_name}")

    try:
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
    except Exception:
        logger.exception("Failed to persist uploaded file")
        raise HTTPException(status_code=500, detail="Could not read uploaded file.")

    # 1. File validation
    file_validation = validate_file(temp_path, document_name)
    if not file_validation.is_valid:
        _persist(db, document_name, document_type.value, ProcessingStatus.rejected,
                  file_validation, {}, [], None, "; ".join(file_validation.errors))
        return DocumentProcessResponse(
            document_name=document_name,
            document_type=document_type,
            status=ProcessingStatus.rejected,
            file_validation=file_validation,
            extracted_data={},
            tables=[],
            financial_validations=[],
            processing_metadata=ProcessingMetadata(processed_at=dt.datetime.utcnow().isoformat()),
            error="; ".join(file_validation.errors),
        )

    # 2. OCR / text extraction
    try:
        pages = extract_pages(temp_path, file_validation.file_type)
    except Exception as exc:  # noqa: BLE001
        logger.exception("OCR stage failed for %s", document_name)
        return _fail(db, document_name, document_type, file_validation, "OCR/text extraction failed.")

    # 3. LLM structured extraction
    try:
        extraction = extract_structured_data(document_type.value, pages)
    except RuntimeError as exc:
        logger.error("Extraction unavailable: %s", exc)
        return _fail(db, document_name, document_type, file_validation, str(exc))
    except Exception:
        logger.exception("Extraction stage crashed for %s", document_name)
        return _fail(db, document_name, document_type, file_validation, "Structured extraction failed unexpectedly.")

    fields = extraction.get("fields", {})
    tables = extraction.get("tables", [])

    # 4. Deterministic financial validation
    financial_results = run_financial_validations(document_type.value, fields, tables)

    processing_ms = int((time.time() - start) * 1000)
    metadata = ProcessingMetadata(
        ocr_engine="tesseract+pymupdf",
        extraction_model=extraction.get("model"),
        processing_time_ms=processing_ms,
        processed_at=dt.datetime.utcnow().isoformat(),
    )

    status = ProcessingStatus.success
    _persist(db, document_name, document_type.value, status, file_validation,
              fields, tables, financial_results, None, metadata)

    return DocumentProcessResponse(
        document_name=document_name,
        document_type=document_type,
        status=status,
        file_validation=file_validation,
        extracted_data=fields,
        tables=tables,
        financial_validations=financial_results,
        processing_metadata=metadata,
        error=None,
    )


def _fail(db, document_name, document_type, file_validation, error_msg):
    metadata = ProcessingMetadata(processed_at=dt.datetime.utcnow().isoformat())
    _persist(db, document_name, document_type.value, ProcessingStatus.failed,
              file_validation, {}, [], [], error_msg, metadata)
    return DocumentProcessResponse(
        document_name=document_name,
        document_type=document_type,
        status=ProcessingStatus.failed,
        file_validation=file_validation,
        extracted_data={},
        tables=[],
        financial_validations=[],
        processing_metadata=metadata,
        error=error_msg,
    )


def _persist(db: Session, document_name, document_type, status, file_validation,
             fields, tables, financial_results, error, metadata=None):
    try:
        row = ProcessedDocument(
            document_name=document_name,
            document_type=document_type,
            status=status.value if hasattr(status, "value") else status,
            file_validation=file_validation.model_dump() if hasattr(file_validation, "model_dump") else file_validation,
            extracted_data={"fields": fields, "tables": tables},
            financial_validations=[r.model_dump() for r in financial_results] if financial_results else [],
            processing_metadata=metadata.model_dump() if hasattr(metadata, "model_dump") else metadata,
            error=error,
        )
        db.add(row)
        db.commit()
    except Exception:
        logger.exception("Failed to persist processed document to DB")
        db.rollback()


@router.get("/documents", response_model=list[DocumentSummary], tags=["documents"])
def list_documents(db: Session = Depends(get_db)):
    rows = db.query(ProcessedDocument).order_by(desc(ProcessedDocument.created_at)).all()
    return [
        DocumentSummary(
            id=r.id, document_name=r.document_name, document_type=r.document_type,
            status=r.status, created_at=r.created_at.isoformat(),
        )
        for r in rows
    ]


@router.get("/documents/{document_name}", tags=["documents"])
def get_document_by_name(document_name: str, db: Session = Depends(get_db)):
    row = (
        db.query(ProcessedDocument)
        .filter(ProcessedDocument.document_name == document_name)
        .order_by(desc(ProcessedDocument.created_at))
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="No processed result found for this document name.")
    return {
        "id": row.id,
        "document_name": row.document_name,
        "document_type": row.document_type,
        "status": row.status,
        "file_validation": row.file_validation,
        "extracted_data": row.extracted_data,
        "financial_validations": row.financial_validations,
        "processing_metadata": row.processing_metadata,
        "error": row.error,
        "created_at": row.created_at.isoformat(),
    }
