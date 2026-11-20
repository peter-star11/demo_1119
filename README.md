# RecordFlow

RecordFlow is a small local demo of automated record processing with human review. It uses mock records and deterministic rules only. It is an isolated POC, not the complete client system, and it has no external integrations.

## Run it

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). The app creates a local SQLite database and seeds sample records automatically.

## Simple demo

1. Click **Process new records**.
2. Show that clear records are processed automatically and exceptions are flagged.
3. Click **Approve** or **Reject** on a flagged record.
4. Open a record or check **Recent activity** to see its history.

Use **Reset demo** to restore the sample records for another run.

## What it demonstrates

- Rule-based normalization, classification, and confidence scoring.
- Automatic processing for complete, consistent records.
- Human approval or rejection for uncertain records.
- Record details and an event-based processing history.

The sample rules are in `app/rules.py`. The UI, API, workflow, and SQLite database are intentionally kept small. This POC does not use browser automation, scraping, OCR, an AI model, or client credentials.

## Tests

```powershell
python -m unittest discover -s tests -v
```

A production system would require client-approved rules, security, access controls, integrations, and operational monitoring. Those are outside this demo's scope.
# demo_1119
