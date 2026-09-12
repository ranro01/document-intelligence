import json

from app.services.doctr_ocr_service import extract_with_doctr


result = extract_with_doctr(
    "uploads/batch2-0499.jpg"
)

print(json.dumps(result, indent=2))