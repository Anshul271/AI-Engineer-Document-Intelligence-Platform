"""
Pydantic schemas defining the mandatory structured JSON contract described
in the case study (section 5.2): document name, supplied document type,
file validation, complete extracted data, financial validations, processing
status and processing metadata.
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    invoice = "invoice"
    balance_sheet = "balance_sheet"
    profit_and_loss = "profit_and_loss"
    cash_flow = "cash_flow"


class ProcessingStatus(str, Enum):
    success = "SUCCESS"
    partial = "PARTIAL_SUCCESS"
    failed = "FAILED"
    rejected = "REJECTED"


class ValidationStatus(str, Enum):
    pass_ = "PASS"
    fail = "FAIL"
    not_applicable = "NOT_APPLICABLE"


class FileValidationResult(BaseModel):
    is_valid: bool
    file_type: Optional[str] = None
    page_count: Optional[int] = None
    size_bytes: Optional[int] = None
    errors: list[str] = Field(default_factory=list)


class Evidence(BaseModel):
    page: Optional[int] = None
    source_text: Optional[str] = None


class ExtractedField(BaseModel):
    value: Any = None
    evidence: Optional[Evidence] = None
    confidence: Optional[float] = None


class FinancialValidationResult(BaseModel):
    check_name: str
    formula: str
    input_values: dict[str, Any] = Field(default_factory=dict)
    calculated_value: Optional[float] = None
    reported_value: Optional[float] = None
    variance: Optional[float] = None
    status: ValidationStatus


class ProcessingMetadata(BaseModel):
    ocr_engine: Optional[str] = None
    extraction_model: Optional[str] = None
    processing_time_ms: Optional[int] = None
    processed_at: str


class DocumentProcessResponse(BaseModel):
    document_name: str
    document_type: DocumentType
    status: ProcessingStatus
    file_validation: FileValidationResult
    extracted_data: dict[str, Any] = Field(default_factory=dict)
    tables: list[dict[str, Any]] = Field(default_factory=list)
    financial_validations: list[FinancialValidationResult] = Field(default_factory=list)
    processing_metadata: ProcessingMetadata
    error: Optional[str] = None


class DocumentSummary(BaseModel):
    id: int
    document_name: str
    document_type: str
    status: str
    created_at: str


class ErrorResponse(BaseModel):
    status: ProcessingStatus = ProcessingStatus.rejected
    error: str
    detail: Optional[str] = None
