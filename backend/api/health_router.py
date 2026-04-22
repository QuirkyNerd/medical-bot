"""
backend/api/health_router.py
==============================
User-scoped health data CRUD endpoints for vitals, records,
medicines, contacts, EHR profile, and medication logs using PostgreSQL.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import text

from database import engine
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
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM health_vitals WHERE user_id = :uid ORDER BY timestamp DESC"),
            {"uid": user_id}
        ).fetchall()
        return JSONResponse({"vitals": [dict(r._mapping) for r in rows]})


@router.post("/vitals")
async def upsert_vital(body: VitalIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        try:
            vid = body.id or str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO health_vitals (id, user_id, type, value, unit, timestamp, notes)
                VALUES (:id, :uid, :type, :val, :unit, :ts, :notes)
                ON CONFLICT(id) DO UPDATE SET
                    value=EXCLUDED.value, unit=EXCLUDED.unit,
                    timestamp=EXCLUDED.timestamp, notes=EXCLUDED.notes,
                    updated_at=CURRENT_TIMESTAMP
                WHERE health_vitals.user_id = :uid
            """), {"id": vid, "uid": user_id, "type": body.type, "val": body.value, 
                   "unit": body.unit, "ts": body.timestamp, "notes": body.notes})
            conn.commit()
            return JSONResponse({"ok": True, "id": vid})
        except Exception as e:
            conn.rollback()
            logger.exception("Error saving vital")
            raise HTTPException(status_code=500, detail=str(e))


@router.delete("/vitals/{vital_id}")
async def delete_vital(vital_id: str, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM health_vitals WHERE id = :vid AND user_id = :uid"),
            {"vid": vital_id, "uid": user_id}
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Vital not found")
        return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Records
# ---------------------------------------------------------------------------

@router.get("/records")
async def list_records(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM health_records WHERE user_id = :uid ORDER BY date DESC"),
            {"uid": user_id}
        ).fetchall()
        return JSONResponse({"records": [dict(r._mapping) for r in rows]})


@router.post("/records")
async def upsert_record(body: RecordIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        try:
            rid = body.id or str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO health_records (id, user_id, title, type, date, provider, notes)
                VALUES (:id, :uid, :title, :type, :date, :provider, :notes)
                ON CONFLICT(id) DO UPDATE SET
                    title=EXCLUDED.title, type=EXCLUDED.type,
                    date=EXCLUDED.date, provider=EXCLUDED.provider,
                    notes=EXCLUDED.notes, updated_at=CURRENT_TIMESTAMP
                WHERE health_records.user_id = :uid
            """), {"id": rid, "uid": user_id, "title": body.title, "type": body.type, 
                   "date": body.date, "provider": body.provider, "notes": body.notes})
            conn.commit()
            return JSONResponse({"ok": True, "id": rid})
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))


@router.delete("/records/{record_id}")
async def delete_record(record_id: str, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM health_records WHERE id = :rid AND user_id = :uid"),
            {"rid": record_id, "uid": user_id}
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Record not found")
        return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Medicines
# ---------------------------------------------------------------------------

@router.get("/medicines")
async def list_medicines(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM health_medicines WHERE user_id = :uid ORDER BY created_at DESC"),
            {"uid": user_id}
        ).fetchall()
        return JSONResponse({"medicines": [dict(r._mapping) for r in rows]})


@router.post("/medicines")
async def upsert_medicine(body: MedicineIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        try:
            mid = body.id or str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO health_medicines (id, user_id, name, dose, form, quantity)
                VALUES (:id, :uid, :name, :dose, :form, :qty)
                ON CONFLICT(id) DO UPDATE SET
                    name=EXCLUDED.name, dose=EXCLUDED.dose,
                    form=EXCLUDED.form, quantity=EXCLUDED.quantity,
                    updated_at=CURRENT_TIMESTAMP
                WHERE health_medicines.user_id = :uid
            """), {"id": mid, "uid": user_id, "name": body.name, "dose": body.dose, 
                   "form": body.form, "qty": body.quantity})
            conn.commit()
            return JSONResponse({"ok": True, "id": mid})
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))


