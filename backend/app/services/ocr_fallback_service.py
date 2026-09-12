import re

from app.services.ocr_space_service import extract_with_ocr_space


# =========================================================
# COMMON HELPERS
# =========================================================

def to_number(value):
    """
    Convert OCR financial values to numbers.

    Handles both common number formats:
        126.27   -> 126.27
        1,234.56 -> 1234.56
        126,27   -> 126.27
        1.234,56 -> 1234.56

    Parentheses are treated as negative values.
    Currency symbols are ignored.
    """
    if value is None:
        return None

    try:
        cleaned = (
            str(value)
            .replace("₹", "")
            .replace("$", "")
            .replace("€", "")
            .replace("£", "")
            .strip()
        )

        if cleaned in {"", "-", "—", "–", "N/A", "n/a"}:
            return None

        negative = (
            cleaned.startswith("(")
            and cleaned.endswith(")")
        )

        if negative:
            cleaned = cleaned[1:-1].strip()

        cleaned = cleaned.replace(" ", "")

        # Handle both US and European number formats.
        if "," in cleaned and "." in cleaned:
            last_comma = cleaned.rfind(",")
            last_dot = cleaned.rfind(".")

            if last_comma > last_dot:
                # European: 1.234,56
                cleaned = (
                    cleaned
                    .replace(".", "")
                    .replace(",", ".")
                )
            else:
                # Standard: 1,234.56
                cleaned = cleaned.replace(",", "")

        elif "," in cleaned:
            parts = cleaned.split(",")

            if (
                len(parts) == 2
                and len(parts[1]) in {1, 2}
            ):
                # Decimal comma: 126,27 / 5,5
                cleaned = ".".join(parts)

            elif (
                len(parts) > 2
                and all(
                    len(part) == 3
                    for part in parts[1:]
                )
            ):
                # Thousands: 1,234,567
                cleaned = "".join(parts)

            elif (
                len(parts) == 2
                and len(parts[1]) == 3
            ):
                # Thousands: 1,234
                cleaned = "".join(parts)

            else:
                # Conservative fallback: final comma is decimal.
                cleaned = (
                    "".join(parts[:-1])
                    + "."
                    + parts[-1]
                )

        number = float(cleaned)

        return -number if negative else number

    except (ValueError, TypeError):
        return None


def is_financial_number(line: str) -> bool:
    line = line.strip()

    return bool(
        re.fullmatch(
            r"-?\(?\d[\d,]*(?:[.,]\d+)?\)?",
            line,
        )
    )


def is_schedule_number(line: str) -> bool:
    return bool(
        re.fullmatch(
            r"\d+[A-Za-z]?",
            line.strip(),
        )
    )


def is_empty_financial_value(value: str) -> bool:
    return value.strip() in {
        "",
        "-",
        "—",
        "–",
    }


# =========================================================
# IDENTIFIER-LINE GUARDS
#
# Lines like "Tax Id: 964-99-8203" or "IBAN: GB31..." must
# never be treated as a source of a financial amount. They
# contain label words (e.g. "tax") that collide with real
# amount labels, and their hyphen/alphanumeric groups look
# like negative numbers to a naive digit scan.
# =========================================================

IDENTIFIER_KEYWORDS = (
    "tax id",
    "vat id",
    "gst id",
    "gstin",
    "pan no",
    "pan number",
    "account no",
    "account number",
    "customer id",
    "client id",
    "vendor id",
    "invoice id",
    "reference no",
    "reference number",
    "iban",
    "swift",
    "routing number",
    "ein",
    "ssn",
)


def is_identifier_line(line: str) -> bool:
    normalized = normalize_label(line)

    return any(
        keyword in normalized
        for keyword in IDENTIFIER_KEYWORDS
    )


def strip_percentage_tokens(line: str) -> str:
    """
    Remove "10%" / "10 %" style tokens before scanning a
    line for a financial amount, so a VAT/tax rate is never
    picked up in place of the actual VAT/tax amount.
    """

    return re.sub(
        r"\d+(?:\.\d+)?\s*%",
        " ",
        line,
    )


def clean_markdown_line(line: str) -> str:
    line = line.strip()
    line = line.replace("**", "")
    line = line.replace("__", "")
    return line


def clean_lines(text: str):
    lines = []

    for raw_line in text.splitlines():

        line = clean_markdown_line(raw_line)

        if not line.strip():
            continue

        stripped = line.replace("|", "").strip()

        if stripped and all(
            char in "-: "
            for char in stripped
        ):
            continue

        lines.append(line.strip())

    return lines


def normalize_label(label: str) -> str:
    label = str(label).lower().strip()

    label = label.replace("’", "'")
    label = label.replace("**", "")
    label = label.replace("__", "")
    label = label.replace("–", "-")
    label = label.replace("—", "-")

    label = re.sub(
        r"\s*/\s*",
        " / ",
        label,
    )

    label = re.sub(
        r"\(\s*",
        "(",
        label,
    )

    label = re.sub(
        r"\s*\)",
        ")",
        label,
    )

    replacements = {
        "(used in) / from": "used in from",
        "(used in)/from": "used in from",
        "(used in) /from": "used in from",
        "(used in) /": "used in",
        "/ (used in)": "used in",
        "from / (used in)": "from used in",
        "from/ (used in)": "from used in",
        "from/(used in)": "from used in",
    }

    for old, new in replacements.items():
        label = label.replace(old, new)

    label = label.replace("/", " ")
    label = label.replace("(", " ")
    label = label.replace(")", " ")

    label = re.sub(
        r"\s+",
        " ",
        label,
    )

    return label.strip()


def labels_match(actual_label: str, target_label: str) -> bool:
    actual = normalize_label(actual_label)
    target = normalize_label(target_label)

    if actual == target:
        return True

    if target in actual:
        return True

    if actual in target:
        return True

    return False


def extract_statement_period(lines):

    for line in lines:

        clean = (
            line
            .replace("|", " ")
            .strip()
        )

        lower = clean.lower()

        if lower.startswith("as at march"):
            return clean

        if lower.startswith("for the year ended"):
            return clean

        if lower.startswith("for the year"):
            return clean

        if lower.startswith("for year"):
            return clean

    return None


