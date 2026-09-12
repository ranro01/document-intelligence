from app.services.financial_validation_service import (
    validate_financial_data,
)


def test_invoice_financial_validation_passes():
    data = {
        "document_type": "invoice",
        "fields": {
            "subtotal": 126.27,
            "tax": 12.63,
            "total": 138.90,
        },
        "line_items": [
            {
                "description": "Item 1",
                "quantity": 5,
                "unit_price": 3.49,
                "amount": 17.45,
            },
            {
                "description": "Item 2",
                "quantity": 3,
                "unit_price": 4.49,
                "amount": 13.47,
            },
            {
                "description": "Item 3",
                "quantity": 5,
                "unit_price": 9.35,
                "amount": 46.75,
            },
            {
                "description": "Item 4",
                "quantity": 4,
                "unit_price": 4.49,
                "amount": 17.96,
            },
            {
                "description": "Item 5",
                "quantity": 2,
                "unit_price": 4.89,
                "amount": 9.78,
            },
            {
                "description": "Item 6",
                "quantity": 1,
                "unit_price": 5.50,
                "amount": 5.50,
            },
            {
                "description": "Item 7",
                "quantity": 2,
                "unit_price": 7.68,
                "amount": 15.36,
            },
        ],
    }

    result = validate_financial_data(data)

    assert result["overall_status"] == "PASS"
    assert result["issues"] == []


def test_invoice_financial_validation_fails_on_wrong_total():
    data = {
        "document_type": "invoice",
        "fields": {
            "subtotal": 126.27,
            "tax": 12.63,
            "total": 100.00,
        },
        "line_items": [],
    }

    result = validate_financial_data(data)

    assert result["overall_status"] == "FAILED"
    assert "invoice_total_check" in result["issues"]