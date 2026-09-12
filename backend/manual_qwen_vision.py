import base64

from groq import Groq

from app.core.config import settings


IMAGE_PATH = "uploads/batch2-0499.jpg"


def encode_image(path: str) -> str:
    with open(path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


image_base64 = encode_image(IMAGE_PATH)

client = Groq(api_key=settings.groq_api_key)

response = client.chat.completions.create(
    model=settings.groq_model,
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": """
Analyze this financial document.

Extract the information you can clearly identify.

Return ONLY valid JSON with these fields:
{
  "document_type": "",
  "invoice_number": "",
  "vendor_name": "",
  "customer_name": "",
  "invoice_date": "",
  "due_date": "",
  "subtotal": null,
  "tax": null,
  "total": null,
  "currency": "",
  "confidence": 0.0
}

Do not invent values. Use null or an empty string when a value is not visible.
""",
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{image_base64}"
                    },
                },
            ],
        }
    ],
    max_tokens=800,
    temperature=0,
)

print(response.choices[0].message.content)