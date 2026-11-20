import json

from app.database import add_event, serialize_record, utc_now
from app.rules import evaluate_record, normalize_record


def process_pending_records(connection):
    rows = connection.execute(
        "SELECT * FROM records WHERE status = 'NEW' ORDER BY created_at, id"
    ).fetchall()
    processed = []

    for row in rows:
        record_id = row["id"]
        connection.execute(
            "UPDATE records SET status = 'PROCESSING', updated_at = ? WHERE id = ?",
            (utc_now(), record_id),
        )
        add_event(connection, record_id, "processing_started", "Processing started")

        data = normalize_record(json.loads(row["data_json"]))
        connection.execute(
            "UPDATE records SET data_json = ?, updated_at = ? WHERE id = ?",
            (json.dumps(data), utc_now(), record_id),
        )
        add_event(connection, record_id, "data_normalized", "Data normalized")

        result = evaluate_record(data)
        status = result["decision"]
        connection.execute(
            """
            UPDATE records
            SET status = ?, confidence = ?, decision = ?, reason = ?, rules_json = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                result["confidence"],
                status,
                result["reason"],
                json.dumps(result["rules"]),
                utc_now(),
                record_id,
            ),
        )
        add_event(
            connection,
            record_id,
            "rules_evaluated",
            f"{status.replace('_', ' ').title()} · {result['confidence']:.0%} confidence",
            result["reason"],
        )
        if status == "AUTO_PROCESSED":
            add_event(connection, record_id, "automatically_processed", "Automatically processed")
        else:
            add_event(connection, record_id, "flagged_for_review", "Flagged for human review", result["reason"])

        processed.append(
            {
                "id": record_id,
                "status": status,
                "confidence": result["confidence"],
            }
        )
    return processed


def review_record(connection, record_id, decision):
    row = connection.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        return None
    if row["status"] != "NEEDS_REVIEW":
        raise ValueError("Only records in the review queue can receive a reviewer decision.")

    actions = {
        "approve": ("APPROVED", "reviewer_approved", "Reviewer approved"),
        "reject": ("REJECTED", "reviewer_rejected", "Reviewer rejected"),
        "send_back": ("NEW", "sent_back_to_queue", "Sent back for reprocessing"),
    }
    status, action, result = actions[decision]
    review_decision = None if decision == "send_back" else decision.upper()
    connection.execute(
        "UPDATE records SET status = ?, review_decision = ?, updated_at = ? WHERE id = ?",
        (status, review_decision, utc_now(), record_id),
    )
    add_event(connection, record_id, action, result)
    if decision == "send_back":
        connection.execute(
            """
            UPDATE records SET confidence = NULL, decision = NULL, reason = NULL, rules_json = '[]'
            WHERE id = ?
            """,
            (record_id,),
        )
    return connection.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()


def record_from_row(row):
    return serialize_record(row)
