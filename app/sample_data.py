import json

from app.database import add_event, utc_now


SAMPLE_RECORDS = [
    {
        "id": "REC-2041",
        "data": {"name": "Jordan Ellis", "category": "Invoice", "amount": 1240.5, "location": "North District", "status": "Open", "date": "2026-03-02"},
        "status": "NEW",
    },
    {
        "id": "REC-2042",
        "data": {"name": "Mina Patel", "category": "Application", "amount": 675, "location": "", "status": "Open", "date": "2026-03-04"},
        "status": "NEW",
    },
    {
        "id": "REC-2043",
        "data": {"name": "Cedar Grove Holdings", "category": "Invoice", "amount": 4820, "location": "West District", "status": "Closed", "date": "2026-03-05"},
        "status": "NEW",
    },
    {
        "id": "REC-2044",
        "data": {"name": "Evelyn Brooks", "category": "Claim", "amount": 0, "location": "Central District", "status": "Open", "date": "2026-03-06"},
        "status": "NEW",
    },
    {
        "id": "REC-2045",
        "data": {"name": "Harbor Point Services", "category": "Permit", "amount": 890, "location": "East District", "status": "Active", "date": "2026-03-07"},
        "status": "NEW",
    },
    {
        "id": "REC-2046",
        "data": {"name": "Noah Williams", "category": "Application", "amount": 2300, "location": "South District", "status": "Open", "date": "2026-03-08"},
        "status": "NEW",
    },
    {
        "id": "REC-2047",
        "data": {"name": "Summit Ridge Partners", "category": "Invoice", "amount": 18750, "location": "North District", "status": "Open", "date": "2026-03-09"},
        "status": "NEW",
    },
    {
        "id": "REC-2034",
        "data": {"name": "Avery Chen", "category": "Permit", "amount": 410, "location": "West District", "status": "Active", "date": "2026-02-26"},
        "status": "AUTO_PROCESSED",
        "confidence": 0.96,
        "decision": "AUTO_PROCESSED",
        "reason": "Required fields and consistency checks passed.",
        "rules": ["required-fields", "non-negative-amount", "consistency-check", "confidence-threshold"],
    },
    {
        "id": "REC-2035",
        "data": {"name": "Lakeside Property Group", "category": "Invoice", "amount": 3390, "location": "Central District", "status": "Open", "date": "2026-02-27"},
        "status": "AUTO_PROCESSED",
        "confidence": 0.96,
        "decision": "AUTO_PROCESSED",
        "reason": "Required fields and consistency checks passed.",
        "rules": ["required-fields", "non-negative-amount", "consistency-check", "confidence-threshold"],
    },
    {
        "id": "REC-2036",
        "data": {"name": "Omar Rivera", "category": "Application", "amount": 960, "location": "East District", "status": "Open", "date": "2026-02-28"},
        "status": "AUTO_PROCESSED",
        "confidence": 0.96,
        "decision": "AUTO_PROCESSED",
        "reason": "Required fields and consistency checks passed.",
        "rules": ["required-fields", "non-negative-amount", "consistency-check", "confidence-threshold"],
    },
    {
        "id": "REC-2037",
        "data": {"name": "Priya Nair", "category": "Claim", "amount": 1500, "location": "", "status": "Open", "date": "2026-03-01"},
        "status": "NEEDS_REVIEW",
        "confidence": 0.34,
        "decision": "NEEDS_REVIEW",
        "reason": "Required information is missing: location.",
        "rules": ["required-fields"],
    },
    {
        "id": "REC-2038",
        "data": {"name": "Maple Street Cooperative", "category": "Invoice", "amount": 0, "location": "South District", "status": "Open", "date": "2026-03-01"},
        "status": "NEEDS_REVIEW",
        "confidence": 0.58,
        "decision": "NEEDS_REVIEW",
        "reason": "Conflicting information: invoice has a zero amount.",
        "rules": ["required-fields", "non-negative-amount", "consistency-check"],
    },
    {
        "id": "REC-2039",
        "data": {"name": "Sofia Martin", "category": "Application", "amount": 720, "location": "Central District", "status": "Closed", "date": "2026-03-01"},
        "status": "APPROVED",
        "confidence": 0.58,
        "decision": "NEEDS_REVIEW",
        "reason": "Conflicting information: record is marked closed but still has an outstanding amount.",
        "rules": ["required-fields", "non-negative-amount", "consistency-check"],
        "review_decision": "APPROVE",
    },
    {
        "id": "REC-2040",
        "data": {"name": "Pinecrest Office Supply", "category": "Invoice", "amount": 0, "location": "North District", "status": "Open", "date": "2026-03-02"},
        "status": "REJECTED",
        "confidence": 0.58,
        "decision": "NEEDS_REVIEW",
        "reason": "Conflicting information: invoice has a zero amount.",
        "rules": ["required-fields", "non-negative-amount", "consistency-check"],
        "review_decision": "REJECT",
    },
    {
        "id": "REC-2033",
        "data": {"name": "Riverside Community Trust", "category": "Claim", "amount": 2400, "location": "West District", "status": "Open", "date": "2026-02-25"},
        "status": "FAILED",
        "reason": "A simulated upstream validation error interrupted processing.",
    },
]


def seed_records(connection):
    if connection.execute("SELECT COUNT(*) FROM records").fetchone()[0]:
        return

    for item in SAMPLE_RECORDS:
        timestamp = utc_now()
        connection.execute(
            """
            INSERT INTO records
                (id, data_json, status, confidence, decision, reason, rules_json, review_decision, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["id"],
                json.dumps(item["data"]),
                item["status"],
                item.get("confidence"),
                item.get("decision"),
                item.get("reason"),
                json.dumps(item.get("rules", [])),
                item.get("review_decision"),
                timestamp,
                timestamp,
            ),
        )
        add_event(connection, item["id"], "record_received", "Record received")

        if item["status"] == "AUTO_PROCESSED":
            add_event(connection, item["id"], "data_normalized", "Data normalized")
            add_event(connection, item["id"], "rules_evaluated", "AUTO PROCESSED · 96% confidence", item["reason"])
            add_event(connection, item["id"], "automatically_processed", "Automatically processed")
        elif item["status"] == "NEEDS_REVIEW":
            add_event(connection, item["id"], "data_normalized", "Data normalized")
            add_event(
                connection,
                item["id"],
                "rules_evaluated",
                f"NEEDS REVIEW · {item['confidence']:.0%} confidence",
                item["reason"],
            )
            add_event(connection, item["id"], "flagged_for_review", "Flagged for human review", item["reason"])
        elif item["status"] in {"APPROVED", "REJECTED"}:
            add_event(connection, item["id"], "data_normalized", "Data normalized")
            add_event(connection, item["id"], "rules_evaluated", f"NEEDS REVIEW · {item['confidence']:.0%} confidence", item["reason"])
            add_event(connection, item["id"], "flagged_for_review", "Flagged for human review", item["reason"])
            action = "reviewer_approved" if item["status"] == "APPROVED" else "reviewer_rejected"
            add_event(connection, item["id"], action, f"Reviewer {item['status'].lower()}")
        elif item["status"] == "FAILED":
            add_event(connection, item["id"], "processing_started", "Processing started")
            add_event(connection, item["id"], "processing_failed", "Processing failed", item["reason"])
