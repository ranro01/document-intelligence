from pathlib import Path
import json

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.document import Document
from app.repositories.document_repository import DocumentRepository
from app.services.document_processing_service import process_document
from app.services.document_validation_service import validate_document


router = APIRouter(
    prefix="/api/v1/documents",
    tags=["Documents"],
)


# ============================================================
# Configuration
# ============================================================

UPLOAD_DIR = Path(__file__).resolve().parents[3] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_DOCUMENT_TYPES = {
    "Invoice",
    "Balance Sheet",
    "Profit & Loss",
    "Cash Flow Statement",
}


# ============================================================
# Helper: Extract structured data
# ============================================================

def extract_result_data(processing_result: dict) -> dict:
    """
    Extract structured data regardless of whether the result
    came from the primary Qwen extraction or an OCR fallback.
    """

    if not isinstance(processing_result, dict):
        return {}

    result = processing_result.get("result", {})

    if not isinstance(result, dict):
        return {}

    # --------------------------------------------------------
    # Primary extraction result
    # --------------------------------------------------------

    extracted_data = result.get("extracted_data")

    if isinstance(extracted_data, dict):
        return extracted_data

    # --------------------------------------------------------
    # OCR fallback result
    # --------------------------------------------------------

    nested_result = result.get("result")

    if isinstance(nested_result, dict):
        extracted_data = nested_result.get("extracted_data")

        if isinstance(extracted_data, dict):
            return extracted_data

    return {}


# ============================================================
# Helper: Extract financial validation
# ============================================================

def extract_financial_validation(processing_result: dict) -> dict:
    """
    Extract financial validation from either the primary
    model result or the OCR fallback result.
    """

    if not isinstance(processing_result, dict):
        return {}

    result = processing_result.get("result", {})

    if not isinstance(result, dict):
        return {}

    # --------------------------------------------------------
    # Primary extraction result
    # --------------------------------------------------------

    validation = result.get("financial_validation")

    if isinstance(validation, dict):
        return validation

    # --------------------------------------------------------
    # OCR fallback result
    # --------------------------------------------------------

    nested_result = result.get("result")

    if isinstance(nested_result, dict):
        validation = nested_result.get("financial_validation")

        if isinstance(validation, dict):
            return validation

    return {}


# ============================================================
# GET: List all processed documents
# ============================================================

@router.get("")
def list_documents(
    db: Session = Depends(get_db),
):
    """
    Return all processed documents for the dashboard.
    Newest documents appear first.
    """

    documents = (
        db.query(Document)
        .order_by(Document.created_at.desc())
        .all()
    )

    results = []

    for document in documents:

        stored_data = {}

        # ----------------------------------------------------
        # Load persisted structured JSON
        # ----------------------------------------------------

        if document.extracted_data:

            try:
                stored_data = json.loads(
                    document.extracted_data
                )

            except json.JSONDecodeError:

                stored_data = {
                    "extracted_data": document.extracted_data
                }

        # ----------------------------------------------------
        # New records contain the complete API response
        # ----------------------------------------------------

        if (
            isinstance(stored_data, dict)
            and "document_name" in stored_data
        ):
            results.append(stored_data)

        # ----------------------------------------------------
        # Backward compatibility for older DB records
        # ----------------------------------------------------

        else:

            results.append(
                {
                    "document_name": document.filename,
                    "processing_status": (
                        document.status.upper()
                        if document.status
                        else "UNKNOWN"
                    ),
                    "extracted_data": stored_data,
                }
            )

    return {
        "documents": results
    }


# ============================================================
# GET: Retrieve latest result by document name
# ============================================================

