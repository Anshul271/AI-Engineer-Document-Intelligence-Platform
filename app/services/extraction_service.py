"""
Turns raw OCR/native page text into structured key-value data using
Google Gemini.

The model is instructed to:
  - extract EVERY meaningful field/value it can see
  - never invent values -> return null when a field is not present
  - attach evidence (page number + short source snippet) to each value
  - return tabular/line-item data as structured arrays

The LLM is only responsible for extraction. Financial validation and
arithmetic checks are computed separately and deterministically.
"""

import json
import re

from google import genai

from app.config import settings
from app.logging_config import get_logger
from app.services.ocr_service import PageText


logger = get_logger(__name__)


# ============================================================
# GEMINI CLIENT
# ============================================================

_client = (
    genai.Client(api_key=settings.GEMINI_API_KEY)
    if settings.GEMINI_API_KEY
    else None
)


# ============================================================
# DOCUMENT TYPE GUIDANCE
# ============================================================

_DOC_TYPE_GUIDANCE = {
    "invoice": (
        "This is an INVOICE. Extract header fields (invoice number, invoice date, "
        "due date, vendor/seller name and address, buyer/customer name and address, "
        "currency, payment terms), the full line-item table (description, quantity, "
        "unit price, line total for each row), subtotal, tax/VAT amount and rate, "
        "discount if any, and the grand total."
    ),

    "balance_sheet": (
        "This is a BALANCE SHEET. Extract company name, statement date/period, "
        "currency, and every line item under Assets (current and non-current), "
        "Liabilities (current and non-current) and Equity, for the current period "
        "AND the comparative prior period where shown. Include total assets, total "
        "liabilities, total equity, and total liabilities + equity."
    ),

    "profit_and_loss": (
        "This is a PROFIT & LOSS / INCOME STATEMENT. Extract company name, period, "
        "currency, revenue/sales, cost of goods sold, gross profit, every operating "
        "expense line item, operating income, other income/expenses, tax, and net "
        "profit/loss, for the current period AND comparative prior period where shown."
    ),

    "cash_flow": (
        "This is a CASH FLOW STATEMENT. Extract company name, period, currency, "
        "opening cash balance, all line items under Operating, Investing and "
        "Financing activities, net cash flow from each activity, net increase/"
        "decrease in cash, and closing cash balance, for the current period AND "
        "comparative prior period where shown."
    ),
}


# ============================================================
# SYSTEM PROMPT
# ============================================================

_SYSTEM_PROMPT = """
You are a meticulous financial document data-extraction engine.

Rules you MUST follow:

1. Extract ALL meaningful fields and values visible in the document text
   provided, not just a small fixed list.

2. Include every meaningful header field, date, party name, currency,
   account name, amount, percentage, and every line item in tables.

3. NEVER invent, guess, calculate, or infer a value that is not clearly
   present in the supplied document text.

4. If a field is not present or not legible, its value must be JSON null.

5. For every non-null scalar field, include:
   - page
   - source_text

6. The source_text must be a SHORT VERBATIM snippet from the supplied
   document text and should contain no more than 15 words.

7. Return line-item / table data as arrays of row objects under "tables".

8. Preserve the values exactly as they appear when possible.
   Do not silently change currencies, dates, names, labels, or amounts.

9. Parentheses used for negative financial values must be preserved or
   represented as negative numbers when the meaning is unambiguous.

10. Do not perform financial validation yourself.
    Extraction only.

11. Respond with ONLY one valid JSON object.

12. Do NOT use markdown code fences.

13. Do NOT include explanations before or after the JSON.

Output JSON shape:

{
  "fields": {
    "<field_name>": {
      "value": <string|number|null>,
      "page": <int|null>,
      "source_text": <string|null>
    }
  },
  "tables": [
    {
      "table_name": "<name>",
      "rows": [
        {
          "<column>": <value>
        }
      ]
    }
  ]
}
"""


# ============================================================
# PAGE TEXT → PROMPT
# ============================================================

