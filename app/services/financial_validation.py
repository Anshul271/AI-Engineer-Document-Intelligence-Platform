"""
Deterministic financial validation. Never uses the LLM - all checks are
plain arithmetic against the values the extraction layer returned, so
results are reproducible and explainable. If a field required for a check
is missing, the check status is NOT_APPLICABLE rather than guessed.
"""
import re
from typing import Any, Optional

from app.config import settings
from app.logging_config import get_logger
from app.schemas import FinancialValidationResult, ValidationStatus

logger = get_logger(__name__)

_NUMERIC_RE = re.compile(r"-?\(?\d[\d,]*\.?\d*\)?")


def _to_number(raw: Any) -> Optional[float]:
    """Best-effort parse of a currency-formatted value like '1,234.50', '(500)', '$1,000'."""
    if raw is None:
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip()
    if not text:
        return None
    match = _NUMERIC_RE.search(text)
    if not match:
        return None
    token = match.group().replace(",", "")
    negative = token.startswith("(") and token.endswith(")")
    token = token.strip("()")
    try:
        value = float(token)
    except ValueError:
        return None
    return -value if negative else value


def _field_value(fields: dict, *candidate_keys: str) -> Optional[float]:
    """Look up the first matching field (case-insensitive, loose match) and parse it as a number."""
    lower_map = {k.lower(): v for k, v in fields.items()}
    for key in candidate_keys:
        if key.lower() in lower_map:
            return _to_number(lower_map[key.lower()].get("value") if isinstance(lower_map[key.lower()], dict) else lower_map[key.lower()])
    # loose substring match as a fallback
    for k, v in fields.items():
        kl = k.lower()
        if any(c.lower() in kl for c in candidate_keys):
            return _to_number(v.get("value") if isinstance(v, dict) else v)
    return None


def _check(name: str, formula: str, inputs: dict, calculated: Optional[float], reported: Optional[float]) -> FinancialValidationResult:
    if calculated is None or reported is None:
        return FinancialValidationResult(
            check_name=name, formula=formula, input_values=inputs,
            calculated_value=calculated, reported_value=reported,
            variance=None, status=ValidationStatus.not_applicable,
        )
    variance = round(calculated - reported, 2)
    tolerance = max(abs(reported) * settings.NUMERIC_TOLERANCE, 0.5)
    status = ValidationStatus.pass_ if abs(variance) <= tolerance else ValidationStatus.fail
    return FinancialValidationResult(
        check_name=name, formula=formula, input_values=inputs,
        calculated_value=calculated, reported_value=reported,
        variance=variance, status=status,
    )


def _sum_table_column(tables: list[dict], candidate_cols: list[str]) -> Optional[float]:
    total = 0.0
    found_any = False
    for table in tables:
        for row in table.get("rows", []):
            for col_key, col_val in row.items():
                if any(c.lower() in col_key.lower() for c in candidate_cols):
                    num = _to_number(col_val)
                    if num is not None:
                        total += num
                        found_any = True
    return total if found_any else None


def validate_invoice(fields: dict, tables: list[dict]) -> list[FinancialValidationResult]:
    results = []
    subtotal = _field_value(fields, "subtotal", "sub total", "sub-total")
    tax = _field_value(fields, "tax", "vat", "gst")
    total = _field_value(fields, "total", "grand total", "amount due")
    line_sum = _sum_table_column(tables, ["line total", "amount", "total"])

    results.append(_check(
        "Subtotal + Tax = Total", "subtotal + tax == total",
        {"subtotal": subtotal, "tax": tax}, 
        (subtotal + tax) if subtotal is not None and tax is not None else None,
        total,
    ))
    results.append(_check(
        "Line items sum = Subtotal", "sum(line_totals) == subtotal",
        {"line_items_sum": line_sum}, line_sum, subtotal,
    ))
    return results


def validate_balance_sheet(fields: dict, tables: list[dict]) -> list[FinancialValidationResult]:
    total_assets = _field_value(fields, "total assets")
    total_liabilities = _field_value(fields, "total liabilities")
    total_equity = _field_value(fields, "total equity", "total shareholders equity", "total stockholders equity")

    calc = None
    if total_liabilities is not None and total_equity is not None:
        calc = total_liabilities + total_equity

    return [_check(
        "Total Assets = Total Liabilities + Total Equity",
        "total_liabilities + total_equity == total_assets",
        {"total_liabilities": total_liabilities, "total_equity": total_equity},
        calc, total_assets,
    )]


def validate_profit_and_loss(fields: dict, tables: list[dict]) -> list[FinancialValidationResult]:
    revenue = _field_value(fields, "revenue", "total revenue", "sales", "net sales")
    cogs = _field_value(fields, "cost of goods sold", "cogs", "cost of sales")
    gross_profit = _field_value(fields, "gross profit")
    expenses = _field_value(fields, "total operating expenses", "operating expenses")
    net_profit = _field_value(fields, "net profit", "net income", "net loss")

    results = []
    calc_gp = (revenue - cogs) if revenue is not None and cogs is not None else None
    results.append(_check(
        "Revenue - COGS = Gross Profit", "revenue - cogs == gross_profit",
        {"revenue": revenue, "cogs": cogs}, calc_gp, gross_profit,
    ))

    calc_np = None
    if gross_profit is not None and expenses is not None:
        calc_np = gross_profit - expenses
    results.append(_check(
        "Gross Profit - Operating Expenses = Net Profit",
        "gross_profit - operating_expenses == net_profit",
        {"gross_profit": gross_profit, "operating_expenses": expenses}, calc_np, net_profit,
    ))
    return results


def validate_cash_flow(fields: dict, tables: list[dict]) -> list[FinancialValidationResult]:
    opening = _field_value(fields, "opening cash balance", "cash at beginning")
    operating = _field_value(fields, "net cash from operating", "operating activities")
    investing = _field_value(fields, "net cash from investing", "investing activities")
    financing = _field_value(fields, "net cash from financing", "financing activities")
    closing = _field_value(fields, "closing cash balance", "cash at end")

    calc = None
    if None not in (opening, operating, investing, financing):
        calc = opening + operating + investing + financing

    return [_check(
        "Opening + Operating + Investing + Financing = Closing",
        "opening + operating + investing + financing == closing",
        {"opening": opening, "operating": operating, "investing": investing, "financing": financing},
        calc, closing,
    )]


_VALIDATORS = {
    "invoice": validate_invoice,
    "balance_sheet": validate_balance_sheet,
    "profit_and_loss": validate_profit_and_loss,
    "cash_flow": validate_cash_flow,
}


def run_financial_validations(document_type: str, flat_fields: dict, tables: list[dict]) -> list[FinancialValidationResult]:
    validator = _VALIDATORS.get(document_type)
    if not validator:
        return []
    try:
        return validator(flat_fields, tables)
    except Exception:  # noqa: BLE001
        logger.exception("Financial validation crashed for doc_type=%s", document_type)
        return []
