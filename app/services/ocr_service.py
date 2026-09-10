"""
Extracts raw text (per page) from PDFs and images.

Strategy:
  - Native PDF: pull embedded text with PyMuPDF. If a page has little/no
    text layer, fall back to OCR on a rasterised image of that page.
  - JPG/JPEG/PNG: always run OCR using Tesseract.

Returns a list of PageText(page_number, text, source) so the extraction
and evidence/grounding layers know which page each snippet came from.
"""

from dataclasses import dataclass

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from app.config import settings
from app.logging_config import get_logger


logger = get_logger(__name__)


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

# Your Tesseract installation is located inside a folder named
# "tesseract.exe", and the actual executable is inside that folder.
#
# Verified executable:
# C:\Program Files\Tesseract-OCR\tesseract.exe\tesseract.exe
#
# We first try to use the value from .env/config.
# If it is missing, we fall back to the verified Windows path.

TESSERACT_FALLBACK_PATH = (
    r"C:\Program Files\Tesseract-OCR\tesseract.exe\tesseract.exe"
)

tesseract_cmd = getattr(settings, "TESSERACT_CMD", None)

if tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
else:
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_FALLBACK_PATH


# ============================================================
# CONSTANTS
# ============================================================

# If a PDF page contains at least this many characters,
# we consider its embedded/native text usable.
MIN_NATIVE_CHARS_PER_PAGE = 20


# ============================================================
# DATA MODEL
# ============================================================

@dataclass
class PageText:
    """
    Represents extracted text from one document page.

    page_number:
        1-based page number.

    text:
        Extracted text.

    source:
        "native" -> extracted directly from PDF text layer.
        "ocr"    -> extracted using Tesseract OCR.
    """

    page_number: int
    text: str
    source: str


# ============================================================
# OCR
# ============================================================

def _ocr_image(image: Image.Image) -> str:
    """
    Run Tesseract OCR on a PIL image.

    Returns:
        Extracted text as a string.

    If OCR fails:
        Logs the exception and returns an empty string.
    """

    try:
        # Convert to RGB to avoid issues with RGBA,
        # grayscale, palette, etc.
        image = image.convert("RGB")

        text = pytesseract.image_to_string(
            image,
            config="--psm 6"
        )

        return text or ""

    except Exception:
        logger.exception("Tesseract OCR failed on an image")
        return ""


# ============================================================
# PDF PAGE OCR
# ============================================================

def _ocr_pdf_page(page) -> str:
    """
    Rasterize a PDF page and run OCR on it.

    Uses OCR_DPI from application settings.
    """

    try:
        dpi = getattr(settings, "OCR_DPI", 200)

        pix = page.get_pixmap(
            dpi=dpi,
            alpha=False
        )

        img = Image.frombytes(
            "RGB",
            (pix.width, pix.height),
            pix.samples
        )

        return _ocr_image(img)

    except Exception:
        logger.exception("OCR failed for PDF page")
        return ""


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def extract_pages(file_path: str, ext: str) -> list[PageText]:
    """
    Extract text page-by-page from supported documents.

    Supported:
        .pdf
        .jpg
        .jpeg
        .png

    PDF:
        1. Try native text extraction.
        2. If insufficient text exists, use OCR.

    Images:
        Always use OCR.

    Returns:
        list[PageText]
    """

    # Normalize extension
    ext = ext.lower().strip()

    # ========================================================
    # JPG / JPEG / PNG
    # ========================================================

    if ext in (".jpg", ".jpeg", ".png"):

        try:
            with Image.open(file_path) as img:

                # Ensure image is loaded before leaving context manager.
                img.load()

                text = _ocr_image(
                    img.convert("RGB")
                )

            return [
                PageText(
                    page_number=1,
                    text=text,
                    source="ocr"
                )
            ]

        except Exception:
            logger.exception(
                "Failed to open/process image: %s",
                file_path
            )

            return [
                PageText(
                    page_number=1,
                    text="",
                    source="ocr"
                )
            ]

    # ========================================================
    # PDF
    # ========================================================

    if ext == ".pdf":

        pages: list[PageText] = []

        try:
            doc = fitz.open(file_path)

        except Exception:
            logger.exception(
                "Failed to open PDF: %s",
                file_path
            )
            raise

        try:

            for i, page in enumerate(doc, start=1):

                # ------------------------------------------------
                # STEP 1: Try native PDF text extraction
                # ------------------------------------------------

                try:
                    native_text = page.get_text("text") or ""

                except Exception:
                    logger.exception(
                        "Native PDF text extraction failed "
                        "for page %s",
                        i
                    )

                    native_text = ""

                # ------------------------------------------------
                # STEP 2: Use native text if sufficient
                # ------------------------------------------------

                if len(native_text.strip()) >= MIN_NATIVE_CHARS_PER_PAGE:

                    pages.append(
                        PageText(
                            page_number=i,
                            text=native_text,
                            source="native"
                        )
                    )

                    logger.info(
                        "Page %s extracted using native PDF text",
                        i
                    )

                # ------------------------------------------------
                # STEP 3: Otherwise OCR the page
                # ------------------------------------------------

                else:

                    logger.info(
                        "Page %s has insufficient native text; "
                        "using OCR",
                        i
                    )

                    ocr_text = _ocr_pdf_page(page)

                    pages.append(
                        PageText(
                            page_number=i,
                            text=ocr_text,
                            source="ocr"
                        )
                    )

        finally:
            doc.close()

        return pages

    # ========================================================
    # UNSUPPORTED FILE TYPE
    # ========================================================

    raise ValueError(
        f"Unsupported extension for OCR: {ext}"
    )