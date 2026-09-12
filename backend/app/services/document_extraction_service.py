import base64
import json
from pathlib import Path

import fitz
from groq import Groq

from app.core.config import settings
from app.services.financial_validation_service import validate_financial_data


DOCUMENT_PROMPTS = {
    "invoice": """
Extract all visible invoice information.

Include:
- invoice number, date, due date
- vendor, customer
- currency
- subtotal, tax, discount, shipping/handling, total
- payment information if visible
- every line item with description, quantity, unit_price and amount
""",

    "balance_sheet": """
Extract all visible Balance Sheet information.

Include:
- company name
- reporting dates/periods
- currency
- every asset, liability, capital/equity line item
- total assets
- total liabilities/equity/capital and liabilities
- comparative values for every line item
""",

    "profit_and_loss": """
Extract all visible Profit and Loss information.

Include:
- company name
- reporting periods
- currency
- every income and expense line item
- revenue
- COGS/cost of sales
- gross profit
- operating expenses
- operating profit
- interest
- tax
- net profit
- comparative values
""",

    "cash_flow_statement": """
Extract all visible Cash Flow Statement information.

Include:
- company name
- reporting periods
- currency
- every operating, investing and financing line item
- operating cash flow
- investing cash flow
- financing cash flow
- FX/translation adjustment
- opening cash
- net change in cash
- closing cash
- comparative values
""",
}


# =========================================================
# GUARDRAILS
#
# These are the two failure modes that were actually observed
# from the OCR-fallback regex parser on real invoices:
#
#   1. An identifier (Tax Id, IBAN, invoice #) gets read as a
#      financial amount.
#   2. An address number (street number, suite number, ZIP)
#      gets read as a quantity/price/amount.
#
# A vision model can avoid both if it's told to explicitly,
# so this instruction is appended to every document type's
# prompt rather than left implicit.
# =========================================================

ANTI_CONFUSION_RULES = """
Critical extraction rules - read carefully:

- Distinguish identifiers (Tax ID, VAT ID, GSTIN, IBAN, SWIFT,
  account numbers, invoice/reference numbers) from monetary
  amounts. An identifier is never a financial value, even if
  it appears next to a currency symbol or in a table.
- Distinguish address components (street numbers, suite/unit
  numbers, ZIP/postal codes, phone numbers) from quantities,
  unit prices, or amounts. Numbers inside a mailing address
  are never line-item data.
- Do not guess or invent a value. If a field is not clearly
  visible, use null.
- Preserve the table's row/column structure exactly - do not
  merge, split, or reorder rows.
- Preserve decimals exactly as shown (e.g. 17.45, not 17 or
  1745).
- A value in parentheses or with a leading minus sign is
  negative.
- Only extract information that is visibly printed on the
  document.
"""


def encode_image(file_path: str) -> bytes:
    """Read an image file as bytes."""

    with open(file_path, "rb") as image_file:
        return image_file.read()


def pdf_to_images(file_path: str) -> list[bytes]:
    """Convert a PDF of up to 3 pages into PNG images."""

    pdf = fitz.open(file_path)

    try:
        if len(pdf) == 0:
            raise ValueError("PDF contains no pages.")

        if len(pdf) > 3:
            raise ValueError(
                "PDF contains more than 3 pages."
            )

        images = []

        for page in pdf:
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(2, 2),
                alpha=False,
            )

            images.append(
                pixmap.tobytes("png")
            )

        return images

    finally:
        pdf.close()


# =========================================================
# MIME TYPE
#
# BUG FIX: the previous version always labeled the data URL
# as "image/png", even for a raw .jpg/.jpeg upload. The model
# was then handed base64 JPEG bytes wrapped in a PNG-declared
# data URL, which is exactly the kind of mismatch that can
# make a vision model silently fail or mis-decode the image -
# a very plausible reason the primary Qwen extraction was
# failing before falling back to OCR at all.
# =========================================================

MIME_TYPES_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


def get_mime_type(suffix: str) -> str:
    return MIME_TYPES_BY_EXTENSION.get(
        suffix.lower(),
        "image/png",
    )


def extract_json(text: str) -> dict:
    """Parse JSON returned by the model, tolerating a
    ```json ... ``` markdown fence if the model adds one
    despite JSON mode being requested."""

    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "")
        text = text.strip()

    return json.loads(text)