@router.get("/{document_name}")
def get_document(
    document_name: str,
    db: Session = Depends(get_db),
):
    """
    Return the latest stored processing result for a
    particular document filename.
    """

    document = (
        db.query(Document)
        .filter(
            Document.filename == document_name
        )
        .order_by(
            Document.created_at.desc()
        )
        .first()
    )

    # --------------------------------------------------------
    # Document not found
    # --------------------------------------------------------

    if not document:
        return {
            "error": "Document not found"
        }

    # --------------------------------------------------------
    # Return complete persisted response
    # --------------------------------------------------------

    if document.extracted_data:

        try:

            stored_data = json.loads(
                document.extracted_data
            )

            if isinstance(stored_data, dict):
                return stored_data

        except json.JSONDecodeError:
            pass

    # --------------------------------------------------------
    # Fallback response
    # --------------------------------------------------------

    return {
        "document_name": document.filename,
        "processing_status": (
            document.status.upper()
            if document.status
            else "UNKNOWN"
        ),
        "extracted_data": {},
        "validation": {},
        "file_validation": {},
        "processing_metadata": {},
    }


# ============================================================
# POST: Upload and process document
# ============================================================

@router.post("/process")
async def process_document_api(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
):
    """
    Upload, validate, extract and financially validate a
    financial document.

    Supported document types:
        - Invoice
        - Balance Sheet
        - Profit & Loss
        - Cash Flow Statement
    """

    # ========================================================
    # 1. Safe filename
    # ========================================================

    safe_filename = Path(
        file.filename or "unnamed_document"
    ).name


    # ========================================================
    # 2. Validate document type
    # ========================================================

    if document_type not in ALLOWED_DOCUMENT_TYPES:

        return {
            "document_name": safe_filename,
            "document_type": document_type,
            "processing_status": "FAILED",

            "file_validation": {
                "status": "FAILED",
                "error": (
                    f"Unsupported document type: "
                    f"{document_type}. "
                    f"Allowed types: "
                    f"{sorted(ALLOWED_DOCUMENT_TYPES)}"
                ),
            },

            "extracted_data": {},

            "validation": {},

            "processing_metadata": {},
        }


    # ========================================================
    # 3. Save uploaded file
    # ========================================================

    file_path = UPLOAD_DIR / safe_filename

    try:

        contents = await file.read()

        with open(file_path, "wb") as buffer:
            buffer.write(contents)

    except Exception as exc:

        return {
            "document_name": safe_filename,
            "document_type": document_type,
            "processing_status": "FAILED",

            "file_validation": {
                "status": "FAILED",
                "error": (
                    f"Could not save uploaded file: {exc}"
                ),
            },

            "extracted_data": {},

            "validation": {},

            "processing_metadata": {},
        }


    # ========================================================
    # 4. Validate file
    # ========================================================

    try:

        validation_result = validate_document(
            str(file_path)
        )

    except Exception as exc:

        validation_result = {
            "status": "FAILED",
            "error": (
                f"Document validation failed: {exc}"
            ),
        }


    # ========================================================
    # 5. Create DB record
    # ========================================================

    try:

        document = DocumentRepository.create(
            db=db,
            filename=safe_filename,
            file_path=str(file_path),
        )

    except Exception as exc:

        return {
            "document_name": safe_filename,
            "document_type": document_type,
            "processing_status": "FAILED",

            "file_validation": validation_result,

            "extracted_data": {},

            "validation": {},

            "processing_metadata": {
                "error": (
                    f"Database record creation failed: "
                    f"{exc}"
                ),
            },
        }


    # ========================================================
    # 6. Stop if file validation failed
    # ========================================================

    if validation_result.get("status") != "PASS":

        DocumentRepository.update_status(
            db=db,
            document=document,
            status="failed",
        )

        response = {
            "document_name": safe_filename,
            "document_type": document_type,
            "processing_status": "FAILED",

            "file_validation": validation_result,

            "extracted_data": {},

            "validation": {},

            "processing_metadata": {
                "provider": None,
                "fallback_used": False,
                "content_type": file.content_type,
            },
        }

        DocumentRepository.update_extracted_data(
            db=db,
            document=document,
            extracted_data=response,
        )

        return response


    # ========================================================
    # 7. AI / OCR document processing
    # ========================================================

    try:

        processing_result = process_document(
            str(file_path),
            document_type,
        )

    except Exception as exc:

        DocumentRepository.update_status(
            db=db,
            document=document,
            status="failed",
        )

        response = {
            "document_name": safe_filename,
            "document_type": document_type,
            "processing_status": "FAILED",

            "file_validation": validation_result,

            "extracted_data": {},

            "validation": {},

            "processing_metadata": {
                "provider": None,
                "fallback_used": False,
                "error": str(exc),
                "content_type": file.content_type,
            },
        }

        DocumentRepository.update_extracted_data(
            db=db,
            document=document,
            extracted_data=response,
        )

        return response


    # ========================================================
    # 8. Primary + fallback processing failed
    # ========================================================

    if processing_result.get("status") != "SUCCESS":

        DocumentRepository.update_status(
            db=db,
            document=document,
            status="failed",
        )

        response = {
            "document_name": safe_filename,
            "document_type": document_type,
            "processing_status": "FAILED",

            "file_validation": validation_result,

            "extracted_data": {},

            "validation": {},

            "processing_metadata": {
                "provider": processing_result.get(
                    "provider"
                ),

                "fallback_used": processing_result.get(
                    "fallback_used",
                    False,
                ),

                "primary_error": processing_result.get(
                    "primary_error"
                ),

                "ocr_fallback_error": processing_result.get(
                    "ocr_fallback_error"
                ),

                "content_type": file.content_type,
            },
        }

        DocumentRepository.update_extracted_data(
            db=db,
            document=document,
            extracted_data=response,
        )

        return response


    # ========================================================
    # 9. Extract structured result
    # ========================================================

    extracted_data = extract_result_data(
        processing_result
    )


    # ========================================================
    # 10. Extract financial validation
    # ========================================================

    financial_validation = extract_financial_validation(
        processing_result
    )


    # ========================================================
    # 11. Determine validation status
    # ========================================================

    validation_status = None

    if isinstance(
        financial_validation,
        dict,
    ):

        validation_status = financial_validation.get(
            "overall_status"
        )


    # ========================================================
    # 12. Determine final processing status
    #
    # IMPORTANT:
    #
    # NOT_APPLICABLE does NOT mean PASS.
    #
    # It means the particular financial validation could
    # not be performed because the required source fields
    # were not present.
    #
    # Only an actual FAILED validation makes the document
    # processing status FAILED here.
    # ========================================================

    if validation_status == "FAILED":

        final_status = "FAILED"

    elif not extracted_data:

        # Extraction succeeded technically, but returned
        # no structured information at all.
        final_status = "FAILED"

    else:

        # This includes:
        #
        #   PASS
        #   NOT_APPLICABLE
        #   missing overall validation object
        #
        # NOT_APPLICABLE itself is NOT converted into PASS.
        # The processing status simply remains successful
        # because there was no failed validation.
        final_status = "PASS"


    # ========================================================
    # 13. Update DB status
    # ========================================================

    db_status = (
        "processed"
        if final_status == "PASS"
        else "failed"
    )

    DocumentRepository.update_status(
        db=db,
        document=document,
        status=db_status,
    )


    # ========================================================
    # 14. Build final structured API response
    # ========================================================

    response = {
        "document_name": safe_filename,

        "document_type": document_type,

        "processing_status": final_status,

        "file_validation": validation_result,

        "extracted_data": extracted_data,

        "validation": financial_validation,

        "processing_metadata": {
            "provider": processing_result.get(
                "provider"
            ),

            "fallback_used": processing_result.get(
                "fallback_used",
                False,
            ),

            "content_type": file.content_type,
        },
    }


    # ========================================================
    # 15. Persist complete structured response
    # ========================================================

    DocumentRepository.update_extracted_data(
        db=db,
        document=document,
        extracted_data=response,
    )


    # ========================================================
    # 16. Return response
    # ========================================================

    return response