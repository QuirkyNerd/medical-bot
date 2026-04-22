"""
backend/api/conversations_router.py
=====================================
Persistent chat history using PostgreSQL.
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from database import engine
from api.auth_router import decode_jwt

logger = logging.getLogger("medai.conversations")
router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class MessageIn(BaseModel):
    role: str = Field(..., pattern=r"^(user|assistant)$")
    content: str
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class ConversationUpsertRequest(BaseModel):
    id: Optional[str] = None        # if None → new conversation
    title: Optional[str] = None
    messages: List[MessageIn] = []


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _require_user(authorization: Optional[str]) -> int:
    """Decode JWT and return user_id (int). Raises 401 on failure."""
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:].strip()
    payload = decode_jwt(token)
    return int(payload["sub"])


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("", summary="List all conversations for authenticated user")
async def list_conversations(authorization: Optional[str] = Header(None)) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        rows = conn.execute(
            text("""
                SELECT c.id, c.title, c.created_at, c.updated_at,
                       (SELECT COUNT(id) FROM messages WHERE conversation_id = c.id) AS message_count,
                       (SELECT content FROM messages 
                        WHERE conversation_id = c.id 
                        ORDER BY created_at LIMIT 1) AS preview
                FROM conversations c
                WHERE c.user_id = :user_id
                ORDER BY c.updated_at DESC
            """),
            {"user_id": user_id},
        ).fetchall()

        conversations = [
            {
                "id": r[0],
                "title": r[1] or "Untitled Chat",
                "message_count": r[4],
                "preview": (r[5] or "")[:120],
                "created_at": r[2].isoformat() if r[2] else None,
                "updated_at": r[3].isoformat() if r[3] else None,
            }
            for r in rows
        ]
        return JSONResponse({"conversations": conversations})


@router.get("/{conversation_id}", summary="Fetch one conversation with all messages")
async def get_conversation(
    conversation_id: str,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        conv = conn.execute(
            text("SELECT id, title, created_at, updated_at FROM conversations WHERE id = :cid AND user_id = :uid"),
            {"cid": conversation_id, "uid": user_id},
        ).fetchone()

        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        msgs = conn.execute(
            text("SELECT role, content, metadata, created_at FROM messages WHERE conversation_id = :cid ORDER BY created_at ASC"),
            {"cid": conversation_id},
        ).fetchall()

        messages = []
        for m in msgs:
            meta = {}
            try:
                if m[2]:
                    meta = json.loads(m[2]) if isinstance(m[2], str) else m[2]
            except Exception:
                pass
            messages.append({
                "role": m[0],
                "content": m[1],
                "timestamp": m[3].isoformat() if m[3] else None,
                "metadata": meta,
            })

        return JSONResponse({
            "id": conv[0],
            "title": conv[1] or "Untitled Chat",
            "created_at": conv[2].isoformat() if conv[2] else None,
            "updated_at": conv[3].isoformat() if conv[3] else None,
            "messages": messages,
        })


@router.post("", summary="Create or update a conversation")
async def upsert_conversation(
    body: ConversationUpsertRequest,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        try:
            conv_id = body.id or str(uuid.uuid4())
            
            existing = conn.execute(
                text("SELECT id FROM conversations WHERE id = :cid AND user_id = :uid"),
                {"cid": conv_id, "uid": user_id},
            ).fetchone()

            if existing:
                conn.execute(
                    text("UPDATE conversations SET title = COALESCE(:title, title), updated_at = CURRENT_TIMESTAMP WHERE id = :cid"),
                    {"title": body.title, "cid": conv_id},
                )
                conn.execute(text("DELETE FROM messages WHERE conversation_id = :cid"), {"cid": conv_id})
            else:
                title = body.title
                if not title and body.messages:
                    first_user = next((m for m in body.messages if m.role == "user"), None)
                    title = (first_user.content[:80] + "...") if first_user and len(first_user.content) > 80 else (first_user.content if first_user else "New Chat")
                
                conn.execute(
                    text("INSERT INTO conversations (id, user_id, title) VALUES (:cid, :uid, :title)"),
                    {"cid": conv_id, "uid": user_id, "title": title},
                )

            for msg in body.messages:
                meta = json.dumps(msg.metadata) if msg.metadata else None
                conn.execute(
                    text("INSERT INTO messages (conversation_id, role, content, metadata) VALUES (:cid, :role, :content, :meta)"),
                    {"cid": conv_id, "role": msg.role, "content": msg.content, "meta": meta},
                )

            conn.commit()
            return JSONResponse({"id": conv_id, "ok": True})
        except Exception as e:
            conn.rollback()
            logger.exception("Upsert conversation failed")
            raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{conversation_id}", summary="Delete a conversation")
async def delete_conversation(
    conversation_id: str,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    with engine.connect() as conn:
        result = conn.execute(
            text("DELETE FROM conversations WHERE id = :cid AND user_id = :uid"),
            {"cid": conversation_id, "uid": user_id},
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return JSONResponse({"ok": True})
