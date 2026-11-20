import json
import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from app import database
from app.database import create_schema, utc_now
from app.rules import evaluate_record, normalize_record
from app.workflow import process_pending_records, review_record


class DatabaseConnectionTests(unittest.TestCase):
    def test_connection_can_be_used_from_another_worker_thread(self):
        original_path = database.DATABASE_PATH
        self.addCleanup(setattr, database, "DATABASE_PATH", original_path)
        with tempfile.TemporaryDirectory() as temp_dir:
            database.DATABASE_PATH = Path(temp_dir) / "thread-test.sqlite3"
            with database.database_session() as connection:
                with ThreadPoolExecutor(max_workers=1) as executor:
                    result = executor.submit(
                        lambda: connection.execute("SELECT 1").fetchone()[0]
                    ).result()
            self.assertEqual(result, 1)


class ProcessingRulesTests(unittest.TestCase):
    def test_complete_record_is_automatically_classified(self):
        record = normalize_record(
            {
                "name": "  Alex   Morgan ",
                "category": "invoice",
                "amount": "125.50",
                "location": " North District ",
                "status": "open",
                "date": "2026-03-03",
            }
        )

        self.assertEqual(record["name"], "Alex Morgan")
        self.assertEqual(record["category"], "Invoice")
        self.assertEqual(record["status"], "OPEN")
        self.assertEqual(evaluate_record(record)["decision"], "AUTO_PROCESSED")

    def test_missing_and_conflicting_data_are_routed_to_review(self):
        missing = evaluate_record(
            {"name": "Taylor Reed", "category": "Claim", "amount": 50, "location": "", "status": "Open", "date": "2026-03-03"}
        )
        conflict = evaluate_record(
            {"name": "Taylor Reed", "category": "Invoice", "amount": 0, "location": "East", "status": "Open", "date": "2026-03-03"}
        )

        self.assertEqual(missing["decision"], "NEEDS_REVIEW")
        self.assertIn("location", missing["reason"])
        self.assertEqual(conflict["decision"], "NEEDS_REVIEW")
        self.assertEqual(conflict["confidence"], 0.58)


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        create_schema(self.connection)
        now = utc_now()
        self.connection.execute(
            """
            INSERT INTO records (id, data_json, status, rules_json, created_at, updated_at)
            VALUES (?, ?, 'NEW', '[]', ?, ?)
            """,
            (
                "REC-TEST",
                json.dumps({"name": "Jamie Park", "category": "Permit", "amount": 120, "location": "Central", "status": "Open", "date": "2026-03-03"}),
                now,
                now,
            ),
        )
        self.connection.execute(
            """
            INSERT INTO records (id, data_json, status, rules_json, created_at, updated_at)
            VALUES (?, ?, 'NEW', '[]', ?, ?)
            """,
            (
                "REC-REVIEW",
                json.dumps({"name": "Riley Stone", "category": "Claim", "amount": 40, "location": "", "status": "Open", "date": "2026-03-03"}),
                now,
                now,
            ),
        )

    def tearDown(self):
        self.connection.close()

    def test_processing_then_human_approval_updates_status_and_audit(self):
        result = process_pending_records(self.connection)
        decisions = {record["id"]: record["status"] for record in result}
        self.assertEqual(decisions["REC-TEST"], "AUTO_PROCESSED")
        self.assertEqual(decisions["REC-REVIEW"], "NEEDS_REVIEW")

        reviewed = review_record(self.connection, "REC-REVIEW", "approve")
        actions = [
            row["action"]
            for row in self.connection.execute(
                "SELECT action FROM events WHERE record_id = 'REC-REVIEW'"
            )
        ]
        automatic_actions = [
            row["action"]
            for row in self.connection.execute(
                "SELECT action FROM events WHERE record_id = 'REC-TEST'"
            )
        ]

        self.assertEqual(reviewed["status"], "APPROVED")
        self.assertEqual(reviewed["review_decision"], "APPROVE")
        self.assertIn("automatically_processed", automatic_actions)
        self.assertIn("reviewer_approved", actions)

    def test_only_review_items_can_be_approved(self):
        with self.assertRaises(ValueError):
            review_record(self.connection, "REC-TEST", "reject")

    def test_send_back_returns_review_item_to_new_queue(self):
        process_pending_records(self.connection)
        returned = review_record(self.connection, "REC-REVIEW", "send_back")
        self.assertEqual(returned["status"], "NEW")
        self.assertIsNone(returned["confidence"])
        self.assertEqual(process_pending_records(self.connection)[0]["status"], "NEEDS_REVIEW")


if __name__ == "__main__":
    unittest.main()
