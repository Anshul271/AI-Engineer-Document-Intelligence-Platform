from app.services.financial_validation import validate_invoice, validate_balance_sheet
from app.schemas import ValidationStatus


def _f(value):
    return {"value": value}


def test_invoice_totals_pass():
    fields = {"subtotal": _f("100.00"), "tax": _f("10.00"), "total": _f("110.00")}
    tables = [{"table_name": "items", "rows": [{"description": "A", "line total": "60.00"},
                                                {"description": "B", "line total": "40.00"}]}]
    results = validate_invoice(fields, tables)
    subtotal_tax_check = results[0]
    assert subtotal_tax_check.status == ValidationStatus.pass_


def test_invoice_totals_fail_on_mismatch():
    fields = {"subtotal": _f("100.00"), "tax": _f("10.00"), "total": _f("500.00")}
    results = validate_invoice(fields, [])
    assert results[0].status == ValidationStatus.fail


def test_missing_fields_are_not_applicable():
    fields = {"subtotal": _f("100.00")}
    results = validate_invoice(fields, [])
    assert results[0].status == ValidationStatus.not_applicable


def test_balance_sheet_equation():
    fields = {
        "total assets": _f("1,000.00"),
        "total liabilities": _f("600.00"),
        "total equity": _f("400.00"),
    }
    results = validate_balance_sheet(fields, [])
    assert results[0].status == ValidationStatus.pass_
