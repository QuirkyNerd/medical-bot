"""
backend/api/schedule_router.py
=================================
Medication schedule CRUD endpoints — user-scoped via JWT.

Endpoints:
  GET    /api/schedule               → today's and all schedules for user
  POST   /api/schedule               → create a new schedule entry
  PATCH  /api/schedule/{id}/status   → toggle done/pending
  DELETE /api/schedule/{id}          → delete schedule entry
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database import get_db
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
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM medication_schedules WHERE user_id = ? ORDER BY time ASC",
            (user_id,),
        ).fetchall()

        schedules = [dict(r) for r in rows]
        return JSONResponse({"schedules": schedules})
    finally:
        conn.close()


@router.post("", summary="Create a new medication schedule entry")
async def create_schedule(
    body: ScheduleCreateRequest,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    try:
        user_id = _require_user(authorization)
    except Exception as e:
        logger.error(f"Failed to authenticate user for schedule: {e}")
        raise e

    conn = get_db()
    try:
        entry_id = str(uuid.uuid4())
        logger.info(f"Creating schedule {entry_id} for user {user_id}")
        
        conn.execute(
            """INSERT INTO medication_schedules
               (id, user_id, medication_name, dosage, time, frequency, notes, status)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending')""",
            (entry_id, user_id, body.medication_name, body.dosage,
             body.time, body.frequency, body.notes),
        )
        conn.commit()

        row = conn.execute(
            "SELECT * FROM medication_schedules WHERE id = ?", (entry_id,)
        ).fetchone()
        logger.info(f"Schedule {entry_id} successfully created")
        return JSONResponse({"schedule": dict(row), "ok": True})
    except Exception as e:
        logger.exception("Error creating schedule:")
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.patch("/{schedule_id}/status", summary="Toggle done/pending status")
async def update_schedule_status(
    schedule_id: str,
    body: ScheduleStatusRequest,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        result = conn.execute(
            """UPDATE medication_schedules
               SET status = ?, updated_at = CURRENT_TIMESTAMP
               WHERE id = ? AND user_id = ?""",
            (body.status, schedule_id, user_id),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Schedule entry not found")
        return JSONResponse({"ok": True, "status": body.status})
    finally:
        conn.close()


@router.delete("/{schedule_id}", summary="Delete a schedule entry")
async def delete_schedule(
    schedule_id: str,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        result = conn.execute(
            "DELETE FROM medication_schedules WHERE id = ? AND user_id = ?",
            (schedule_id, user_id),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Schedule entry not found")
        return JSONResponse({"ok": True})
    finally:
        conn.close()
