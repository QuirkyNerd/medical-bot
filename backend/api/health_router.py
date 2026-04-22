"""
backend/api/health_router.py
==============================
User-scoped health data CRUD endpoints for vitals, records,
medicines, contacts, EHR profile, and medication logs.

Every table is filtered by user_id extracted from JWT.
No cross-user data leakage is possible.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import get_db
from api.auth_router import decode_jwt

logger = logging.getLogger("medai.health")
router = APIRouter()


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
# Schemas
# ---------------------------------------------------------------------------

class VitalIn(BaseModel):
    id: Optional[str] = None
    type: str
    value: str
    unit: str
    timestamp: str
    notes: Optional[str] = None


class RecordIn(BaseModel):
    id: Optional[str] = None
    title: str
    type: str
    date: str
    provider: Optional[str] = None
    notes: Optional[str] = None


class MedicineIn(BaseModel):
    id: Optional[str] = None
    name: str
    dose: str
    form: str
    quantity: int


class ContactIn(BaseModel):
    id: Optional[str] = None
    name: str
    role: str
    phone: Optional[str] = None
    email: Optional[str] = None


class MedicationLogIn(BaseModel):
    id: Optional[str] = None
    medication_id: str
    date: str
    time: str
    taken: bool


# ---------------------------------------------------------------------------
# Vitals
# ---------------------------------------------------------------------------

@router.get("/vitals")
async def list_vitals(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM health_vitals WHERE user_id = ? ORDER BY timestamp DESC",
            (user_id,)
        ).fetchall()
        return JSONResponse({"vitals": [dict(r) for r in rows]})
    finally:
        conn.close()


@router.post("/vitals")
async def upsert_vital(body: VitalIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        vid = body.id or str(uuid.uuid4())
        conn.execute("""
            INSERT INTO health_vitals (id, user_id, type, value, unit, timestamp, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                value=excluded.value, unit=excluded.unit,
                timestamp=excluded.timestamp, notes=excluded.notes,
                updated_at=CURRENT_TIMESTAMP
            WHERE health_vitals.user_id = ?
        """, (vid, user_id, body.type, body.value, body.unit, body.timestamp, body.notes, user_id))
        conn.commit()
        return JSONResponse({"ok": True, "id": vid})
    except Exception as e:
        conn.rollback()
        logger.exception("Error saving vital")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/vitals/{vital_id}")
async def delete_vital(vital_id: str, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        result = conn.execute(
            "DELETE FROM health_vitals WHERE id = ? AND user_id = ?",
            (vital_id, user_id)
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Vital not found")
        return JSONResponse({"ok": True})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@router.get("/records")
async def list_records(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM health_records WHERE user_id = ? ORDER BY date DESC",
            (user_id,)
        ).fetchall()
        return JSONResponse({"records": [dict(r) for r in rows]})
    finally:
        conn.close()


@router.post("/records")
async def upsert_record(body: RecordIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        rid = body.id or str(uuid.uuid4())
        conn.execute("""
            INSERT INTO health_records (id, user_id, title, type, date, provider, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                title=excluded.title, type=excluded.type,
                date=excluded.date, provider=excluded.provider,
                notes=excluded.notes, updated_at=CURRENT_TIMESTAMP
            WHERE health_records.user_id = ?
        """, (rid, user_id, body.title, body.type, body.date, body.provider, body.notes, user_id))
        conn.commit()
        return JSONResponse({"ok": True, "id": rid})
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        result = conn.execute(
            "DELETE FROM health_records WHERE id = ? AND user_id = ?",
            (record_id, user_id)
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        return JSONResponse({"ok": True})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Medicines
# ---------------------------------------------------------------------------

@router.get("/medicines")
async def list_medicines(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM health_medicines WHERE user_id = ? ORDER BY created_at DESC",
            (user_id,)
        ).fetchall()
        return JSONResponse({"medicines": [dict(r) for r in rows]})
    finally:
        conn.close()


@router.post("/medicines")
async def upsert_medicine(body: MedicineIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        mid = body.id or str(uuid.uuid4())
        conn.execute("""
            INSERT INTO health_medicines (id, user_id, name, dose, form, quantity)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, dose=excluded.dose,
                form=excluded.form, quantity=excluded.quantity,
                updated_at=CURRENT_TIMESTAMP
            WHERE health_medicines.user_id = ?
        """, (mid, user_id, body.name, body.dose, body.form, body.quantity, user_id))
        conn.commit()
        return JSONResponse({"ok": True, "id": mid})
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/medicines/{medicine_id}")
async def delete_medicine(medicine_id: str, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        result = conn.execute(
            "DELETE FROM health_medicines WHERE id = ? AND user_id = ?",
            (medicine_id, user_id)
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Medicine not found")
        return JSONResponse({"ok": True})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@router.get("/contacts")
async def list_contacts(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM health_contacts WHERE user_id = ? ORDER BY name ASC",
            (user_id,)
        ).fetchall()
        return JSONResponse({"contacts": [dict(r) for r in rows]})
    finally:
        conn.close()


@router.post("/contacts")
async def upsert_contact(body: ContactIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        cid = body.id or str(uuid.uuid4())
        conn.execute("""
            INSERT INTO health_contacts (id, user_id, name, role, phone, email)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name, role=excluded.role,
                phone=excluded.phone, email=excluded.email,
                updated_at=CURRENT_TIMESTAMP
            WHERE health_contacts.user_id = ?
        """, (cid, user_id, body.name, body.role, body.phone, body.email, user_id))
        conn.commit()
        return JSONResponse({"ok": True, "id": cid})
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        result = conn.execute(
            "DELETE FROM health_contacts WHERE id = ? AND user_id = ?",
            (contact_id, user_id)
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Contact not found")
        return JSONResponse({"ok": True})
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# EHR Profile
# ---------------------------------------------------------------------------

@router.get("/ehr-profile")
async def get_ehr_profile(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT data FROM ehr_profiles WHERE user_id = ?",
            (user_id,)
        ).fetchone()
        if not row:
            return JSONResponse({"ehr": {}})
        return JSONResponse({"ehr": json.loads(row["data"])})
    finally:
        conn.close()


@router.post("/ehr-profile")
async def save_ehr_profile(request_data: Dict[str, Any], authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        profile_id = str(uuid.uuid4())
        data_json = json.dumps(request_data)
        conn.execute("""
            INSERT INTO ehr_profiles (id, user_id, data)
            VALUES (?, ?, ?)
            ON CONFLICT DO UPDATE SET data=excluded.data, updated_at=CURRENT_TIMESTAMP
            WHERE ehr_profiles.user_id = ?
        """, (profile_id, user_id, data_json, user_id))
        conn.commit()
        return JSONResponse({"ok": True})
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Medication Logs
# ---------------------------------------------------------------------------

@router.get("/medication-logs")
async def list_medication_logs(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM medication_logs WHERE user_id = ? ORDER BY date DESC, time DESC",
            (user_id,)
        ).fetchall()
        return JSONResponse({"logs": [dict(r) for r in rows]})
    finally:
        conn.close()


@router.post("/medication-logs")
async def upsert_medication_log(body: MedicationLogIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        lid = body.id or str(uuid.uuid4())
        conn.execute("""
            INSERT INTO medication_logs (id, user_id, medication_id, date, time, taken)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                taken=excluded.taken, updated_at=CURRENT_TIMESTAMP
            WHERE medication_logs.user_id = ?
        """, (lid, user_id, body.medication_id, body.date, body.time, body.taken, user_id))
        conn.commit()
        return JSONResponse({"ok": True, "id": lid})
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()
