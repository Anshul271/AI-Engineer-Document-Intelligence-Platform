import os
import tempfile

from app.services.validation import validate_file


def _write_temp(content: bytes, suffix: str) -> str:
    fd, path = tempfile.mkstemp(suffix=suffix)
    with os.fdopen(fd, "wb") as f:
        f.write(content)
    return path


def test_rejects_unsupported_extension():
    path = _write_temp(b"hello world", ".txt")
    result = validate_file(path, "note.txt")
    assert result.is_valid is False
    assert any("Unsupported" in e for e in result.errors)


def test_rejects_empty_file():
    path = _write_temp(b"", ".pdf")
    result = validate_file(path, "empty.pdf")
    assert result.is_valid is False
    assert any("empty" in e.lower() for e in result.errors)


def test_rejects_corrupted_pdf():
    path = _write_temp(b"not a real pdf", ".pdf")
    result = validate_file(path, "broken.pdf")
    assert result.is_valid is False
