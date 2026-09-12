import json

from sqlalchemy.orm import Session

from app.models.document import Document


class DocumentRepository:

    @staticmethod
    def create(
        db: Session,
        filename: str,
        file_path: str,
    ) -> Document:
        document = Document(
            filename=filename,
            file_path=file_path,
        )

        db.add(document)
        db.commit()
        db.refresh(document)

        return document

    @staticmethod
    def get_by_id(
        db: Session,
        document_id: int,
    ) -> Document | None:
        return (
            db.query(Document)
            .filter(Document.id == document_id)
            .first()
        )

    @staticmethod
    def update_status(
        db: Session,
        document: Document,
        status: str,
    ) -> Document:
        document.status = status
        db.commit()
        db.refresh(document)

        return document

    @staticmethod
    def update_extracted_data(
        db: Session,
        document: Document,
        extracted_data: dict,
    ) -> Document:
        document.extracted_data = json.dumps(
            extracted_data
        )

        db.commit()
        db.refresh(document)

        return document