def extract_currency(lines):

    for line in lines:

        lower = line.lower()

        if "₹ in crore" in lower:
            return "INR"

        if "in crore" in lower:
            return "INR"

        if "₹ in '000" in lower:
            return "in '000"

        if "in '000" in lower:
            return "in '000"

        if "₹" in line:
            return "INR"

        if "rs." in lower:
            return "INR"

        if "inr" in lower:
            return "INR"

        if "$" in line:
            return "USD"

        if "usd" in lower:
            return "USD"

        if "eur" in lower or "€" in line:
            return "EUR"

        if "gbp" in lower or "£" in line:
            return "GBP"

    return None


# =========================================================
# MARKDOWN TABLE HELPERS
# =========================================================

def parse_markdown_table_row(line):

    if "|" not in line:
        return []

    parts = [
        part.strip()
        for part in line.split("|")
    ]

    return [
        part
        for part in parts
        if part != ""
    ]


def extract_table_numeric_values(line):

    parts = parse_markdown_table_row(line)

    if not parts:
        return []

    values = []

    for part in parts:

        if is_schedule_number(part):
            continue

        if is_financial_number(part):

            number = to_number(part)

            if number is not None:
                values.append(number)

    return values


def extract_table_two_values(parts):

    if len(parts) < 3:
        return None, None

    candidate_parts = parts[1:]

    filtered_parts = []

    for part in candidate_parts:

        if is_schedule_number(part):
            continue

        filtered_parts.append(part)

    if len(filtered_parts) < 2:
        return None, None

    current_raw = filtered_parts[-2]
    comparative_raw = filtered_parts[-1]

    current = (
        None
        if is_empty_financial_value(current_raw)
        else to_number(current_raw)
    )

    comparative = (
        None
        if is_empty_financial_value(comparative_raw)
        else to_number(comparative_raw)
    )

    return current, comparative


# =========================================================
# GENERIC LABELED VALUE EXTRACTION
# =========================================================

def find_labeled_values(
    lines,
    labels,
    field_name,
    fields,
):

    normalized_labels = [
        normalize_label(label)
        for label in labels
    ]

    for index, line in enumerate(lines):

        # -------------------------------------------------
        # MARKDOWN TABLE
        # -------------------------------------------------

        if "|" in line:

            parts = parse_markdown_table_row(line)

            if not parts:
                continue

            actual_label = normalize_label(parts[0])

            matched = any(
                labels_match(
                    actual_label,
                    target,
                )
                for target in normalized_labels
            )

            if not matched:
                continue

            current, comparative = (
                extract_table_two_values(parts)
            )

            if current is not None:

                fields[
                    f"{field_name}_current"
                ] = current

            if comparative is not None:

                fields[
                    f"{field_name}_comparative"
                ] = comparative

            return

        # -------------------------------------------------
        # NORMAL OCR
        # -------------------------------------------------

        actual_label = normalize_label(line)

        matched = any(
            labels_match(
                actual_label,
                target,
            )
            for target in normalized_labels
        )

        if not matched:
            continue

        values = []

        for next_line in lines[
            index + 1:index + 8
        ]:

            if is_schedule_number(next_line):
                continue

            if is_financial_number(next_line):

                values.append(next_line)

                if len(values) == 2:
                    break

        if len(values) >= 1:

            fields[
                f"{field_name}_current"
            ] = to_number(values[0])

        if len(values) >= 2:

            fields[
                f"{field_name}_comparative"
            ] = to_number(values[1])

        return


# =========================================================
# BALANCE SHEET
# =========================================================

def extract_two_values(
    lines,
    start_index,
):

    values = []

    for line in lines[
        start_index + 1:start_index + 8
    ]:

        if "|" in line:

            row_values = (
                extract_table_numeric_values(line)
            )

            if len(row_values) >= 2:

                return (
                    row_values[-2],
                    row_values[-1],
                )

            continue

        if is_schedule_number(line):
            continue

        if is_financial_number(line):

            values.append(line)

            if len(values) == 2:
                break

    if len(values) == 2:

        return (
            to_number(values[0]),
            to_number(values[1]),
        )

    return None, None


def parse_balance_sheet_ocr(text: str) -> dict:

    fields = {}

    row_mapping = {

        "Capital":
            "capital",

        "Reserves and surplus":
            "reserves_and_surplus",

        "Minority interest":
            "minority_interest",

        "Deposits":
            "deposits",

        "Borrowings":
            "borrowings",

        "Other liabilities and provisions":
            "other_liabilities_and_provisions",

        "Cash and balances with Reserve Bank of India":
            "cash_and_balances_with_rbi",

        "Balances with banks and money at call and short notice":
            "balances_with_banks",

        "Investments":
            "investments",

        "Advances":
            "advances",

        "Fixed assets":
            "fixed_assets",

        "Other assets":
            "other_assets",
    }

    normalized_mapping = {
        normalize_label(label): key
        for label, key in row_mapping.items()
    }

    lines = clean_lines(text)

    statement_period = extract_statement_period(lines)
    currency = extract_currency(lines)

    for index, line in enumerate(lines):

        if "|" in line:

            parts = parse_markdown_table_row(line)

            if not parts:
                continue

            label = normalize_label(parts[0])

            if label not in normalized_mapping:
                continue

            current, comparative = (
                extract_table_two_values(parts)
            )

            key = normalized_mapping[label]

            if current is not None:

                fields[
                    f"{key}_current"
                ] = current

            if comparative is not None:

                fields[
                    f"{key}_comparative"
                ] = comparative

            continue

        label = normalize_label(line)

        if label not in normalized_mapping:
            continue

        key = normalized_mapping[label]

        current_value, comparative_value = (
            extract_two_values(
                lines,
                index,
            )
        )

        if current_value is not None:

            fields[
                f"{key}_current"
            ] = current_value

        if comparative_value is not None:

            fields[
                f"{key}_comparative"
            ] = comparative_value

    # -----------------------------------------------------
    # Total rows
    # -----------------------------------------------------

    total_rows = []

    for line in lines:

        if "|" not in line:
            continue

        parts = parse_markdown_table_row(line)

        if not parts:
            continue

        label = normalize_label(parts[0])

        if label != "total":
            continue

        current, comparative = (
            extract_table_two_values(parts)
        )

        if (
            current is not None
            or comparative is not None
        ):

            total_rows.append(
                [current, comparative]
            )

    if len(total_rows) >= 1:

        fields[
            "total_capital_and_liabilities_current"
        ] = total_rows[0][0]

        fields[
            "total_capital_and_liabilities_comparative"
        ] = total_rows[0][1]

    if len(total_rows) >= 2:

        fields[
            "total_assets_current"
        ] = total_rows[1][0]

        fields[
            "total_assets_comparative"
        ] = total_rows[1][1]

    return {
        "document_type": "balance_sheet",
        "statement_period": statement_period,
        "currency": currency,
        "fields": fields,
        "line_items": [],
    }


