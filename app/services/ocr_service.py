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
import os
import shutil

import fitz  # PyMuPDF
import pytesseract
from PIL import Image

from app.config import settings
from app.logging_config import get_logger


logger = get_logger(__name__)


# ============================================================
# TESSERACT CONFIGURATION
# ============================================================

def configure_tesseract():
    """
    Configure Tesseract for both Windows and Linux/Docker.

    Priority:
      1. Valid TESSERACT_CMD from application settings
      2. Windows standard installation paths
      3. Tesseract found in PATH (Linux/Docker)
    """

    # --------------------------------------------------------
    # 1. Check configured Tesseract path
    # --------------------------------------------------------

    configured_path = getattr(
        settings,
        "TESSERACT_CMD",
        None
    )

    if configured_path:

        configured_path = str(configured_path).strip()

        # On Linux/Docker, do not use a Windows path.
        if os.name != "nt" and (
            "\\" in configured_path
            or configured_path.lower().startswith("c:")
            or configured_path.lower().startswith("d:")
        ):

            logger.warning(
                "Ignoring Windows Tesseract path inside Linux/Docker: %s",
                configured_path
            )

        elif os.path.isfile(configured_path):

            pytesseract.pytesseract.tesseract_cmd = configured_path

            logger.info(
                "Using configured Tesseract executable: %s",
                configured_path
            )

            return

        else:

            logger.warning(
                "Configured Tesseract path does not exist: %s",
                configured_path
            )

    # --------------------------------------------------------
    # 2. Windows
    # --------------------------------------------------------

    if os.name == "nt":

        windows_paths = [
            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        ]

        for path in windows_paths:

            if os.path.isfile(path):

                pytesseract.pytesseract.tesseract_cmd = path

                logger.info(
                    "Using Windows Tesseract executable: %s",
                    path
                )

                return

    # --------------------------------------------------------
    # 3. Linux / Docker
    # --------------------------------------------------------

    linux_path = shutil.which("tesseract")

    if linux_path:

        pytesseract.pytesseract.tesseract_cmd = linux_path

        logger.info(
            "Using Linux/Docker Tesseract executable: %s",
            linux_path
        )

        return

    # --------------------------------------------------------
    # 4. Tesseract not found
    # --------------------------------------------------------

    raise RuntimeError(
        "Tesseract executable not found. "
        "Install Tesseract or set a valid TESSERACT_CMD."
    )


configure_tesseract()


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

        logger.info(
            "Tesseract OCR completed successfully. Text length=%s",
            len(text.strip())
        )

        return text or ""

    except Exception:

        logger.exception(
            "Tesseract OCR failed on an image"
        )

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

        dpi = getattr(
            settings,
            "OCR_DPI",
            200
        )

        logger.info(
            "Rasterizing PDF page for OCR at DPI=%s",
            dpi
        )

        pix = page.get_pixmap(
            dpi=dpi,
            alpha=False
        )

        img = Image.frombytes(
            "RGB",
            (pix.width, pix.height),
            pix.samples
        )

        text = _ocr_image(img)

        logger.info(
            "PDF page OCR finished. Text length=%s",
            len(text.strip())
        )

        return text

    except Exception:

        logger.exception(
            "OCR failed for PDF page"
        )

        return ""


# ============================================================
# MAIN EXTRACTION FUNCTION
# ============================================================

def extract_pages(
    file_path: str,
    ext: str
) -> list[PageText]:
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

    logger.info(
        "Starting text extraction: file=%s ext=%s",
        file_path,
        ext
    )

    # ========================================================
    # JPG / JPEG / PNG
    # ========================================================

    if ext in (
        ".jpg",
        ".jpeg",
        ".png"
    ):

        try:

            with Image.open(file_path) as img:

                # Ensure image is loaded before leaving
                # context manager.
                img.load()

                logger.info(
                    "Image opened successfully: size=%s mode=%s",
                    img.size,
                    img.mode
                )

                text = _ocr_image(
                    img.convert("RGB")
                )

            logger.info(
                "Image extraction completed: text_length=%s",
                len(text.strip())
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

            logger.info(
                "PDF opened successfully: pages=%s",
                len(doc)
            )

        except Exception:

            logger.exception(
                "Failed to open PDF: %s",
                file_path
            )

            raise

        try:

            for i, page in enumerate(
                doc,
                start=1
            ):

                # ------------------------------------------------
                # STEP 1: Try native PDF text extraction
                # ------------------------------------------------

                try:

                    native_text = (
                        page.get_text("text")
                        or ""
                    )

                    logger.info(
                        "Page %s native text length=%s",
                        i,
                        len(native_text.strip())
                    )

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

                if len(
                    native_text.strip()
                ) >= MIN_NATIVE_CHARS_PER_PAGE:

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

                    ocr_text = _ocr_pdf_page(
                        page
                    )

                    pages.append(
                        PageText(
                            page_number=i,
                            text=ocr_text,
                            source="ocr"
                        )
                    )

                    logger.info(
                        "Page %s OCR text length=%s",
                        i,
                        len(ocr_text.strip())
                    )

        finally:

            doc.close()

            logger.info(
                "PDF closed successfully: %s",
                file_path
            )

        logger.info(
            "PDF extraction completed: pages=%s total_text_length=%s",
            len(pages),
            sum(
                len(page.text or "")
                for page in pages
            )
        )

        return pages

    # ========================================================
    # UNSUPPORTED FILE TYPE
    # ========================================================

    raise ValueError(
        f"Unsupported extension for OCR: {ext}"
    )