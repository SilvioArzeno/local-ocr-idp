# local-ocr-idp

A self-hosted, open-source replacement for Salesforce Einstein (MuleSoft) Intelligent Document Processing (IDP). Instead of paying for a cloud IDP pipeline, this project runs everything locally using a vision-capable LLM (Qwen), a lightweight HTTP server, and a simple UI for document submission and prompt configuration.

## What it does

Einstein IDP extracts structured data from documents (invoices, forms, contracts, etc.) by combining OCR with an LLM to classify content and return field-level results. This project replicates that workflow locally:

1. **Document upload** — submit a document (PDF, image) via the UI or REST API
2. **OCR / extraction** — a locally-running Qwen vision model reads the document and extracts text and structured fields based on a configurable prompt
3. **Results** — structured JSON output matching the fields you defined, returned via the API and displayed in the UI

## Stack

| Layer | Technology |
|-------|-----------|
| LLM / OCR | [Ollama](https://ollama.com) running Qwen (vision model) |
| API server | FastAPI |
| UI | Simple web interface for uploading documents and editing extraction prompts |

## Why

MuleSoft IDP is expensive and cloud-only. This project provides an equivalent workflow for teams that need document intelligence on-premise or at low cost, using open-weight models.

## License

GNU General Public License v3 — see [LICENSE](LICENSE).
