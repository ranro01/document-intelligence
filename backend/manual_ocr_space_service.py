import json

from app.services.ocr_space_service import extract_with_ocr_space


result = extract_with_ocr_space(
    "uploads/batch2-0499.jpg"
)

print(json.dumps(result, indent=2))