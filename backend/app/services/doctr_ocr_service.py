from doctr.io import DocumentFile
from doctr.models import ocr_predictor


# Load the OCR model once when the application starts.
ocr_model = ocr_predictor(
    pretrained=True,
)


def extract_with_doctr(file_path: str) -> dict:
    """
    Extract OCR text locally using docTR.
    """

    try:
        document = DocumentFile.from_images(file_path)

        result = ocr_model(document)

        exported = result.export()

        return {
            "status": "SUCCESS",
            "provider": "docTR",
            "text": result.render(),
            "pages": exported.get("pages", []),
        }

    except Exception as exc:
        return {
            "status": "FAILED",
            "error": str(exc),
        }