# =========================================================
# PROFIT & LOSS
# =========================================================

def extract_pl_table_values(lines):

    values = []

    income_found = False

    for line in lines:

        if "|" in line:

            parts = parse_markdown_table_row(line)

            if not parts:
                continue

            label = normalize_label(parts[0])

            if (
                label == "i income"
                or label == "income"
            ):

                income_found = True
                continue

            if not income_found:
                continue

            numeric_values = []

            for part in parts[1:]:

                if is_schedule_number(part):
                    continue

                if is_financial_number(part):

                    number = to_number(part)

                    if number is not None:
                        numeric_values.append(number)

            if len(numeric_values) >= 2:

                values.extend(
                    numeric_values[-2:]
                )

            continue

        lower = normalize_label(line)

        if (
            lower == "i income"
            or lower == "income"
        ):

            income_found = True
            continue

        if not income_found:
            continue

        if "earnings per equity share" in lower:
            break

        if (
            lower == "basic"
            or lower == "diluted"
        ):
            break

        if is_schedule_number(line):
            continue

        if is_financial_number(line):

            number = to_number(line)

            if number is not None:
                values.append(number)

    return values


def parse_profit_and_loss_ocr(text: str) -> dict:

    lines = clean_lines(text)

    statement_period = extract_statement_period(lines)
    currency = extract_currency(lines)

    fields = {}

    values = extract_pl_table_values(lines)

    field_names = [

        "interest_earned",

        "other_income",

        "total_income",

        "interest_expended",

        "operating_expenses",

        "provisions_and_contingencies",

        "total_expenditure",

        "net_profit_for_year",

        "minority_interest",

        "consolidated_net_profit",

        "balance_brought_forward",

        "total_profit_and_loss_account",
    ]

    value_index = 0

    for field_name in field_names:

        if value_index + 1 >= len(values):
            break

        fields[
            f"{field_name}_current"
        ] = values[value_index]

        fields[
            f"{field_name}_comparative"
        ] = values[value_index + 1]

        value_index += 2

    # -----------------------------------------------------
    # Validator-compatible profit field
    # -----------------------------------------------------

    if "net_profit_for_year_current" in fields:

        fields[
            "consolidated_net_profit_before_minority_interest_current"
        ] = fields[
            "net_profit_for_year_current"
        ]

    if "net_profit_for_year_comparative" in fields:

        fields[
            "consolidated_net_profit_before_minority_interest_comparative"
        ] = fields[
            "net_profit_for_year_comparative"
        ]

    # -----------------------------------------------------
    # Appropriations
    # -----------------------------------------------------

    appropriation_fields = [

        "transfer_to_statutory_reserve",

        "proposed_dividend",

        "tax_on_dividend",

        "dividend_previous_year",

        "transfer_to_general_reserve",

        "transfer_to_capital_reserve",

        "transfer_to_investment_reserve_account",

        "transfer_to_investment_fluctuation_reserve",

        "balance_carried_over_to_balance_sheet",

        "appropriation_total",
    ]

    for field_name in appropriation_fields:

        if value_index + 1 >= len(values):
            break

        fields[
            f"{field_name}_current"
        ] = values[value_index]

        fields[
            f"{field_name}_comparative"
        ] = values[value_index + 1]

        value_index += 2

    return {
        "document_type": "profit_and_loss",
        "statement_period": statement_period,
        "currency": currency,
        "fields": fields,
        "line_items": [],
    }


# =========================================================
# CASH FLOW
# =========================================================