def build_extraction_prompt(
    document_type: str,
) -> str:
    """Build a compact extraction prompt."""

    instructions = DOCUMENT_PROMPTS[
        document_type
    ]

    return f"""
You are a financial document extraction system.

Document type: {document_type}

{instructions}

{ANTI_CONFUSION_RULES}

Return ONLY valid JSON in this exact structure:

{{
  "document_type": "{document_type}",
  "company_name": null,
  "statement_period": null,
  "currency": null,
  "fields": {{}},
  "line_items": []
}}

Rules:
- Extract all meaningful visible financial information.
- Do not invent or infer missing values.
- Use null for missing values.
- Preserve actual line-item names.
- Monetary values must be numbers.
- Parentheses/bracketed values are negative.
- Preserve comparative-period values.
- For invoices, line_items must contain description, quantity,
  unit_price and amount where visible.
- Keep the JSON compact.
- Do not include explanations.
- Return JSON only.
"""


def extract_document(
    file_path: str,
    document_type: str = "invoice",
) -> dict:
    """
    Extract financial documents using Qwen through Groq.

    Supports PDF, JPG, JPEG and PNG.
    """

    path = Path(file_path)

    # ---------------------------------------------
    # 1. File check
    # ---------------------------------------------

    if not path.exists():
        return {
            "status": "FAILED",
            "error": "Document file not found.",
        }

    supported_extensions = {
        ".pdf",
        ".jpg",
        ".jpeg",
        ".png",
    }

    if path.suffix.lower() not in supported_extensions:
        return {
            "status": "FAILED",
            "error": (
                "Only PDF, JPG, JPEG and PNG "
                "files are supported."
            ),
        }

    # ---------------------------------------------
    # 2. Document type check
    # ---------------------------------------------

    supported_document_types = {
        "invoice",
        "balance_sheet",
        "profit_and_loss",
        "cash_flow_statement",
    }

    if document_type not in supported_document_types:
        return {
            "status": "FAILED",
            "error": (
                f"Unsupported document type: "
                f"{document_type}"
            ),
        }

    try:

        # -----------------------------------------
        # 3. Convert PDF to images / read image bytes
        # -----------------------------------------

        if path.suffix.lower() == ".pdf":
            page_images = pdf_to_images(
                str(path)
            )
            mime_type = "image/png"
        else:
            page_images = [
                encode_image(str(path))
            ]
            mime_type = get_mime_type(
                path.suffix
            )

        # -----------------------------------------
        # 4. Groq client
        # -----------------------------------------

        client = Groq(
            api_key=settings.groq_api_key
        )

        # -----------------------------------------
        # 5. Build multimodal request
        # -----------------------------------------

        content = [
            {
                "type": "text",
                "text": build_extraction_prompt(
                    document_type
                ),
            }
        ]

        for image_bytes in page_images:

            image_base64 = base64.b64encode(
                image_bytes
            ).decode("utf-8")

            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            f"data:{mime_type};base64,"
                            f"{image_base64}"
                        )
                    },
                }
            )

        # -----------------------------------------
        # 6. Qwen extraction
        #
        # BUG FIX: max_tokens=1000 was far too small for a
        # multi-page invoice with several line items - the
        # model's JSON was getting cut off mid-object, which
        # then failed to parse. Raised to a much safer budget
        # and switched to max_completion_tokens (the parameter
        # Groq's own docs use for this endpoint).
        #
        # response_format={"type": "json_object"} turns on
        # Groq/Qwen's JSON mode instead of only hoping the
        # prompt is followed.
        # -----------------------------------------

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            max_completion_tokens=900,
            temperature=0,
            response_format={"type": "json_object"},
        )

        choice = response.choices[0]

        raw_response = choice.message.content

        # -----------------------------------------
        # 7. Catch truncated output explicitly, instead of
        #    letting json.loads fail with a generic error.
        # -----------------------------------------

        if choice.finish_reason == "length":
            return {
                "status": "FAILED",
                "error": (
                    "Model output was truncated "
                    "(finish_reason=length). Increase "
                    "max_completion_tokens."
                ),
            }

        # -----------------------------------------
        # 8. Parse JSON
        # -----------------------------------------

        extracted_data = extract_json(
            raw_response
        )

        # -----------------------------------------
        # 9. Financial validation
        # -----------------------------------------

        financial_validation = (
            validate_financial_data(
                extracted_data
            )
        )

        # -----------------------------------------
        # 10. Return result
        # -----------------------------------------

        return {
            "status": "SUCCESS",
            "model_used": settings.groq_model,
            "fallback_used": False,
            "document_type": document_type,
            "page_count": len(page_images),
            "extracted_data": extracted_data,
            "financial_validation": (
                financial_validation
            ),
        }

    except json.JSONDecodeError as exc:

        return {
            "status": "FAILED",
            "error": (
                "Model returned invalid JSON: "
                f"{exc}"
            ),
        }

    except Exception as exc:

        return {
            "status": "FAILED",
            "error": str(exc),
        }