@router.delete("/medicines/{medicine_id}")
async def delete_medicine(medicine_id: str, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM health_medicines WHERE id = :mid AND user_id = :uid"),
            {"mid": medicine_id, "uid": user_id}
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Medicine not found")
        return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# Contacts
# ---------------------------------------------------------------------------

@router.get("/contacts")
async def list_contacts(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM health_contacts WHERE user_id = :uid ORDER BY name ASC"),
            {"uid": user_id}
        ).fetchall()
        return JSONResponse({"contacts": [dict(r._mapping) for r in rows]})


@router.post("/contacts")
async def upsert_contact(body: ContactIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        try:
            cid = body.id or str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO health_contacts (id, user_id, name, role, phone, email)
                VALUES (:id, :uid, :name, :role, :phone, :email)
                ON CONFLICT(id) DO UPDATE SET
                    name=EXCLUDED.name, role=EXCLUDED.role,
                    phone=EXCLUDED.phone, email=EXCLUDED.email,
                    updated_at=CURRENT_TIMESTAMP
                WHERE health_contacts.user_id = :uid
            """), {"id": cid, "uid": user_id, "name": body.name, "role": body.role, 
                   "phone": body.phone, "email": body.email})
            conn.commit()
            return JSONResponse({"ok": True, "id": cid})
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))


@router.delete("/contacts/{contact_id}")
async def delete_contact(contact_id: str, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM health_contacts WHERE id = :cid AND user_id = :uid"),
            {"cid": contact_id, "uid": user_id}
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Contact not found")
        return JSONResponse({"ok": True})


# ---------------------------------------------------------------------------
# EHR Profile
# ---------------------------------------------------------------------------

@router.get("/ehr-profile")
async def get_ehr_profile(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT data FROM ehr_profiles WHERE user_id = :uid"),
            {"uid": user_id}
        ).fetchone()
        if not row:
            return JSONResponse({"ehr": {}})
        return JSONResponse({"ehr": json.loads(row[0])})


@router.post("/ehr-profile")
async def save_ehr_profile(request_data: Dict[str, Any], authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        try:
            profile_id = str(uuid.uuid4())
            data_json = json.dumps(request_data)
            conn.execute(text("""
                INSERT INTO ehr_profiles (id, user_id, data)
                VALUES (:id, :uid, :data)
                ON CONFLICT(user_id) DO UPDATE SET data=EXCLUDED.data, updated_at=CURRENT_TIMESTAMP
            """), {"id": profile_id, "uid": user_id, "data": data_json})
            conn.commit()
            return JSONResponse({"ok": True})
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Medication Logs
# ---------------------------------------------------------------------------

@router.get("/medication-logs")
async def list_medication_logs(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        rows = conn.execute(
            text("SELECT * FROM medication_logs WHERE user_id = :uid ORDER BY date DESC, time DESC"),
            {"uid": user_id}
        ).fetchall()
        return JSONResponse({"logs": [dict(r._mapping) for r in rows]})


@router.post("/medication-logs")
async def upsert_medication_log(body: MedicationLogIn, authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        try:
            lid = body.id or str(uuid.uuid4())
            conn.execute(text("""
                INSERT INTO medication_logs (id, user_id, medication_id, date, time, taken)
                VALUES (:id, :uid, :mid, :date, :time, :taken)
                ON CONFLICT(id) DO UPDATE SET
                    taken=EXCLUDED.taken, updated_at=CURRENT_TIMESTAMP
                WHERE medication_logs.user_id = :uid
            """), {"id": lid, "uid": user_id, "mid": body.medication_id, 
                   "date": body.date, "time": body.time, "taken": body.taken})
            conn.commit()
            return JSONResponse({"ok": True, "id": lid})
        except Exception as e:
            conn.rollback()
            raise HTTPException(status_code=500, detail=str(e))