def parse_cash_flow_ocr(text: str) -> dict:

    fields = {}

    lines = clean_lines(text)

    statement_period = extract_statement_period(lines)
    currency = extract_currency(lines)

    # -----------------------------------------------------
    # OPERATING
    # -----------------------------------------------------

    find_labeled_values(
        lines,
        [
            "Net cash from operating activities",
            "Net cash flow from operating activities",
            "Net cash flows from operating activities",
            "Net cash flow from / (used in) operating activities",
            "Net cash flows from / (used in) operating activities",
            "Net cash flow from/(used in) operating activities",
            "Net cash flows from/(used in) operating activities",
            "Net cash flow from (used in) operating activities",
            "Net cash flows from (used in) operating activities",
            "Net cash generated from operating activities",
            "Net cash generated by operating activities",
            "Operating cash flow",
            "Cash flow from operating activities",
            "Cash flows from operating activities",
            "Cash flows from / (used in) operating activities",
            "Cash flows from/(used in) operating activities",
            "Cash flows from (used in) operating activities",
        ],
        "operating_cash_flow",
        fields,
    )

    # -----------------------------------------------------
    # INVESTING
    # -----------------------------------------------------

    find_labeled_values(
        lines,
        [
            "Net cash from investing activities",
            "Net cash flow from investing activities",
            "Net cash flows from investing activities",
            "Net cash used in investing activities",
            "Net cash flow used in investing activities",
            "Net cash flows used in investing activities",
            "Net cash flow from / (used in) investing activities",
            "Net cash flows from / (used in) investing activities",
            "Net cash flow from/(used in) investing activities",
            "Net cash flows from/(used in) investing activities",
            "Net cash flow from (used in) investing activities",
            "Net cash flows from (used in) investing activities",
            "Net cash generated from investing activities",
            "Net cash generated by investing activities",
            "Investing cash flow",
            "Cash flow from investing activities",
            "Cash flows from investing activities",
            "Cash flows used in investing activities",
            "Cash flows from / (used in) investing activities",
            "Cash flows from/(used in) investing activities",
            "Cash flows from (used in) investing activities",
        ],
        "investing_cash_flow",
        fields,
    )

    # -----------------------------------------------------
    # FINANCING
    # -----------------------------------------------------

    find_labeled_values(
        lines,
        [
            "Net cash from financing activities",
            "Net cash flow from financing activities",
            "Net cash flows from financing activities",
            "Net cash used in financing activities",
            "Net cash flow used in financing activities",
            "Net cash flows used in financing activities",
            "Net cash (used in) / from financing activities",
            "Net cash (used in)/from financing activities",
            "Net cash (used in) /from financing activities",
            "Net cash flow (used in) / from financing activities",
            "Net cash flow (used in)/from financing activities",
            "Net cash flow (used in) /from financing activities",
            "Net cash flows (used in) / from financing activities",
            "Net cash flows (used in)/from financing activities",
            "Net cash flows (used in) /from financing activities",
            "Net cash flow from / (used in) financing activities",
            "Net cash flows from / (used in) financing activities",
            "Net cash flow from/(used in) financing activities",
            "Net cash flows from/(used in) financing activities",
            "Net cash flow from (used in) financing activities",
            "Net cash flows from (used in) financing activities",
            "Cash flows (used in) / from financing activities",
            "Cash flows (used in)/from financing activities",
            "Cash flows (used in) /from financing activities",
            "Cash flows from / (used in) financing activities",
            "Cash flows from/(used in) financing activities",
            "Net cash generated from financing activities",
            "Net cash generated by financing activities",
            "Financing cash flow",
            "Cash flow from financing activities",
            "Cash flows from financing activities",
        ],
        "financing_cash_flow",
        fields,
    )

    # -----------------------------------------------------
    # FX
    # -----------------------------------------------------

    find_labeled_values(
        lines,
        [
            "Effect of exchange rate changes",
            "Effect of foreign exchange rate changes",
            "Effect of exchange fluctuation on translation reserve",
            "Effect of fluctuation in foreign currency translation reserve",
            "Effect of fluctuation in foreign currency translation",
            "Effect of exchange fluctuation",
            "Foreign exchange adjustment",
            "FX translation adjustment",
            "Exchange difference",
        ],
        "fx_translation_adjustment",
        fields,
    )

    # -----------------------------------------------------
    # AMALGAMATION
    # -----------------------------------------------------

    find_labeled_values(
        lines,
        [
            "Cash and cash equivalents on amalgamation",
            "Cash and cash equivalents received on amalgamation",
            "Cash and cash equivalents acquired on amalgamation",
            "Cash on amalgamation",
        ],
        "cash_on_amalgamation",
        fields,
    )

    # -----------------------------------------------------
    # OPENING CASH
    # -----------------------------------------------------

    find_labeled_values(
        lines,
        [
            "Cash and cash equivalents at beginning",
            "Cash and cash equivalents at the beginning",
            "Cash and cash equivalents at the beginning of the year",
            "Cash and cash equivalents as at April 1st",
            "Cash and cash equivalents as at April 1",
            "Cash and cash equivalents at April 1st",
            "Cash and cash equivalents at April 1",
            "Cash and cash equivalents as at April 1st (Schedule 6 + 7)",
            "Cash and cash equivalents as at April 1 (Schedule 6 + 7)",
            "Opening cash",
            "Opening cash balance",
        ],
        "opening_cash",
        fields,
    )

    # -----------------------------------------------------
    # NET CHANGE
    # -----------------------------------------------------

    find_labeled_values(
        lines,
        [
            "Net change in cash",
            "Net increase in cash",
            "Net decrease in cash",
            "Net increase/(decrease) in cash",
            "Net increase / (decrease) in cash",
            "Net increase/(decrease) in cash and cash equivalents",
            "Net increase / (decrease) in cash and cash equivalents",
            "Net change in cash and cash equivalents",
            "Net increase in cash and cash equivalents",
            "Net decrease in cash and cash equivalents",
        ],
        "net_change_in_cash",
        fields,
    )

    # -----------------------------------------------------
    # CLOSING CASH
    # -----------------------------------------------------

    find_labeled_values(
        lines,
        [
            "Cash and cash equivalents at end",
            "Cash and cash equivalents at the end",
            "Cash and cash equivalents at the end of the year",
            "Cash and cash equivalents as at March 31st",
            "Cash and cash equivalents as at March 31",
            "Cash and cash equivalents at March 31st",
            "Cash and cash equivalents at March 31",
            "Cash and cash equivalents as at the year end",
            "Cash and cash equivalents at the year end",
            "Cash and cash equivalents as at the year end (Schedule 6 + 7)",
            "Cash and cash equivalents at the year end (Schedule 6 + 7)",
            "Closing cash",
            "Closing cash balance",
        ],
        "closing_cash",
        fields,
    )

    return {
        "document_type": "cash_flow_statement",
        "statement_period": statement_period,
        "currency": currency,
        "fields": fields,
        "line_items": [],
    }


# =========================================================
# INVOICE
# =========================================================

def extract_invoice_number(lines, fields):

    patterns = [
        r"invoice\s*(?:number|no\.?|#)\s*[:\-]?\s*(.+)",
        r"inv(?:oice)?\.?\s*(?:number|no\.?|#)\s*[:\-]?\s*(.+)",
    ]

    for line in lines:

        clean = line.strip()

        for pattern in patterns:

            match = re.search(
                pattern,
                clean,
                re.IGNORECASE,
            )

            if match:

                value = match.group(1).strip()

                if value:
                    fields["invoice_number"] = value
                    return


def extract_invoice_party(
    lines,
    fields,
    keywords,
    field_name,
):

    normalized_keywords = [
        normalize_label(keyword)
        for keyword in keywords
    ]

    for index, line in enumerate(lines):

        normalized = normalize_label(line)

        if not any(
            keyword in normalized
            for keyword in normalized_keywords
        ):
            continue

        # Label: value
        if ":" in line:

            value = line.split(
                ":",
                1,
            )[1].strip()

            if value:
                fields[field_name] = value
                return

        # Label - value
        if "-" in line:

            parts = line.split(
                "-",
                1,
            )

            if len(parts) == 2:

                value = parts[1].strip()

                if value:
                    fields[field_name] = value
                    return

        # Value on next line
        for next_line in lines[
            index + 1:index + 4
        ]:

            if not is_financial_number(
                next_line
            ):

                candidate = next_line.strip()

                if candidate:
                    fields[field_name] = candidate
                    return


