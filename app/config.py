"""
Central configuration for the Document Intelligence platform.
All values can be overridden via environment variables / .env file.
"""

import os

from dotenv import load_dotenv


load_dotenv()


class Settings:

    # ============================================================
    # GENERAL
    # ============================================================

    APP_NAME: str = "Document Intelligence Platform"

    ENV: str = os.getenv(
        "ENV",
        "development"
    )

    # ============================================================
    # DATABASE
    # ============================================================

    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./docintel.db"
    )

    # ============================================================
    # FILE CONSTRAINTS
    # ============================================================

    MAX_PAGES: int = int(
        os.getenv(
            "MAX_PAGES",
            "3"
        )
    )

    MAX_FILE_SIZE_MB: int = int(
        os.getenv(
            "MAX_FILE_SIZE_MB",
            "15"
        )
    )

    ALLOWED_EXTENSIONS = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png"
    }

    # ============================================================
    # LLM - GOOGLE GEMINI
    # ============================================================

    GEMINI_API_KEY: str = os.getenv(
        "GEMINI_API_KEY",
        ""
    )

    GEMINI_MODEL: str = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash"
    )

    # ============================================================
    # OCR
    # ============================================================

    # IMPORTANT:
    #
    # Do not hardcode a Windows Tesseract path here.
    #
    # Docker/Linux will automatically find Tesseract using
    # shutil.which("tesseract") inside ocr_service.py.
    #
    # If you ever want to explicitly configure Tesseract,
    # set TESSERACT_CMD through the environment.
    #

    TESSERACT_CMD: str = os.getenv(
        "TESSERACT_CMD",
        ""
    )

    OCR_DPI: int = int(
        os.getenv(
            "OCR_DPI",
            "300"
        )
    )

    # ============================================================
    # STORAGE
    # ============================================================

    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        "./storage/uploads"
    )

    # ============================================================
    # FINANCIAL VALIDATION
    # ============================================================

    NUMERIC_TOLERANCE: float = float(
        os.getenv(
            "NUMERIC_TOLERANCE",
            "0.01"
        )
    )


# ================================================================
# CREATE SETTINGS INSTANCE
# ================================================================

settings = Settings()


# ================================================================
# CREATE UPLOAD DIRECTORY
# ================================================================

os.makedirs(
    settings.UPLOAD_DIR,
    exist_ok=True
)