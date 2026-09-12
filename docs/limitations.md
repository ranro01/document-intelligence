# Limitations and Production Considerations

Neostats is a case-study implementation and is not intended to be treated as a production financial system without further engineering.

## Current limitations

- OCR quality depends on the quality and layout of the source document.
- Poor scans, unusual layouts, handwritten content, or heavily fragmented tables may reduce extraction accuracy.
- AI extraction can still produce incorrect values, so extracted financial information should be reviewed when accuracy is critical.
- OCR fallback services may have availability, rate-limit, or processing constraints.
- The current development database uses SQLite.
- Uploaded files are stored on the local filesystem during development.
- The current implementation is designed for documents of up to three pages.
- Currency formats and document layouts can vary significantly between organizations.
- Financial validation can only verify relationships for values that were successfully extracted and are applicable to the document.

## Production improvements

A production deployment would benefit from:

- PostgreSQL or another production-grade database.
- Object storage for uploaded documents.
- Authentication and authorization.
- Stronger file-security and malware scanning.
- Rate limiting and request-size controls.
- More comprehensive audit logging.
- Better OCR quality assessment and confidence scoring.
- Human review workflows for low-confidence extraction.
- More extensive document-layout handling.
- Automated monitoring and alerting.
- Secure secret management.
- Additional unit, integration, and end-to-end tests.