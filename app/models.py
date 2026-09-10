"""
Database models.

ProcessedDocument stores one row per processing request. If a document with
the same document_name is re-processed, a new row is inserted and the
GET-by-name endpoint returns the most recent one (ordered by created_at).
"""
import datetime as dt

from sqlalchemy import Column, Integer, String, DateTime, JSON, Text

from app.database import Base


class ProcessedDocument(Base):
    __tablename__ = "processed_documents"

    id = Column(Integer, primary_key=True, index=True)
    document_name = Column(String(255), index=True, nullable=False)
    document_type = Column(String(64), index=True, nullable=False)
    status = Column(String(32), index=True, nullable=False)  # SUCCESS / FAILED / REJECTED
    file_validation = Column(JSON, nullable=True)
    extracted_data = Column(JSON, nullable=True)
    financial_validations = Column(JSON, nullable=True)
    processing_metadata = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)
