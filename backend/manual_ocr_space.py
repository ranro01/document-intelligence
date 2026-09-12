import requests

from app.core.config import settings


IMAGE_PATH = "uploads/batch2-0499.jpg"

url = "https://api.ocr.space/parse/image"

with open(IMAGE_PATH, "rb") as image_file:
    response = requests.post(
        url,
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

print("HTTP status:", response.status_code)
print(response.text)