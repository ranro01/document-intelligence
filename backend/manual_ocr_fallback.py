import json

from app.services.ocr_fallback_service import extract_with_ocr_fallback


result = extract_with_ocr_fallback(
    "uploads/batch2-0499.jpg"
)

print(json.dumps(result, indent=2))