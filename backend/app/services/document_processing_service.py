from app.services.document_extraction_service import extract_document
from app.services.ocr_fallback_service import extract_with_ocr_fallback
from app.services.financial_validation_service import validate_financial_data


def process_document(
    file_path: str,
    document_type: str,
) -> dict:
    """
    Main document processing pipeline.

    Primary:
        Qwen via Groq

    Fallback:
        OCR.space
        then local docTR

    Final:
        Financial validation
    """

    # 1. PRIMARY: Qwen / Groq
    qwen_result = extract_document(
        file_path,
        document_type,
    )

    if qwen_result["status"] == "SUCCESS":

        extracted_data = qwen_result.get(
            "extracted_data",
            {},
        )

        financial_validation = validate_financial_data(
            extracted_data
        )

        qwen_result["financial_validation"] = (
            financial_validation
        )

        return {
            "status": "SUCCESS",
            "provider": "qwen",
            "fallback_used": False,
            "result": qwen_result,
        }

    # 2. FALLBACK: OCR.space -> docTR
    ocr_result = extract_with_ocr_fallback(
        file_path,
        document_type,
    )

    if ocr_result["status"] == "SUCCESS":

        result = ocr_result.get(
            "result",
            {},
        )

        extracted_data = result.get(
            "extracted_data",
            {},
        )

        # OCR fallback currently stores structured
        # extraction inside result["extracted_data"].
        if not extracted_data:
            extracted_data = (
                result.get("result", {})
                .get("extracted_data", {})
            )

        financial_validation = validate_financial_data(
            extracted_data
        )

        result["financial_validation"] = (
            financial_validation
        )

        ocr_result["result"] = result

        return {
            "status": "SUCCESS",
            "provider": ocr_result[
                "fallback_provider"
            ],
            "fallback_used": True,
            "result": ocr_result,
            "primary_error": qwen_result.get(
                "error"
            ),
        }

    # 3. EVERYTHING FAILED
    return {
        "status": "FAILED",
        "provider": None,
        "fallback_used": True,
        "error": (
            "Primary extraction and both "
            "OCR fallbacks failed."
        ),
        "primary_error": qwen_result.get(
            "error"
        ),
        "ocr_fallback_error": ocr_result.get(
            "error"
        ),
    }