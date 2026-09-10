"""
Central configuration for the Document Intelligence platform.
All values can be overridden via environment variables / .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # --- General ---
    APP_NAME: str = "Document Intelligence Platform"
    ENV: str = os.getenv("ENV", "development")

    # --- Database ---
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./docintel.db"
    )

    # --- File constraints ---
    MAX_PAGES: int = int(
        os.getenv("MAX_PAGES", "3")
    )

    MAX_FILE_SIZE_MB: int = int(
        os.getenv("MAX_FILE_SIZE_MB", "15")
    )

    ALLOWED_EXTENSIONS = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png"
    }

    # --- LLM (Google Gemini) ---
    GEMINI_API_KEY: str = os.getenv(
        "GEMINI_API_KEY",
        ""
    )

    GEMINI_MODEL: str = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash"
    )

    # --- OCR ---
    TESSERACT_CMD: str = os.getenv(
        "TESSERACT_CMD",
        r"C:\Program Files\Tesseract-OCR\tesseract.exe\tesseract.exe"
    )

    OCR_DPI: int = int(
        os.getenv("OCR_DPI", "300")
    )

    # --- Storage ---
    UPLOAD_DIR: str = os.getenv(
        "UPLOAD_DIR",
        "./storage/uploads"
    )

    # --- Financial validation tolerance ---
    NUMERIC_TOLERANCE: float = float(
        os.getenv("NUMERIC_TOLERANCE", "0.01")
    )


settings = Settings()

os.makedirs(
    settings.UPLOAD_DIR,
    exist_ok=True
)