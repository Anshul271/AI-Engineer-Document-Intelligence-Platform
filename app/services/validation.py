"""
Input-control layer: validates file type, size, integrity and page count
BEFORE any OCR/extraction is attempted. This is deliberately separate from
document-type classification (the type is supplied by the caller).
"""
import os

import fitz  # PyMuPDF
from PIL import Image, UnidentifiedImageError

from app.config import settings
from app.logging_config import get_logger
from app.schemas import FileValidationResult

logger = get_logger(__name__)


def validate_file(file_path: str, original_filename: str) -> FileValidationResult:
    errors: list[str] = []
    ext = os.path.splitext(original_filename)[1].lower()

    if ext not in settings.ALLOWED_EXTENSIONS:
        errors.append(f"Unsupported file extension '{ext}'. Allowed: PDF, JPG, PNG.")
        logger.warning("Validation failed - unsupported extension: %s", ext)
        return FileValidationResult(is_valid=False, file_type=ext, errors=errors)

    size_bytes = os.path.getsize(file_path)
    if size_bytes == 0:
        errors.append("File is empty.")
        return FileValidationResult(is_valid=False, file_type=ext, size_bytes=0, errors=errors)

    if size_bytes > settings.MAX_FILE_SIZE_MB * 1024 * 1024:
        errors.append(f"File exceeds max size of {settings.MAX_FILE_SIZE_MB} MB.")

    page_count = None
    if ext == ".pdf":
        try:
            doc = fitz.open(file_path)
            page_count = doc.page_count
            doc.close()
            if page_count == 0:
                errors.append("PDF has no readable pages (possibly corrupted).")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Corrupt PDF detected: %s", original_filename)
            errors.append("PDF could not be opened - file appears corrupted.")
    else:
        try:
            with Image.open(file_path) as img:
                img.verify()
            page_count = 1
        except (UnidentifiedImageError, OSError):
            logger.exception("Corrupt image detected: %s", original_filename)
            errors.append("Image file could not be read - file appears corrupted.")

    if page_count is not None and page_count > settings.MAX_PAGES:
        errors.append(
            f"Document has {page_count} pages; only {settings.MAX_PAGES} pages are supported."
        )

    is_valid = len(errors) == 0
    result = FileValidationResult(
        is_valid=is_valid,
        file_type=ext,
        page_count=page_count,
        size_bytes=size_bytes,
        errors=errors,
    )
    logger.info("File validation for %s -> valid=%s errors=%s", original_filename, is_valid, errors)
    return result