def extract_invoice_labeled_number(
    lines,
    labels,
    field_name,
):

    normalized_labels = [
        normalize_label(label)
        for label in labels
    ]

    # -----------------------------------------------------
    # First pass: explicit label/value on same line.
    #
    # Search BOTTOM-UP. Column headers like "Net worth" /
    # "VAT" / "Gross worth" appear once near the top (as the
    # item table's header row) and again near the bottom (as
    # the summary table's header row) - only the bottom one
    # sits next to the real total. Scanning from the end means
    # the summary section is found before an unrelated header
    # collision higher up in the document.
    # -----------------------------------------------------

    for line in reversed(lines):

        # Never read an amount off an identifier line such
        # as "Tax Id: 964-99-8203" or "IBAN: GB31...". These
        # contain label words (e.g. "tax") purely by
        # coincidence, and their digit groups are not
        # amounts.
        if is_identifier_line(line):
            continue

        normalized = normalize_label(line)

        # Drop rate tokens ("10%") so a VAT/tax *rate* is
        # never mistaken for the VAT/tax *amount*.
        amount_line = strip_percentage_tokens(line)

        for target in normalized_labels:

            if not re.search(
                r"\b" + re.escape(target) + r"\b",
                normalized,
            ):
                continue

            # Find number anywhere on the line.
            number_matches = re.findall(
                r"-?\(?\d[\d,]*(?:\.\d+)?\)?",
                amount_line,
            )

            if number_matches:

                # Use the final number on the line.
                number = to_number(
                    number_matches[-1]
                )

                if number is not None:
                    return number

    # -----------------------------------------------------
    # Second pass: label followed by number, again scanned
    # bottom-up for the same reason as above. Because we are
    # going backwards, "next_line" (the value) is looked up
    # going forward from wherever the bottom-most matching
    # label line was found - the value still comes after its
    # label in the document's real reading order.
    # -----------------------------------------------------

    for index in range(len(lines) - 1, -1, -1):

        line = lines[index]

        if is_identifier_line(line):
            continue

        normalized = normalize_label(line)

        matched = any(
            labels_match(
                normalized,
                target,
            )
            or re.search(
                r"\b" + re.escape(target) + r"\b",
                normalized,
            )
            for target in normalized_labels
        )

        if not matched:
            continue

        for next_line in lines[
            index + 1:index + 5
        ]:

            if is_identifier_line(next_line):
                continue

            if is_financial_number(
                next_line
            ):

                return to_number(
                    next_line
                )

    return None


def extract_invoice_dates(
    lines,
    fields,
):

    date_pattern = (
        r"\b(?:"
        r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}"
        r"|"
        r"\d{4}[-/]\d{1,2}[-/]\d{1,2}"
        r"|"
        r"[A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4}"
        r"|"
        r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"
        r")\b"
    )

    for index, line in enumerate(lines):

        matches = re.findall(
            date_pattern,
            line,
        )

        lower = line.lower()

        # ---------------------------------------------------
        # Label and value on the same line.
        # ---------------------------------------------------

        if matches:

            if (
                "due date" in lower
                or "payment due" in lower
                or "due" in lower
            ):

                fields[
                    "due_date"
                ] = matches[-1]

            elif (
                "invoice date" in lower
                or "invoice issued" in lower
                or "issue date" in lower
            ):

                fields[
                    "invoice_date"
                ] = matches[-1]

            elif (
                "date" in lower
                and "due" not in lower
            ):

                if "invoice_date" not in fields:
                    fields[
                        "invoice_date"
                    ] = matches[0]

            continue

        # ---------------------------------------------------
        # Label alone on its own line (common with OCR output
        # from a table cell): look at the next couple of
        # lines for the actual date value.
        # ---------------------------------------------------

        is_due_label = (
            "due date" in lower
            or "payment due" in lower
            or lower.strip() == "due"
        )

        is_invoice_date_label = (
            "invoice date" in lower
            or "invoice issued" in lower
            or "issue date" in lower
            or "date of issue" in lower
            or (
                re.search(r"\bdate\b", lower)
                and "due" not in lower
            )
        )

        if not (is_due_label or is_invoice_date_label):
            continue

        for next_line in lines[
            index + 1:index + 3
        ]:

            next_matches = re.findall(
                date_pattern,
                next_line,
            )

            if not next_matches:
                continue

            if is_due_label:
                fields["due_date"] = next_matches[0]
            elif "invoice_date" not in fields:
                fields["invoice_date"] = next_matches[0]

            break


INVOICE_TABLE_HEADER_WORDS = {
    "no",
    "no.",
    "item",
    "item no",
    "description",
    "product",
    "service",
    "qty",
    "quantity",
    "um",
    "unit",
    "unit of measure",
    "price",
    "net price",
    "unit price",
    "net worth",
    "vat",
    "vat %",
    "gross worth",
    "amount",
    "total",
}

INVOICE_SUMMARY_LABELS = {
    "subtotal",
    "sub total",
    "net worth",
    "net amount",
    "tax",
    "vat",
    "vat rate",
    "discount",
    "shipping",
    "shipping and handling",
    "total",
    "grand total",
    "gross worth",
    "amount due",
    "balance due",
}


ADDRESS_HINT_PATTERN = re.compile(
    r"\b("
    r"street|st\.|suite|ste\.|ave|avenue|road|rd\.|"
    r"blvd|boulevard|drive|dr\.|lane|ln\.|apt|"
    r"apartment|floor|fl\.|highway|hwy|po box"
    r")\b",
    re.IGNORECASE,
)

# US-style "ST 12345" or "ST 12345-6789" trailing a city/state,
# and a bare 5-digit ZIP on its own - both mark an address line.
STATE_ZIP_PATTERN = re.compile(
    r"\b[A-Z]{2}\s+\d{5}(-\d{4})?\b"
)

BARE_ZIP_PATTERN = re.compile(
    r"^\d{5}(-\d{4})?$"
)


def is_address_line(line: str) -> bool:

    if ADDRESS_HINT_PATTERN.search(line):
        return True

    if STATE_ZIP_PATTERN.search(line):
        return True

    return False


# A row starts with a small leading item index: "1", "1.",
# either alone on its own line or followed by the rest of
# the row's text/numbers on the same line.
ITEM_ROW_START_PATTERN = re.compile(r"^\d{1,3}\.?(\s|$)")

# A real invoice amount always shows an explicit fractional
# part - "3.49", "17,45", "5,00" - one or two digits after a
# "." or ",". Plain integers (street numbers, suite numbers,
# ZIP codes, thousands-grouped numbers like "1,234") don't
# end this way, so this is a decimal-agnostic way to tell a
# genuine price/amount apart from an unrelated number.
DECIMAL_FRACTION_PATTERN = re.compile(r"[.,]\d{1,2}$")


