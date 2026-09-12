from decimal import Decimal, InvalidOperation


# =========================================================
# CONFIGURATION
# =========================================================

TOLERANCE = Decimal("0.01")


# =========================================================
# COMMON HELPERS
# =========================================================

def to_decimal(value):

    if value is None:
        return None

    try:

        return Decimal(
            str(value).replace(",", "")
        )

    except (
        InvalidOperation,
        ValueError,
        TypeError,
    ):

        return None


def amounts_match(a, b):

    a = to_decimal(a)
    b = to_decimal(b)

    if a is None or b is None:
        return None

    return abs(a - b) <= TOLERANCE


def get_value(data, key):
    """
    Supports:

        data[key]

    fields[key]

    fields[key_current]

    """

    if key in data:
        return data.get(key)

    fields = data.get("fields", {})

    if not isinstance(fields, dict):
        return None

    if key in fields:
        return fields.get(key)

    current_key = f"{key}_current"

    if current_key in fields:
        return fields.get(current_key)

    return None


def make_check(
    name,
    formula,
    operands,
    calculated_value,
    reported_value,
):

    calculated = to_decimal(
        calculated_value
    )

    reported = to_decimal(
        reported_value
    )

    if calculated is None or reported is None:

        return {

            "name": name,

            "formula": formula,

            "operands": operands,

            "calculated_value": (
                float(calculated)
                if calculated is not None
                else None
            ),

            "reported_value": (
                float(reported)
                if reported is not None
                else None
            ),

            "variance": None,

            "status":
                "NOT_APPLICABLE",
        }

    variance = calculated - reported

    status = (
        "PASS"
        if abs(variance) <= TOLERANCE
        else "FAILED"
    )

    return {

        "name":
            name,

        "formula":
            formula,

        "operands":
            operands,

        "calculated_value":
            float(calculated),

        "reported_value":
            float(reported),

        "variance":
            float(variance),

        "status":
            status,
    }


# =========================================================
# INVOICE
# =========================================================

def validate_invoice(data):

    checks = []

    subtotal = to_decimal(
        get_value(
            data,
            "subtotal",
        )
    )

    tax = to_decimal(
        get_value(
            data,
            "tax",
        )
    )

    if tax is None:

        tax = to_decimal(
            get_value(
                data,
                "tax_amount",
            )
        )

    discount = to_decimal(
        get_value(
            data,
            "discount",
        )
    )

    shipping = to_decimal(
        get_value(
            data,
            "shipping_and_handling",
        )
    )

    total = to_decimal(
        get_value(
            data,
            "total",
        )
    )

    if total is None:

        total = to_decimal(
            get_value(
                data,
                "total_amount",
            )
        )

    line_items = data.get(
        "line_items",
        [],
    )

    # -----------------------------------------------------
    # Line item validation
    # -----------------------------------------------------

    if isinstance(line_items, list):

        line_total_sum = Decimal("0")

        valid_line_items = 0

        for item in line_items:

            if not isinstance(item, dict):
                continue

            quantity = to_decimal(
                item.get("quantity")
            )

            unit_price = to_decimal(
                item.get("unit_price")
            )

            amount = to_decimal(
                item.get("amount")
            )

            if (
                quantity is not None
                and unit_price is not None
                and amount is not None
            ):

                calculated_amount = (
                    quantity * unit_price
                )

                checks.append(
                    make_check(

                        name=
                            "line_item_amount_check",

                        formula=
                            "quantity * unit_price",

                        operands={
                            "quantity":
                                float(quantity),

                            "unit_price":
                                float(unit_price),
                        },

                        calculated_value=
                            calculated_amount,

                        reported_value=
                            amount,
                    )
                )

                line_total_sum += amount

                valid_line_items += 1

        if (
            valid_line_items > 0
            and subtotal is not None
        ):

            checks.append(
                make_check(

                    name=
                        "invoice_line_items_vs_subtotal",

                    formula=
                        "sum(line_item_amounts)",

                    operands={
                        "line_item_total":
                            float(line_total_sum),
                    },

                    calculated_value=
                        line_total_sum,

                    reported_value=
                        subtotal,
                )
            )

    # -----------------------------------------------------
    # Invoice total
    # -----------------------------------------------------

    if (
        subtotal is not None
        and tax is not None
        and total is not None
    ):

        if shipping is None:
            shipping = Decimal("0")

        if discount is None:
            discount = Decimal("0")

        calculated_total = (
            subtotal
            + tax
            + shipping
            - discount
        )

        checks.append(
            make_check(

                name=
                    "invoice_total_check",

                formula=
                    (
                        "subtotal + tax + "
                        "shipping_and_handling - discount"
                    ),

                operands={
                    "subtotal":
                        float(subtotal),

                    "tax":
                        float(tax),

                    "shipping_and_handling":
                        float(shipping),

                    "discount":
                        float(discount),
                },

                calculated_value=
                    calculated_total,

                reported_value=
                    total,
            )
        )

    return checks


