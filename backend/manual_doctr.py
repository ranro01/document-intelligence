from doctr.io import DocumentFile
from doctr.models import ocr_predictor


IMAGE_PATH = "uploads/batch2-0499.jpg"

print("Loading docTR model...")

model = ocr_predictor(
    pretrained=True,
)

print("Running OCR...")

document = DocumentFile.from_images(IMAGE_PATH)

result = model(document)

print("\n===== OCR TEXT =====\n")
print(result.render())

print("\n===== JSON =====\n")
print(result.export())