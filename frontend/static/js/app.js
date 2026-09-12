const API_BASE = "/api/v1";


// ============================================================
// ELEMENTS
// ============================================================

const documentType =
    document.getElementById("documentType");

const fileInput =
    document.getElementById("fileInput");

const processButton =
    document.getElementById("processButton");

const refreshButton =
    document.getElementById("refreshButton");

const uploadMessage =
    document.getElementById("uploadMessage");

const documentsTableBody =
    document.getElementById("documentsTableBody");

const resultSection =
    document.getElementById("resultSection");

const resultTitle =
    document.getElementById("resultTitle");

const resultStatus =
    document.getElementById("resultStatus");

const fieldsContainer =
    document.getElementById("fieldsContainer");

const lineItemsSection =
    document.getElementById("lineItemsSection");

const lineItemsContainer =
    document.getElementById("lineItemsContainer");

const validationSection =
    document.getElementById("validationSection");

const validationSummary =
    document.getElementById("validationSummary");

const validationChecks =
    document.getElementById("validationChecks");

const processingSection =
    document.getElementById("processingSection");

const processingInfo =
    document.getElementById("processingInfo");

const rawJson =
    document.getElementById("rawJson");

const heroImage =
    document.getElementById("heroImage");

const paginationProgress =
    document.getElementById("paginationProgress");


// ============================================================
// SECURITY / DISPLAY HELPERS
// ============================================================

