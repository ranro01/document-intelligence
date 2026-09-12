import base64
import json
from pathlib import Path

import fitz
from groq import Groq

from app.core.config import settings
from app.services.financial_validation_service import validate_financial_data


DOCUMENT_PROMPTS = {
    "invoice": """
Extract ALL meaningful visible information from this invoice.

Include:
- invoice number
- invoice date
- due date
- vendor/supplier
- customer/bill-to information
- currency
- subtotal
- tax
- discount if present
- shipping/handling if present
- total amount
- payment information if present
- every visible invoice line item

For line items include:
- description
- quantity
- unit price
- amount
""",

    "balance_sheet": """
Extract ALL meaningful visible information from this balance sheet.

Include:
- statement title
- company/entity name
- reporting period/date
- currency
- every visible financial line item
- total assets
- total liabilities
- total equity
- comparative period values if present

Preserve the actual line-item names from the document.
""",

    "profit_and_loss": """
Extract ALL meaningful visible information from this Profit and Loss statement.

Include:
- statement title
- company/entity name
- reporting period
- currency
- every visible income and expense line item
- revenue
- cost of sales / COGS
- gross profit
- operating expenses
- operating profit
- tax
- net profit
- comparative period values if present

Preserve the actual line-item names from the document.
""",

    "cash_flow_statement": """
Extract ALL meaningful visible information from this Cash Flow Statement.

Include:
- statement title
- company/entity name
- reporting period
- currency
- every visible cash-flow line item
- operating cash flow
- investing cash flow
- financing cash flow
- FX / translation adjustment if present
- opening cash
- net change in cash
- closing cash
- comparative period values if present

Preserve the actual line-item names from the document.
""",
}


def encode_image(file_path: str) -> bytes:
    """Read an image file as bytes."""
    with open(file_path, "rb") as image_file:
        return image_file.read()


def pdf_to_images(file_path: str) -> list[bytes]:
    """
    Convert PDF pages into PNG image bytes.

    The case study allows documents up to 3 pages.
    """

    pdf = fitz.open(file_path)

    if len(pdf) > 3:
        pdf.close()
        raise ValueError("PDF contains more than 3 pages.")

    images = []

    for page in pdf:
        pixmap = page.get_pixmap(
            matrix=fitz.Matrix(2, 2),
            alpha=False,
        )

        images.append(pixmap.tobytes("png"))

    pdf.close()

    return images


def extract_json(text: str) -> dict:
    """Parse JSON returned by the model."""

    text = text.strip()

    if text.startswith("```"):
        text = text.replace("```json", "", 1)
        text = text.replace("```", "")
        text = text.strip()

    return json.loads(text)


def build_prompt(document_type: str) -> str:
    """Build the extraction prompt for the selected document type."""

    type_instructions = DOCUMENT_PROMPTS.get(
        document_type,
        DOCUMENT_PROMPTS["invoice"],
    )

    return f"""
You are a financial document extraction system.

Document type:
{document_type}

{type_instructions}

Return ONLY valid JSON using this structure:

{{
  "document_type": "{document_type}",
  "document_metadata": {{}},
  "extracted_fields": {{}},
  "line_items": [],
  "confidence": 0.0,
  "evidence": []
}}

Rules:
- Extract ALL meaningful visible information.
- Do not invent values.
- Missing values must be null.
- Preserve the actual values from the document.
- Preserve the actual line-item names where possible.
- Monetary values must be numeric.
- Confidence must be between 0.0 and 1.0.
- Evidence should contain useful source text when available.
- Return JSON only.
"""


def extract_document(
    file_path: str,
    document_type: str = "invoice",
) -> dict:
    """
    Extract structured financial information using Qwen via Groq.

    Supports:
        PDF
        JPG
        JPEG
        PNG
    """

    path = Path(file_path)

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
            "error": "Only PDF, JPG, JPEG and PNG files are supported.",
        }

    supported_types = {
        "invoice",
        "balance_sheet",
        "profit_and_loss",
        "cash_flow_statement",
    }

    if document_type not in supported_types:
        return {
            "status": "FAILED",
            "error": f"Unsupported document type: {document_type}",
        }

    try:
        # ---------------------------------------------
        # Prepare document pages
        # ---------------------------------------------

        if path.suffix.lower() == ".pdf":
            page_images = pdf_to_images(str(path))
        else:
            page_images = [
                encode_image(str(path))
            ]

        # ---------------------------------------------
        # Create Qwen/Groq client
        # ---------------------------------------------

        client = Groq(
            api_key=settings.groq_api_key
        )

        content = [
            {
                "type": "text",
                "text": build_prompt(document_type),
            }
        ]

        # Add every page as an image
        for image_bytes in page_images:
            image_base64 = base64.b64encode(
                image_bytes
            ).decode("utf-8")

            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": (
                            "data:image/png;base64,"
                            f"{image_base64}"
                        )
                    },
                }
            )

        # ---------------------------------------------
        # Qwen extraction
        # ---------------------------------------------

        response = client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {
                    "role": "user",
                    "content": content,
                }
            ],
            max_tokens=4000,
            temperature=0,
        )

        raw_response = response.choices[0].message.content

        extracted_data = extract_json(
            raw_response
        )

        # ---------------------------------------------
        # Financial validation
        # ---------------------------------------------

        financial_validation = (
            validate_financial_data(
                extracted_data
            )
        )

        # ---------------------------------------------
        # Return structured result
        # ---------------------------------------------

        return {
            "status": "SUCCESS",
            "model_used": settings.groq_model,
            "fallback_used": False,
            "document_type": document_type,
            "page_count": len(page_images),
            "extracted_data": extracted_data,
            "financial_validation": financial_validation,
        }

    except json.JSONDecodeError as exc:
        return {
            "status": "FAILED",
            "error": f"Model returned invalid JSON: {exc}",
        }

    except Exception as exc:
        return {
            "status": "FAILED",
            "error": str(exc),
        }