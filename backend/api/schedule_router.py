"""
backend/api/schedule_router.py
=================================
Medication schedule CRUD endpoints — user-scoped via JWT.
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from database import engine
from api.auth_router import decode_jwt

logger = logging.getLogger("medai.schedule")
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ScheduleCreateRequest(BaseModel):
    medication_name: str = Field(..., min_length=1)
    dosage: str = Field(..., min_length=1)
    time: str = Field(..., description="HH:MM format")
    frequency: Optional[str] = "daily"
    notes: Optional[str] = None


class ScheduleStatusRequest(BaseModel):
    status: str = Field(..., pattern=r"^(pending|done)$")


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _require_user(authorization: Optional[str]) -> int:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:].strip()
    payload = decode_jwt(token)
    return int(payload["sub"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", summary="List all schedule entries for user")
async def list_schedules(
    today_only: bool = False,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM medication_schedules WHERE user_id = :uid ORDER BY time ASC"),
            {"uid": user_id},
        ).fetchall()

        schedules = [dict(r._mapping) for r in rows]
        return JSONResponse({"schedules": schedules})


@router.post("", summary="Create a new medication schedule entry")
async def create_schedule(
    body: ScheduleCreateRequest,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)

    with engine.connect() as conn:
        try:
            entry_id = str(uuid.uuid4())
            conn.execute(
                text("""INSERT INTO medication_schedules
                       (id, user_id, medication_name, dosage, time, frequency, notes, status)
                       VALUES (:id, :uid, :name, :dose, :time, :freq, :notes, 'pending')"""),
                {"id": entry_id, "uid": user_id, "name": body.medication_name, 
                 "dose": body.dosage, "time": body.time, "freq": body.frequency, "notes": body.notes},
            )
            conn.commit()

            row = conn.execute(
                text("SELECT * FROM medication_schedules WHERE id = :id"), {"id": entry_id}
            ).fetchone()
            
            return JSONResponse({"schedule": dict(row._mapping), "ok": True})
        except Exception as e:
            conn.rollback()
            logger.exception("Error creating schedule")
            raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{schedule_id}/status", summary="Toggle done/pending status")
async def update_schedule_status(
    schedule_id: str,
    body: ScheduleStatusRequest,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        result = conn.execute(
            text("""UPDATE medication_schedules
                   SET status = :status, updated_at = CURRENT_TIMESTAMP
                   WHERE id = :sid AND user_id = :uid"""),
            {"status": body.status, "sid": schedule_id, "uid": user_id},
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Schedule entry not found")
        return JSONResponse({"ok": True, "status": body.status})


@router.delete("/{schedule_id}", summary="Delete a schedule entry")
async def delete_schedule(
    schedule_id: str,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM medication_schedules WHERE id = :sid AND user_id = :uid"),
            {"sid": schedule_id, "uid": user_id},
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Schedule entry not found")
        return JSONResponse({"ok": True})
