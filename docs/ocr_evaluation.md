# OCR Framework Evaluation (CBK PDFs)

This document is a placeholder for manual notes when you evaluate OCR/text-
extraction frameworks on 5–10 sample CBK Treasury PDFs (bonds and bills).

| Framework / Pipeline         | Layout score (1–5) | Text quality | Table fidelity | Speed | Pros | Cons |
|-----------------------------|--------------------|--------------|----------------|-------|------|------|
| pdfplumber (text-only)      |                    |              |                |       |      |      |
| pdfplumber + ocrmypdf (*)   |                    |              |                |       |      |      |
| unstructured (*)            |                    |              |                |       |      |      |

(*) Optional pipelines to explore later; the current implementation uses
`pdfplumber` only (see `cbk_ocr.engine.TextFirstOcrEngine`).