def _pages_to_prompt(pages: list[PageText]) -> str:
    """
    Convert page-level OCR/native extraction into a clearly
    separated prompt.
    """

    parts = []

    for page in pages:
        parts.append(
            f"--- PAGE {page.page_number} "
            f"(source: {page.source}) ---\n"
            f"{page.text.strip()}"
        )

    return "\n\n".join(parts)


# ============================================================
# CLEAN GEMINI RESPONSE
# ============================================================

def _strip_code_fence(text: str) -> str:
    """
    Remove markdown code fences if the model accidentally returns them.
    """

    text = text.strip()

    text = re.sub(
        r"^```(?:json)?",
        "",
        text,
        flags=re.IGNORECASE
    ).strip()

    text = re.sub(
        r"```$",
        "",
        text
    ).strip()

    return text


# ============================================================
# JSON EXTRACTION FALLBACK
# ============================================================

def _extract_json_object(text: str) -> str:
    """
    Attempt to locate a JSON object if Gemini returns additional text.
    """

    text = _strip_code_fence(text)

    start = text.find("{")
    end = text.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return text

    return text[start:end + 1]


# ============================================================
# MAIN EXTRACTION
# ============================================================

def extract_structured_data(
    document_type: str,
    pages: list[PageText]
) -> dict:
    """
    Extract structured financial data using Google Gemini.

    Returns:

    {
        "fields": {...},
        "tables": [...],
        "model": "..."
    }

    Raises RuntimeError if Gemini is unavailable or returns
    unusable output.
    """

    # --------------------------------------------------------
    # Check Gemini API key
    # --------------------------------------------------------

    if _client is None:

        raise RuntimeError(
            "GEMINI_API_KEY is not configured. "
            "Set it in your .env file to enable extraction."
        )

    # --------------------------------------------------------
    # Document guidance
    # --------------------------------------------------------

    guidance = _DOC_TYPE_GUIDANCE.get(
        document_type,
        ""
    )

    # --------------------------------------------------------
    # Convert pages to prompt
    # --------------------------------------------------------

    document_text = _pages_to_prompt(pages)

    user_prompt = (
        f"{guidance}\n\n"
        "Document text (page by page):\n\n"
        f"{document_text}"
    )

    logger.info(
        "Calling Gemini for extraction "
        "(doc_type=%s, pages=%d, model=%s)",
        document_type,
        len(pages),
        settings.GEMINI_MODEL
    )

    # --------------------------------------------------------
    # Gemini API call
    # --------------------------------------------------------

    try:

        response = _client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=user_prompt,
            config={
                "system_instruction": _SYSTEM_PROMPT,
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )

    except Exception as exc:

        logger.exception(
            "Gemini extraction request failed"
        )

        raise RuntimeError(
            f"Gemini extraction failed: {exc}"
        ) from exc

    # --------------------------------------------------------
    # Extract response text
    # --------------------------------------------------------

    raw_text = getattr(
        response,
        "text",
        None
    )

    if not raw_text:

        logger.error(
            "Gemini returned an empty response"
        )

        raise RuntimeError(
            "Gemini extraction returned an empty response."
        )

    # --------------------------------------------------------
    # Clean JSON
    # --------------------------------------------------------

    cleaned = _extract_json_object(
        raw_text
    )

    # --------------------------------------------------------
    # Parse JSON
    # --------------------------------------------------------

    try:

        parsed = json.loads(
            cleaned
        )

    except json.JSONDecodeError:

        logger.error(
            "Gemini returned non-JSON output: %s",
            raw_text[:1000]
        )

        raise RuntimeError(
            "Gemini extraction returned an unparsable JSON response."
        )

    # --------------------------------------------------------
    # Validate basic structure
    # --------------------------------------------------------

    if not isinstance(parsed, dict):

        raise RuntimeError(
            "Gemini extraction response must be a JSON object."
        )

    parsed.setdefault(
        "fields",
        {}
    )

    parsed.setdefault(
        "tables",
        []
    )

    # --------------------------------------------------------
    # Store model used
    # --------------------------------------------------------

    parsed["model"] = settings.GEMINI_MODEL

    logger.info(
        "Gemini extraction completed successfully "
        "(fields=%d, tables=%d)",
        len(parsed.get("fields", {})),
        len(parsed.get("tables", []))
    )

    return parsed