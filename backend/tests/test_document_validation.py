from pathlib import Path

from PIL import Image

from app.services.document_validation_service import validate_document


def test_valid_image_passes(tmp_path):
    image_path = Path(tmp_path) / "valid_invoice.png"

    image = Image.new("RGB", (200, 200), "white")
    image.save(image_path)

    result = validate_document(str(image_path))

    assert result["is_supported"] is True
    assert result["is_readable"] is True
    assert result["page_count"] == 1
    assert result["status"] == "PASS"


def test_unsupported_file_fails(tmp_path):
    file_path = Path(tmp_path) / "document.txt"
    file_path.write_text("unsupported document")

    result = validate_document(str(file_path))

    assert result["is_supported"] is False
    assert result["is_readable"] is False
    assert result["status"] == "FAILED"


def test_corrupt_image_fails(tmp_path):
    image_path = Path(tmp_path) / "corrupt.png"
    image_path.write_bytes(b"not a real image")

    result = validate_document(str(image_path))

    assert result["is_supported"] is True
    assert result["is_readable"] is False
    assert result["status"] == "FAILED"