def has_decimal_fraction(token: str) -> bool:
    return bool(DECIMAL_FRACTION_PATTERN.search(token))


def is_invoice_row_boundary(line: str) -> bool:
    """
    True once a line clearly belongs to the summary section
    (or repeats the table header) rather than an item row -
    used to stop collecting the last item's row so it doesn't
    swallow the totals that follow it.
    """

    normalized = normalize_label(line)

    if normalized == "summary":
        return True

    if normalized in INVOICE_SUMMARY_LABELS:
        return True

    if normalized in SUMMARY_LABEL_TO_FIELD:
        return True

    if normalized in INVOICE_TABLE_HEADER_WORDS:
        return True

    if all(
        word in INVOICE_TABLE_HEADER_WORDS
        for word in normalized.split()
        if word
    ):
        return True

    if is_identifier_line(line):
        return True

    return False


# =========================================================
# SUMMARY BLOCK ZIPPER
#
# When OCR fragments a table cell-by-cell, an invoice's
# summary section typically comes back as one contiguous run
# of column-header words ("VAT [%]", "Net worth", "VAT",
# "Gross worth") followed immediately by an equal-length run
# of values ("10%", "126.27", "12.63", "138.90"). A simple
# "find the label, grab the nearest number" search can't
# correctly align a header with its own column in that shape
# - "VAT" and "126.27" (Net worth's value) end up looking
# adjacent even though they belong to different columns. This
# pairs each label run with the value run right after it,
# position-for-position, which is the layout actually used.
# =========================================================

SUMMARY_LABEL_TO_FIELD = {
    "vat %": None,
    "vat [%]": None,
    "vat[%]": None,
    "vat rate": None,
    "vat percent": None,
    "net worth": "subtotal",
    "subtotal": "subtotal",
    "sub total": "subtotal",
    "net amount": "subtotal",
    "net subtotal": "subtotal",
    "vat": "tax",
    "tax": "tax",
    "tax amount": "tax",
    "sales tax": "tax",
    "gst": "tax",
    "igst": "tax",
    "cgst": "tax",
    "sgst": "tax",
    "discount": "discount",
    "discount amount": "discount",
    "shipping": "shipping_and_handling",
    "shipping and handling": "shipping_and_handling",
    "freight": "shipping_and_handling",
    "delivery": "shipping_and_handling",
    "gross worth": "total",
    "total": "total",
    "grand total": "total",
    "invoice total": "total",
    "total amount": "total",
    "total due": "total",
    "amount due": "total",
    "balance due": "total",
}

VALUE_TOKEN_PATTERN = re.compile(
    r"-?\(?\d+(?:[.,]\d+)?\)?%?"
)


def strip_currency_symbols(token: str) -> str:
    return token.strip().lstrip("$₹€£").rstrip()


def find_summary_value_blocks(lines):
    """
    Scan for a run of recognized summary labels immediately
    followed by an equal-length run of values, and pair them
    column-for-column. Returns {field_name: number}.
    """

    usable_lines = [
        line
        for line in lines
        if not is_identifier_line(line)
    ]

    resolved = {}

    n = len(usable_lines)
    i = 0

    while i < n:

        normalized = normalize_label(
            usable_lines[i]
        )

        if normalized not in SUMMARY_LABEL_TO_FIELD:
            i += 1
            continue

        label_run = []
        j = i

        while j < n:

            candidate_normalized = normalize_label(
                usable_lines[j]
            )

            if candidate_normalized in SUMMARY_LABEL_TO_FIELD:

                label_run.append(
                    SUMMARY_LABEL_TO_FIELD[
                        candidate_normalized
                    ]
                )

                j += 1

            else:
                break

        value_run = []
        k = j

        while k < n:

            candidate = strip_currency_symbols(
                usable_lines[k]
            )

            if re.fullmatch(
                VALUE_TOKEN_PATTERN,
                candidate,
            ):

                value_run.append(candidate)
                k += 1

            else:
                break

        if (
            len(label_run) >= 1
            and len(value_run) == len(label_run)
        ):

            for field_name, raw_value in zip(
                label_run,
                value_run,
            ):

                if field_name is None:
                    continue

                if raw_value.endswith("%"):
                    continue

                number = to_number(raw_value)

                if (
                    number is not None
                    and field_name not in resolved
                ):
                    resolved[field_name] = number

        i = j if j > i else i + 1

    return resolved


def parse_invoice_item_row_text(row_text):
    """
    Parse one reconstructed item row (already joined into a
    single string) into a line-item dict, or None if it
    doesn't look like a real item row.
    """

    # Percentage tokens (VAT rate) are informative but
    # shouldn't be counted as quantity/price/amount values.
    vat_rate_match = re.search(
        r"(\d+(?:\.\d+)?)\s*%",
        row_text,
    )

    amount_text = strip_percentage_tokens(row_text)

    raw_tokens = amount_text.split()

    if not raw_tokens:
        return None

    # A bare 5-digit ZIP on its own token is never an
    # invoice amount.
    raw_tokens = [
        token
        for token in raw_tokens
        if not BARE_ZIP_PATTERN.match(token)
    ]

    if not raw_tokens:
        return None

    # The leading item index ("1", "1.") is a row index, not
    # a data value.
    if re.fullmatch(r"\d{1,3}\.?", raw_tokens[0]):
        raw_tokens = raw_tokens[1:]

    if not raw_tokens:
        return None

    numeric_tokens = [
        token
        for token in raw_tokens
        if is_financial_number(token)
    ]

    if len(numeric_tokens) < 2:
        return None

    # Require at least one genuine decimal amount (comma or
    # period) so a plain integer-only line (street number +
    # suite number, or a bare quantity) is never mistaken for
    # a priced item row.
    if not any(
        has_decimal_fraction(token)
        for token in numeric_tokens
    ):
        return None

    description_tokens = [
        token
        for token in raw_tokens
        if not is_financial_number(token)
    ]

    description = " ".join(
        description_tokens
    ).strip(" .:-")

    if not description:
        return None

    if normalize_label(description) in INVOICE_SUMMARY_LABELS:
        return None

    numeric_values = [
        to_number(token)
        for token in numeric_tokens
    ]

    numeric_values = [
        value
        for value in numeric_values
        if value is not None
    ]

    if len(numeric_values) < 2:
        return None

    item = {
        "description": description,
        "quantity": None,
        "unit_price": None,
        "amount": numeric_values[-1],
    }

    if len(numeric_values) == 4:

        # quantity, unit (net) price, net worth, gross worth
        # - the layout used by this invoice family. "amount"
        # is the net worth (pre-VAT), since that's what
        # quantity * unit_price reconciles to and what the
        # invoice subtotal is built from.

        item["quantity"] = numeric_values[0]
        item["unit_price"] = numeric_values[1]
        item["amount"] = numeric_values[2]
        item["gross_amount"] = numeric_values[3]

    elif len(numeric_values) == 3:

        item["quantity"] = numeric_values[0]
        item["unit_price"] = numeric_values[1]
        item["amount"] = numeric_values[2]

    elif len(numeric_values) == 2:

        item["quantity"] = numeric_values[0]
        item["unit_price"] = numeric_values[1]

    else:

        # More than 4 numeric tokens: layout is unclear, fall
        # back to first-two-as-qty/price and the last value
        # as the reported line amount.

        item["quantity"] = numeric_values[0]
        item["unit_price"] = numeric_values[1]
        item["amount"] = numeric_values[-1]

    if vat_rate_match:
        item["vat_rate"] = to_number(
            vat_rate_match.group(1)
        )

    return item


