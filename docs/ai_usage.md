# AI Usage Declaration

AI tools were used during the development of Neostats as development assistance.

The main uses of AI were:

- Helping design and refine the document extraction prompts.
- Assisting with Python implementation and debugging.
- Helping investigate OCR and document-processing issues.
- Reviewing API and frontend implementation ideas.
- Assisting with documentation and project structure.

The final system architecture, application logic, validation rules, testing, configuration, and integration were reviewed and tested during development.

The financial validation layer is intentionally deterministic. Calculations such as invoice totals, line-item amounts, Balance Sheet checks, Profit & Loss checks, and Cash Flow checks are performed by application code rather than being delegated to an AI model.

AI-generated suggestions were treated as development assistance and were tested against the actual application before being included.