# =========================================================
# BALANCE SHEET
# =========================================================

def validate_balance_sheet(data):

    checks = []

    total_assets = to_decimal(
        get_value(
            data,
            "total_assets",
        )
    )

    total_capital_liabilities = to_decimal(
        get_value(
            data,
            "total_capital_and_liabilities",
        )
    )

    # -----------------------------------------------------
    # Current period
    # -----------------------------------------------------

    if (
        total_assets is not None
        and total_capital_liabilities is not None
    ):

        checks.append(
            make_check(

                name=
                    "balance_sheet_balance_check",

                formula=
                    (
                        "total_capital_and_liabilities "
                        "= total_assets"
                    ),

                operands={
                    "total_capital_and_liabilities":
                        float(
                            total_capital_liabilities
                        ),

                    "total_assets":
                        float(total_assets),
                },

                calculated_value=
                    total_capital_liabilities,

                reported_value=
                    total_assets,
            )
        )

    # -----------------------------------------------------
    # Comparative period
    # -----------------------------------------------------

    fields = data.get(
        "fields",
        {},
    )

    if isinstance(fields, dict):

        comparative_assets = to_decimal(
            fields.get(
                "total_assets_comparative"
            )
        )

        comparative_capital_liabilities = to_decimal(
            fields.get(
                "total_capital_and_liabilities_comparative"
            )
        )

        if (
            comparative_assets is not None
            and comparative_capital_liabilities is not None
        ):

            checks.append(
                make_check(

                    name=
                        "balance_sheet_comparative_balance_check",

                    formula=
                        (
                            "comparative_total_capital_and_liabilities "
                            "= comparative_total_assets"
                        ),

                    operands={
                        "comparative_total_capital_and_liabilities":
                            float(
                                comparative_capital_liabilities
                            ),

                        "comparative_total_assets":
                            float(
                                comparative_assets
                            ),
                    },

                    calculated_value=
                        comparative_capital_liabilities,

                    reported_value=
                        comparative_assets,
                )
            )

    return checks


# =========================================================
# PROFIT & LOSS
# =========================================================

def validate_profit_and_loss(data):

    checks = []

    total_income = to_decimal(
        get_value(
            data,
            "total_income",
        )
    )

    total_expenditure = to_decimal(
        get_value(
            data,
            "total_expenditure",
        )
    )

    net_profit = to_decimal(
        get_value(
            data,
            "consolidated_net_profit_before_minority_interest",
        )
    )

    interest_earned = to_decimal(
        get_value(
            data,
            "interest_earned",
        )
    )

    other_income = to_decimal(
        get_value(
            data,
            "other_income",
        )
    )

    # -----------------------------------------------------
    # Total income
    # -----------------------------------------------------

    if (
        interest_earned is not None
        and other_income is not None
        and total_income is not None
    ):

        calculated_income = (
            interest_earned
            + other_income
        )

        checks.append(
            make_check(

                name=
                    "profit_and_loss_total_income_check",

                formula=
                    "interest_earned + other_income",

                operands={
                    "interest_earned":
                        float(interest_earned),

                    "other_income":
                        float(other_income),
                },

                calculated_value=
                    calculated_income,

                reported_value=
                    total_income,
            )
        )

    # -----------------------------------------------------
    # Profit before minority interest
    # -----------------------------------------------------

    if (
        total_income is not None
        and total_expenditure is not None
        and net_profit is not None
    ):

        calculated_profit = (
            total_income
            - total_expenditure
        )

        checks.append(
            make_check(

                name=
                    "profit_before_minority_interest_check",

                formula=
                    "total_income - total_expenditure",

                operands={
                    "total_income":
                        float(total_income),

                    "total_expenditure":
                        float(total_expenditure),
                },

                calculated_value=
                    calculated_profit,

                reported_value=
                    net_profit,
            )
        )

    return checks


# =========================================================
# CASH FLOW
# =========================================================

