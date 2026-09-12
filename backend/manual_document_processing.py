import json

from app.services.document_processing_service import process_document


result = process_document(
    "uploads/batch2-0499.jpg"
)

print(json.dumps(result, indent=2))