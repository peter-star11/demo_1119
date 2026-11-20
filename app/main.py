from contextlib import asynccontextmanager
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.database import add_event, create_schema, database_session, serialize_record
from app.sample_data import seed_records
from app.workflow import process_pending_records, review_record


STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(application):
    with database_session() as connection:
        create_schema(connection)
        seed_records(connection)
    yield


app = FastAPI(title="Record Processing Dashboard", lifespan=lifespan)
app.mount("/assets", StaticFiles(directory=STATIC_DIR), name="assets")


def get_connection():
    with database_session() as connection:
        yield connection


class ReviewRequest(BaseModel):
    decision: Literal["approve", "reject", "send_back"]


def record_payload(row):
    return serialize_record(row)


@app.get("/")
def home():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/dashboard")
def dashboard(connection=Depends(get_connection)):
    counts = {
        row["status"]: row["count"]
        for row in connection.execute("SELECT status, COUNT(*) AS count FROM records GROUP BY status")
    }
    total = sum(counts.values())
    return {
        "total": total,
        "auto_processed": counts.get("AUTO_PROCESSED", 0),
        "needs_review": counts.get("NEEDS_REVIEW", 0),
        "completed": sum(counts.get(status, 0) for status in ("AUTO_PROCESSED", "APPROVED", "REJECTED")),
        "failed": counts.get("FAILED", 0),
        "new": counts.get("NEW", 0),
        "processing": counts.get("PROCESSING", 0),
        "status_counts": counts,
    }


@app.get("/api/records")
def records(status: str | None = None, connection=Depends(get_connection)):
    if status:
        rows = connection.execute(
            "SELECT * FROM records WHERE status = ? ORDER BY created_at DESC, id",
            (status.upper(),),
        ).fetchall()
    else:
        rows = connection.execute("SELECT * FROM records ORDER BY created_at DESC, id").fetchall()
    return [record_payload(row) for row in rows]


@app.get("/api/records/{record_id}")
def record_details(record_id: str, connection=Depends(get_connection)):
    row = connection.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    record = record_payload(row)
    record["events"] = [
        dict(event)
        for event in connection.execute(
            "SELECT action, result, details, created_at FROM events WHERE record_id = ? ORDER BY id",
            (record_id,),
        )
    ]
    return record


@app.get("/api/events")
def activity(connection=Depends(get_connection)):
    return [
        dict(row)
        for row in connection.execute(
            """
            SELECT events.id, events.record_id, events.action,
                   events.result, events.details, events.created_at
            FROM events JOIN records ON records.id = events.record_id
            ORDER BY events.id DESC LIMIT 100
            """
        )
        .fetchall()
    ]


@app.post("/api/process")
def run_processing(connection=Depends(get_connection)):
    processed = process_pending_records(connection)
    return {"processed": processed, "count": len(processed)}


@app.post("/api/records/{record_id}/review")
def submit_review(record_id: str, request: ReviewRequest, connection=Depends(get_connection)):
    try:
        row = review_record(connection, record_id, request.decision)
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    if row is None:
        raise HTTPException(status_code=404, detail="Record not found.")
    return record_payload(row)


@app.post("/api/demo/reset")
def reset_demo(connection=Depends(get_connection)):
    connection.execute("DELETE FROM events")
    connection.execute("DELETE FROM records")
    seed_records(connection)
    add_event(connection, "REC-2041", "demo_reset", "Demo data reset")
    return {"message": "Demo data has been reset."}
