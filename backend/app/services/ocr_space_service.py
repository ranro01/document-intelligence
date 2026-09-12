import requests

from app.core.config import settings


OCR_SPACE_URL = "https://api.ocr.space/parse/image"


def extract_with_ocr_space(file_path: str) -> dict:
    """
    Extract OCR text using the OCR.space API.
    """

    try:
        with open(file_path, "rb") as image_file:
            response = requests.post(
                OCR_SPACE_URL,
                files={
                    "file": image_file,
                },
                data={
                    "apikey": settings.ocr_space_api_key,
                    "language": "eng",
                    "isTable": "true",
                    "OCREngine": "3",
                },
                timeout=60,
            )

        response.raise_for_status()

        result = response.json()

        if result.get("IsErroredOnProcessing"):
            return {
                "status": "FAILED",
                "error": result.get("ErrorMessage", "OCR.space processing failed"),
            }

        parsed_results = result.get("ParsedResults", [])

        if not parsed_results:
            return {
                "status": "FAILED",
                "error": "OCR.space returned no OCR results",
            }

        parsed_text = "\n".join(
            item.get("ParsedText", "")
            for item in parsed_results
        ).strip()

        return {
            "status": "SUCCESS",
            "provider": "ocr.space",
            "text": parsed_text,
            "page_count": len(parsed_results),
        }

    except requests.RequestException as exc:
        return {
            "status": "FAILED",
            "error": f"OCR.space request failed: {exc}",
        }

    except Exception as exc:
        return {
            "status": "FAILED",
            "error": str(exc),
        }