def validate_cash_flow(data):

    checks = []

    operating = to_decimal(
        get_value(
            data,
            "operating_cash_flow",
        )
    )

    investing = to_decimal(
        get_value(
            data,
            "investing_cash_flow",
        )
    )

    financing = to_decimal(
        get_value(
            data,
            "financing_cash_flow",
        )
    )

    fx_adjustment = to_decimal(
        get_value(
            data,
            "fx_translation_adjustment",
        )
    )

    net_change = to_decimal(
        get_value(
            data,
            "net_change_in_cash",
        )
    )

    opening_cash = to_decimal(
        get_value(
            data,
            "opening_cash",
        )
    )

    closing_cash = to_decimal(
        get_value(
            data,
            "closing_cash",
        )
    )

    cash_on_amalgamation = to_decimal(
        get_value(
            data,
            "cash_on_amalgamation",
        )
    )

    # =====================================================
    # CHECK 1
    # Operating + Investing + Financing + FX
    # =====================================================

    if (
        operating is not None
        and investing is not None
        and financing is not None
        and net_change is not None
    ):

        if fx_adjustment is None:
            fx_adjustment = Decimal("0")

        calculated_net_change = (
            operating
            + investing
            + financing
            + fx_adjustment
        )

        checks.append(
            make_check(

                name=
                    "cash_flow_net_change_check",

                formula=
                    (
                        "operating_cash_flow + "
                        "investing_cash_flow + "
                        "financing_cash_flow + "
                        "fx_translation_adjustment"
                    ),

                operands={
                    "operating_cash_flow":
                        float(operating),

                    "investing_cash_flow":
                        float(investing),

                    "financing_cash_flow":
                        float(financing),

                    "fx_translation_adjustment":
                        float(fx_adjustment),
                },

                calculated_value=
                    calculated_net_change,

                reported_value=
                    net_change,
            )
        )

    # =====================================================
    # CHECK 2
    # Opening + Net Change = Closing
    #
    # This is the primary cash reconciliation.
    # =====================================================

    if (
        opening_cash is not None
        and net_change is not None
        and closing_cash is not None
    ):

        calculated_closing = (
            opening_cash
            + net_change
        )

        checks.append(
            make_check(

                name=
                    "cash_flow_closing_cash_check",

                formula=
                    (
                        "opening_cash + "
                        "net_change_in_cash"
                    ),

                operands={
                    "opening_cash":
                        float(opening_cash),

                    "net_change_in_cash":
                        float(net_change),
                },

                calculated_value=
                    calculated_closing,

                reported_value=
                    closing_cash,
            )
        )

    # =====================================================
    # CHECK 3
    # Opening + Net Change + Adjustment = Closing
    #
    # Only perform this when the statement explicitly
    # provides an adjustment amount.
    # =====================================================

    if (
        opening_cash is not None
        and net_change is not None
        and closing_cash is not None
        and cash_on_amalgamation is not None
    ):

        calculated_adjusted_closing = (
            opening_cash
            + net_change
            + cash_on_amalgamation
        )

        checks.append(
            make_check(

                name=
                    "cash_flow_adjusted_closing_cash_check",

                formula=
                    (
                        "opening_cash + "
                        "net_change_in_cash + "
                        "cash_on_amalgamation"
                    ),

                operands={
                    "opening_cash":
                        float(opening_cash),

                    "net_change_in_cash":
                        float(net_change),

                    "cash_on_amalgamation":
                        float(
                            cash_on_amalgamation
                        ),
                },

                calculated_value=
                    calculated_adjusted_closing,

                reported_value=
                    closing_cash,
            )
        )

    return checks


# =========================================================
# MAIN VALIDATOR
# =========================================================

def validate_financial_data(
    data: dict,
) -> dict:

    document_type = data.get(
        "document_type",
        "invoice",
    )

    if document_type == "invoice":

        checks = validate_invoice(data)

    elif document_type == "balance_sheet":

        checks = validate_balance_sheet(data)

    elif document_type == "profit_and_loss":

        checks = validate_profit_and_loss(data)

    elif document_type == "cash_flow_statement":

        checks = validate_cash_flow(data)

    else:

        return {

            "overall_status":
                "NOT_APPLICABLE",

            "checks":
                [],

            "issues": [
                (
                    "Unsupported document type: "
                    f"{document_type}"
                )
            ],
        }

    applicable_checks = [
        check
        for check in checks
        if check["status"] != "NOT_APPLICABLE"
    ]

    failed_checks = [
        check
        for check in applicable_checks
        if check["status"] == "FAILED"
    ]

    if not applicable_checks:

        overall_status = "NOT_APPLICABLE"

    elif failed_checks:

        overall_status = "FAILED"

    else:

        overall_status = "PASS"

    issues = [
        check["name"]
        for check in failed_checks
    ]

    return {

        "overall_status":
            overall_status,

        "checks":
            checks,

        "issues":
            issues,
    }