def extract_invoice_line_items_plain_text(lines):
    """
    Fallback line-item parser for OCR text that has no
    markdown "|" table formatting at all (the normal case
    for a plain OCR.space/docTR transcription of a scanned
    invoice).

    OCR of a table can come back two different ways:
      - one full row of text per line ("1. Widget 5 3.49
        17.45 10% 19.20"), or
      - one cell per line (each of "1.", "Widget", "5",
        "3.49", ... on its own line) - very common for
        table-aware OCR engines.

    Rather than assume either shape, item rows are
    reconstructed from item-index markers ("1.", "2.", ...):
    everything between one marker and the next is joined
    into a single row string and parsed the same way
    regardless of how many physical lines it came from. This
    also naturally absorbs a description that itself wraps
    across several lines.
    """

    usable_lines = [
        line
        for line in lines
        if "|" not in line
        and not is_identifier_line(line)
        and not is_address_line(line)
    ]

    row_start_indexes = [
        index
        for index, line in enumerate(usable_lines)
        if ITEM_ROW_START_PATTERN.match(line.strip())
    ]

    if not row_start_indexes:
        return []

    line_items = []

    for position, start in enumerate(row_start_indexes):

        if position + 1 < len(row_start_indexes):
            end = row_start_indexes[position + 1]
        else:
            # Last item: collect forward until something
            # that clearly belongs to the summary section
            # (or a header repeat), capped so a missed
            # boundary can't swallow the whole document.
            end = start + 1

            for candidate in range(
                start + 1,
                min(start + 20, len(usable_lines)),
            ):

                candidate_line = usable_lines[candidate]

                if is_invoice_row_boundary(
                    candidate_line
                ):
                    break

                end = candidate + 1

        row_text = " ".join(
            usable_lines[start:end]
        )

        item = parse_invoice_item_row_text(row_text)

        if item:
            line_items.append(item)

    return line_items


def extract_invoice_line_items(
    lines,
):

    line_items = []

    # -----------------------------------------------------
    # Markdown-table invoices
    # -----------------------------------------------------

    for line in lines:

        if "|" not in line:
            continue

        parts = parse_markdown_table_row(line)

        if len(parts) < 2:
            continue

        normalized_parts = [
            normalize_label(part)
            for part in parts
        ]

        # Skip obvious header rows.
        header_words = {
            "description",
            "item",
            "product",
            "service",
            "qty",
            "quantity",
            "price",
            "unit price",
            "amount",
            "total",
        }

        if any(
            part in header_words
            for part in normalized_parts
        ):
            continue

        numeric_parts = []

        for part in parts:

            if is_financial_number(part):

                number = to_number(part)

                if number is not None:
                    numeric_parts.append(number)

        if not numeric_parts:
            continue

        description = parts[0].strip()

        if not description:
            continue

        # Avoid treating totals as line items.
        if normalize_label(
            description
        ) in {
            "subtotal",
            "tax",
            "discount",
            "shipping",
            "shipping and handling",
            "total",
            "grand total",
            "amount due",
            "balance due",
        }:
            continue

        item = {
            "description": description,
            "quantity": None,
            "unit_price": None,
            "amount": numeric_parts[-1],
        }

        if len(numeric_parts) == 4:

            # quantity, unit (net) price, net worth, gross
            # worth. "amount" is the net worth (pre-VAT),
            # which is what quantity * unit_price reconciles
            # to and what the invoice subtotal sums from.

            item["quantity"] = numeric_parts[0]
            item["unit_price"] = numeric_parts[1]
            item["amount"] = numeric_parts[2]
            item["gross_amount"] = numeric_parts[3]

        elif len(numeric_parts) == 3:

            item["quantity"] = numeric_parts[0]
            item["unit_price"] = numeric_parts[1]
            item["amount"] = numeric_parts[2]

        elif len(numeric_parts) == 2:

            item["quantity"] = (
                numeric_parts[-2]
            )

            item["unit_price"] = (
                numeric_parts[-1]
            )

        elif len(numeric_parts) > 4:

            item["quantity"] = numeric_parts[0]
            item["unit_price"] = numeric_parts[1]
            item["amount"] = numeric_parts[-1]

        line_items.append(item)

    # -----------------------------------------------------
    # Plain-text invoices (no "|" table markup at all, the
    # normal case for raw OCR.space/docTR text)
    # -----------------------------------------------------

    if not line_items:

        line_items = (
            extract_invoice_line_items_plain_text(
                lines
            )
        )

    return line_items


