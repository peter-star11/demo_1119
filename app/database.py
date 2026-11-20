import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = Path(os.environ.get("RECORDS_DB_PATH", ROOT_DIR / "data" / "records.sqlite3"))


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


@contextmanager
def database_session():
    connection = connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def create_schema(connection):
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS records (
            id TEXT PRIMARY KEY,
            data_json TEXT NOT NULL,
            status TEXT NOT NULL,
            confidence REAL,
            decision TEXT,
            reason TEXT,
            rules_json TEXT NOT NULL DEFAULT '[]',
            review_decision TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id TEXT NOT NULL REFERENCES records(id) ON DELETE CASCADE,
            action TEXT NOT NULL,
            result TEXT NOT NULL,
            details TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_records_status ON records(status);
        CREATE INDEX IF NOT EXISTS idx_events_created_at ON events(created_at);
        """
    )


def serialize_record(row):
    record = dict(row)
    record["data"] = json.loads(record.pop("data_json"))
    record["rules"] = json.loads(record.pop("rules_json"))
    if "events" in record:
        record["events"] = [dict(event) for event in record["events"]]
    return record


def add_event(connection, record_id, action, result, details=""):
    connection.execute(
        "INSERT INTO events (record_id, action, result, details, created_at) VALUES (?, ?, ?, ?, ?)",
        (record_id, action, result, details, utc_now()),
    )