function escapeHtml(value) {

    if (value === null || value === undefined) {
        return "";
    }

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function formatFieldName(key) {

    return String(key)
        .replaceAll("_", " ")
        .replace(/\b\w/g, char => char.toUpperCase());
}


function displayValue(value) {

    if (
        value === null ||
        value === undefined ||
        value === ""
    ) {
        return "Missing / null";
    }

    if (typeof value === "object") {
        return JSON.stringify(value);
    }

    return String(value);
}


function getStatusClass(status) {

    const value =
        String(status || "")
            .toUpperCase();

    if (value === "PASS") {
        return "status-pass";
    }

    if (
        value === "FAILED" ||
        value === "FAIL"
    ) {
        return "status-failed";
    }

    return "status-na";
}


function showMessage(message, type) {

    uploadMessage.textContent =
        message;

    uploadMessage.className =
        `message message-${type}`;
}


// ============================================================
// SCROLL PARALLAX
// ============================================================

let scrollTicking = false;


function updateScrollAnimation() {

    const scrollY =
        window.scrollY || 0;

    const hero =
        document.querySelector(".hero");

    const heroHeight =
        hero?.offsetHeight || 1;


    // Move the horse subtly.

    if (heroImage) {

        const offset =
            Math.min(
                scrollY * 0.10,
                55
            );

        const scale =
            1.08 +
            Math.min(
                scrollY * 0.000035,
                0.035
            );

        heroImage.style.transform =
            `scale(${scale})
             translate3d(0, ${offset}px, 0)`;
    }


    // Update vertical progress indicator.

    if (paginationProgress) {

        const progress =
            Math.min(
                Math.max(
                    scrollY / heroHeight,
                    0
                ),
                1
            );

        paginationProgress.style.height =
            `${38 + progress * 62}%`;
    }


    scrollTicking = false;
}


window.addEventListener(
    "scroll",
    () => {

        if (!scrollTicking) {

            window.requestAnimationFrame(
                updateScrollAnimation
            );

            scrollTicking = true;
        }

    },
    { passive: true }
);


// ============================================================
// SCROLL REVEAL
// ============================================================

function setupScrollReveal() {

    const elements =
        document.querySelectorAll(
            ".upload-card, .history-card, .about-section"
        );


    if (!("IntersectionObserver" in window)) {

        elements.forEach(element => {

            element.classList.add(
                "is-visible"
            );

        });

        return;
    }


    const observer =
        new IntersectionObserver(
            entries => {

                entries.forEach(entry => {

                    if (entry.isIntersecting) {

                        entry.target.classList.add(
                            "is-visible"
                        );

                        observer.unobserve(
                            entry.target
                        );
                    }

                });

            },
            {
                threshold: 0.12
            }
        );


    elements.forEach(element => {

        element.classList.add(
            "reveal-on-scroll"
        );

        observer.observe(element);
    });
}


// ============================================================
// LOAD DOCUMENT HISTORY
// ============================================================

async function loadDocuments() {

    documentsTableBody.innerHTML = `
        <tr>
            <td colspan="4" class="empty">
                Loading documents...
            </td>
        </tr>
    `;


    try {

        const response =
            await fetch(
                `${API_BASE}/documents`
            );


        if (!response.ok) {

            throw new Error(
                "Could not load documents."
            );
        }


        const data =
            await response.json();


        /*
         * Your API returns an array for this endpoint.
         * This also handles a wrapped {documents: []}
         * response if the route changes later.
         */

        const documents =
            Array.isArray(data)
                ? data
                : (
                    Array.isArray(data.documents)
                        ? data.documents
                        : []
                );


        if (documents.length === 0) {

            documentsTableBody.innerHTML = `
                <tr>
                    <td colspan="4" class="empty">
                        No processed documents yet.
                    </td>
                </tr>
            `;

            return;
        }


        documentsTableBody.innerHTML = "";


        documents.forEach(document => {

            const row =
                document.createElement("tr");


            const status =
                document.processing_status ||
                document.status ||
                "UNKNOWN";


            row.innerHTML = `

                <td>
                    ${escapeHtml(
                        document.document_name ||
                        document.filename ||
                        "-"
                    )}
                </td>

                <td>
                    ${escapeHtml(
                        document.document_type ||
                        "-"
                    )}
                </td>

                <td>

                    <span
                        class="status ${getStatusClass(status)}"
                    >
                        ${escapeHtml(status)}
                    </span>

                </td>

                <td>

                    <button
                        type="button"
                        class="view-button"
                        data-document="${escapeHtml(
                            document.document_name ||
                            document.filename ||
                            ""
                        )}"
                    >
                        VIEW →
                    </button>

                </td>
            `;


            documentsTableBody.appendChild(
                row
            );
        });


        document
            .querySelectorAll(".view-button")
            .forEach(button => {

                button.addEventListener(
                    "click",
                    () => {

                        loadDocument(
                            button.dataset.document
                        );

                    }
                );

            });


    } catch (error) {

        console.error(
            "Dashboard error:",
            error
        );


        documentsTableBody.innerHTML = `
            <tr>
                <td colspan="4" class="empty">
                    Could not connect to the API.
                </td>
            </tr>
        `;
    }
}


// ============================================================
// PROCESS DOCUMENT
// ============================================================

async function processDocument() {

    const file =
        fileInput.files[0];


    if (!file) {

        showMessage(
            "Please select a document first.",
            "error"
        );

        return;
    }


    const formData =
        new FormData();


    formData.append(
        "file",
        file
    );


    formData.append(
        "document_type",
        documentType.value
    );


    processButton.disabled =
        true;


    processButton.innerHTML = `
        <span>PROCESSING</span>
        <span class="button-arrow">...</span>
    `;


    try {

        const response =
            await fetch(
                `${API_BASE}/documents/process`,
                {
                    method: "POST",
                    body: formData
                }
            );


        const data =
            await response.json();


        if (!response.ok) {

            throw new Error(
                data?.error?.message ||
                data?.detail ||
                "Document processing failed."
            );
        }


        const status =
            String(
                data.processing_status ||
                "UNKNOWN"
            ).toUpperCase();


        showMessage(
            `Processing complete — ${status}`,
            status === "PASS"
                ? "success"
                : "error"
        );


        renderResult(data);


        await loadDocuments();


    } catch (error) {

        console.error(
            "Processing error:",
            error
        );


        showMessage(
            error.message ||
            "Something went wrong.",
            "error"
        );


    } finally {

        processButton.disabled =
            false;


        processButton.innerHTML = `
            <span>PROCESS DOCUMENT</span>
            <span class="button-arrow">→</span>
        `;
    }
}


// ============================================================
// LOAD SINGLE DOCUMENT
// ============================================================

async function loadDocument(filename) {

    if (!filename) {
        return;
    }


    try {

        const response =
            await fetch(
                `${API_BASE}/documents/${encodeURIComponent(
                    filename
                )}`
            );


        if (!response.ok) {

            throw new Error(
                "Could not retrieve document."
            );
        }


        const data =
            await response.json();


        renderResult(data);


    } catch (error) {

        console.error(
            "Document loading error:",
            error
        );


        showMessage(
            error.message,
            "error"
        );
    }
}


// ============================================================
// RENDER COMPLETE RESULT
// ============================================================

function renderResult(data) {

    resultSection.classList.remove(
        "hidden"
    );


    resultTitle.textContent =
        data.document_name ||
        "Document Result";


    const status =
        String(
            data.processing_status ||
            "UNKNOWN"
        ).toUpperCase();


    resultStatus.className =
        `status ${getStatusClass(status)}`;


    resultStatus.textContent =
        `PROCESSING STATUS: ${status}`;


    renderFields(
        data.extracted_data
    );


    renderLineItems(
        data.extracted_data
    );


    renderValidation(
        data.validation
    );


    renderProcessing(
        data.processing_metadata
    );


    renderRawJson(
        data
    );


    resultSection.scrollIntoView({
        behavior: "smooth",
        block: "start"
    });
}


// ============================================================
// RENDER EXTRACTED FIELDS
// ============================================================

function renderFields(extractedData) {

    fieldsContainer.innerHTML = "";


    if (
        !extractedData ||
        typeof extractedData !== "object"
    ) {

        fieldsContainer.innerHTML = `
            <div class="field">

                <div class="field-name">
                    EXTRACTION
                </div>

                <div class="field-value field-null">
                    No extracted data.
                </div>

            </div>
        `;

        return;
    }


    const fields =
        (
            extractedData.fields &&
            typeof extractedData.fields === "object"
        )
            ? extractedData.fields
            : extractedData;


    Object.entries(fields)
        .forEach(([key, value]) => {

            if (
                key === "fields" ||
                key === "line_items"
            ) {
                return;
            }


            addField(
                formatFieldName(key),
                displayValue(value),
                value === null ||
                value === undefined ||
                value === ""
            );
        });


    // Add top-level metadata only when it
    // wasn't already represented.

    if (
        extractedData.document_type &&
        !fields.document_type
    ) {

        addField(
            "Document Type",
            extractedData.document_type
        );
    }


    if (
        extractedData.statement_period &&
        !fields.statement_period
    ) {

        addField(
            "Statement Period",
            extractedData.statement_period
        );
    }


    if (
        extractedData.currency &&
        !fields.currency
    ) {

        addField(
            "Currency",
            extractedData.currency
        );
    }
}


// ============================================================
// ADD FIELD CARD
// ============================================================

function addField(
    name,
    value,
    isMissing = false
) {

    const field =
        document.createElement("div");


    field.className =
        "field";


    field.innerHTML = `

        <div class="field-name">

            ${escapeHtml(name)}

        </div>


        <div class="field-value ${
            isMissing
                ? "field-null"
                : ""
        }">

            ${escapeHtml(value)}

        </div>

    `;


    fieldsContainer.appendChild(
        field
    );
}


// ============================================================
// RENDER LINE ITEMS
// ============================================================

function renderLineItems(extractedData) {

    lineItemsContainer.innerHTML = "";


    const items =
        extractedData?.line_items;


    if (
        !Array.isArray(items) ||
        items.length === 0
    ) {

        lineItemsSection.classList.add(
            "hidden"
        );

        return;
    }


    lineItemsSection.classList.remove(
        "hidden"
    );


    const columns = [
        ...new Set(
            items.flatMap(
                item =>
                    Object.keys(item || {})
            )
        )
    ];


    if (columns.length === 0) {

        lineItemsSection.classList.add(
            "hidden"
        );

        return;
    }


    const table =
        document.createElement("table");


    table.className =
        "line-items-table";


    table.innerHTML = `

        <thead>

            <tr>

                ${columns.map(column => `
                    <th>
                        ${escapeHtml(
                            formatFieldName(column)
                        )}
                    </th>
                `).join("")}

            </tr>

        </thead>


        <tbody>

            ${items.map(item => `

                <tr>

                    ${columns.map(column => `

                        <td>

                            ${escapeHtml(
                                displayValue(
                                    item?.[column]
                                )
                            )}

                        </td>

                    `).join("")}

                </tr>

            `).join("")}

        </tbody>
    `;


    lineItemsContainer.appendChild(
        table
    );
}


// ============================================================
// RENDER FINANCIAL VALIDATION
// ============================================================

function renderValidation(validation) {

    validationChecks.innerHTML = "";


    if (
        !validation ||
        typeof validation !== "object"
    ) {

        validationSection.classList.add(
            "hidden"
        );

        return;
    }


    validationSection.classList.remove(
        "hidden"
    );


    const overallStatus =
        String(
            validation.overall_status ||
            "NOT_APPLICABLE"
        ).toUpperCase();


    validationSummary.innerHTML = `

        <div class="validation-overall">

            <span>
                OVERALL STATUS
            </span>

            <strong
                class="status ${getStatusClass(
                    overallStatus
                )}"
            >
                ${escapeHtml(
                    overallStatus
                )}
            </strong>

        </div>

    `;


    const checks =
        Array.isArray(validation.checks)
            ? validation.checks
            : [];


    if (checks.length === 0) {

        validationChecks.innerHTML = `

            <div class="validation-empty">

                No applicable financial checks.

            </div>

        `;

        return;
    }


    checks.forEach(check => {

        const card =
            document.createElement("div");


        card.className =
            "validation-check";


        const status =
            String(
                check.status ||
                "NOT_APPLICABLE"
            ).toUpperCase();


        const operands =
            check.operands || {};


        card.innerHTML = `

            <div class="validation-check-header">


                <div>

                    <div class="validation-check-name">

                        ${escapeHtml(
                            formatFieldName(
                                check.name ||
                                "Validation Check"
                            )
                        )}

                    </div>


                    <div class="validation-formula">

                        ${escapeHtml(
                            check.formula ||
                            "Formula not available"
                        )}

                    </div>

                </div>


                <span
                    class="status ${getStatusClass(status)}"
                >
                    ${escapeHtml(status)}
                </span>


            </div>


            <div class="validation-values">


                <div>

                    <span>
                        OPERANDS
                    </span>

                    <strong>
                        ${escapeHtml(
                            JSON.stringify(
                                operands
                            )
                        )}
                    </strong>

                </div>


                <div>

                    <span>
                        CALCULATED
                    </span>

                    <strong>
                        ${escapeHtml(
                            displayValue(
                                check.calculated_value
                            )
                        )}
                    </strong>

                </div>


                <div>

                    <span>
                        REPORTED
                    </span>

                    <strong>
                        ${escapeHtml(
                            displayValue(
                                check.reported_value
                            )
                        )}
                    </strong>

                </div>


                <div>

                    <span>
                        VARIANCE
                    </span>

                    <strong>
                        ${escapeHtml(
                            displayValue(
                                check.variance
                            )
                        )}
                    </strong>

                </div>


            </div>

        `;


        validationChecks.appendChild(
            card
        );
    });
}


// ============================================================
// RENDER PROCESSING INFORMATION
// ============================================================

function renderProcessing(metadata) {

    processingInfo.innerHTML = "";


    if (
        !metadata ||
        typeof metadata !== "object"
    ) {

        processingSection.classList.add(
            "hidden"
        );

        return;
    }


    processingSection.classList.remove(
        "hidden"
    );


    Object.entries(metadata)
        .forEach(([key, value]) => {

            const item =
                document.createElement("div");


            item.className =
                "processing-item";


            item.innerHTML = `

                <span>

                    ${escapeHtml(
                        formatFieldName(key)
                    )}

                </span>


                <strong>

                    ${escapeHtml(
                        displayValue(value)
                    )}

                </strong>

            `;


            processingInfo.appendChild(
                item
            );
        });
}


// ============================================================
// RAW JSON
// ============================================================

function renderRawJson(data) {

    if (!rawJson) {
        return;
    }


    rawJson.textContent =
        JSON.stringify(
            data,
            null,
            2
        );
}


// ============================================================
// EVENTS
// ============================================================

processButton.addEventListener(
    "click",
    processDocument
);


refreshButton.addEventListener(
    "click",
    loadDocuments
);


// ============================================================
// INITIALIZE
// ============================================================

setupScrollReveal();

loadDocuments();

updateScrollAnimation();