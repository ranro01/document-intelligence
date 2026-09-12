from pathlib import Path

import fitz
from PIL import Image


SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
MAX_PAGES = 3


def validate_document(file_path: str) -> dict:
    path = Path(file_path)
    extension = path.suffix.lower()

    if extension not in SUPPORTED_EXTENSIONS:
        return {
            "file_type": extension,
            "is_supported": False,
            "is_readable": False,
            "page_count": None,
            "status": "FAILED",
            "error": "Unsupported file type",
        }

    try:
        if extension == ".pdf":
            document = fitz.open(file_path)
            page_count = len(document)

            if page_count == 0:
                document.close()
                return {
                    "file_type": "application/pdf",
                    "is_supported": True,
                    "is_readable": False,
                    "page_count": 0,
                    "status": "FAILED",
                    "error": "PDF contains no pages",
                }

            if page_count > MAX_PAGES:
                document.close()
                return {
                    "file_type": "application/pdf",
                    "is_supported": True,
                    "is_readable": True,
                    "page_count": page_count,
                    "status": "FAILED",
                    "error": "Document exceeds the 3-page limit",
                }

            document.close()

            return {
                "file_type": "application/pdf",
                "is_supported": True,
                "is_readable": True,
                "page_count": page_count,
                "status": "PASS",
            }

        with Image.open(file_path) as image:
            image.verify()

        return {
            "file_type": f"image/{extension.lstrip('.')}",
            "is_supported": True,
            "is_readable": True,
            "page_count": 1,
            "status": "PASS",
        }

    except Exception as exc:
        return {
            "file_type": extension,
            "is_supported": True,
            "is_readable": False,
            "page_count": None,
            "status": "FAILED",
            "error": str(exc),
        }