def parse_invoice_ocr(text: str) -> dict:

    fields = {}

    lines = clean_lines(text)

    # -----------------------------------------------------
    # Invoice number
    # -----------------------------------------------------

    extract_invoice_number(
        lines,
        fields,
    )

    # -----------------------------------------------------
    # Vendor
    # -----------------------------------------------------

    extract_invoice_party(
        lines,
        fields,
        [
            "vendor",
            "seller",
            "supplier",
            "from",
            "bill from",
        ],
        "vendor_name",
    )

    # -----------------------------------------------------
    # Customer
    # -----------------------------------------------------

    extract_invoice_party(
        lines,
        fields,
        [
            "customer",
            "client",
            "buyer",
            "bill to",
            "sold to",
        ],
        "customer_name",
    )

    # -----------------------------------------------------
    # Dates
    # -----------------------------------------------------

    extract_invoice_dates(
        lines,
        fields,
    )

    # -----------------------------------------------------
    # Financial fields
    #
    # Try the summary block-zipper first (handles OCR that
    # fragments the summary table cell-by-cell), then fall
    # back to the label/value search for OCR that keeps a
    # label and its value on the same line.
    # -----------------------------------------------------

    summary_fields = find_summary_value_blocks(lines)

    subtotal = summary_fields.get("subtotal")

    if subtotal is None:
        subtotal = extract_invoice_labeled_number(
            lines,
            [
                "subtotal",
                "sub total",
                "net subtotal",
                "net amount",
                "net worth",
            ],
            "subtotal",
        )

    if subtotal is not None:
        fields["subtotal"] = subtotal

    tax = summary_fields.get("tax")

    if tax is None:
        tax = extract_invoice_labeled_number(
            lines,
            [
                "tax",
                "tax amount",
                "sales tax",
                "vat",
                "gst",
                "igst",
                "cgst",
                "sgst",
            ],
            "tax",
        )

    if tax is not None:
        fields["tax"] = tax

    discount = summary_fields.get("discount")

    if discount is None:
        discount = extract_invoice_labeled_number(
            lines,
            [
                "discount",
                "discount amount",
            ],
            "discount",
        )

    if discount is not None:
        fields["discount"] = discount

    shipping = summary_fields.get(
        "shipping_and_handling"
    )

    if shipping is None:
        shipping = extract_invoice_labeled_number(
            lines,
            [
                "shipping",
                "shipping and handling",
                "shipping & handling",
                "freight",
                "delivery",
            ],
            "shipping_and_handling",
        )

    if shipping is not None:
        fields[
            "shipping_and_handling"
        ] = shipping

    total = summary_fields.get("total")

    if total is None:
        total = extract_invoice_labeled_number(
            lines,
            [
                "grand total",
                "invoice total",
                "total amount",
                "total due",
                "amount due",
                "balance due",
                "gross worth",
                "total",
            ],
            "total",
        )

    if total is not None:
        fields["total"] = total

    # -----------------------------------------------------
    # Currency
    # -----------------------------------------------------

    currency = extract_currency(lines)

    # -----------------------------------------------------
    # Line items
    # -----------------------------------------------------

    line_items = extract_invoice_line_items(
        lines
    )

    return {
        "document_type": "invoice",
        "statement_period": None,
        "currency": currency,
        "fields": fields,
        "line_items": line_items,
    }


# =========================================================
# DOCUMENT TYPE DISPATCHER
# =========================================================

def parse_ocr_text(
    text: str,
    document_type: str,
) -> dict:

    # API document types:
    #
    # Invoice
    # Balance Sheet
    # Profit & Loss
    # Cash Flow Statement
    #
    # Normalize them before dispatching.

    document_type_normalized = (
        document_type.strip().lower()
    )

    # -----------------------------------------------------
    # Balance Sheet
    # -----------------------------------------------------

    if document_type_normalized in {
        "balance sheet",
        "balance_sheet",
    }:

        return parse_balance_sheet_ocr(
            text
        )

    # -----------------------------------------------------
    # Profit & Loss
    # -----------------------------------------------------

    if document_type_normalized in {
        "profit & loss",
        "profit and loss",
        "profit_and_loss",
        "p&l",
        "p & l",
        "pnl",
    }:

        return parse_profit_and_loss_ocr(
            text
        )

    # -----------------------------------------------------
    # Cash Flow Statement
    # -----------------------------------------------------

    if document_type_normalized in {
        "cash flow statement",
        "cash_flow_statement",
        "cash flow",
        "cash_flow",
    }:

        return parse_cash_flow_ocr(
            text
        )

    # -----------------------------------------------------
    # Invoice
    # -----------------------------------------------------

    if document_type_normalized == "invoice":

        return parse_invoice_ocr(
            text
        )

    # -----------------------------------------------------
    # Unsupported document type
    # -----------------------------------------------------

    return {
        "document_type": document_type,
        "statement_period": None,
        "currency": None,
        "fields": {},
        "line_items": [],
    }


# =========================================================
# OCR FALLBACK PIPELINE
# =========================================================

def extract_with_ocr_fallback(
    file_path: str,
    document_type: str,
) -> dict:

    # =====================================================
    # 1. OCR.SPACE
    # =====================================================

    ocr_space_result = (
        extract_with_ocr_space(
            file_path
        )
    )

    if (
        ocr_space_result["status"]
        == "SUCCESS"
    ):

        text = ocr_space_result["text"]

        structured_data = parse_ocr_text(
            text,
            document_type,
        )

        return {
            "status": "SUCCESS",
            "fallback_provider": "ocr.space",
            "result": {
                "status": "SUCCESS",
                "provider": "ocr.space",
                "text": text,
                "page_count": (
                    ocr_space_result[
                        "page_count"
                    ]
                ),
                "extracted_data": structured_data,
            },
        }

    # =====================================================
    # 2. DOCTR
    # =====================================================

    try:
        from app.services.doctr_ocr_service import (
            extract_with_doctr
        )

        doctr_result = extract_with_doctr(
            file_path
        )

    except Exception as exc:
        doctr_result = {
            "status": "FAILED",
            "error": str(exc),
        }
    
    if (
        doctr_result["status"]
        == "SUCCESS"
    ):

        text = doctr_result["text"]

        structured_data = parse_ocr_text(
            text,
            document_type,
        )

        doctr_result[
            "extracted_data"
        ] = structured_data

        return {
            "status": "SUCCESS",
            "fallback_provider": "docTR",
            "result": doctr_result,
            "ocr_space_error": (
                ocr_space_result.get(
                    "error"
                )
            ),
        }

    # =====================================================
    # 3. EVERYTHING FAILED
    # =====================================================

    return {
        "status": "FAILED",
        "error": (
            "Both OCR fallback "
            "providers failed."
        ),
        "ocr_space_error": (
            ocr_space_result.get(
                "error"
            )
        ),
        "doctr_error": (
            doctr_result.get(
                "error"
            )
        ),
    }
