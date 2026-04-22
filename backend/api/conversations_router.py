"""
backend/api/conversations_router.py
=====================================
Persistent chat history — CRUD endpoints bound to authenticated users via JWT.

Endpoints:
  GET  /api/conversations          → list all conversations for current user
  GET  /api/conversations/{id}     → fetch one conversation with all messages
  POST /api/conversations          → create or update a conversation
  DELETE /api/conversations/{id}   → delete a conversation
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database import get_db
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
    conn = get_db()
    try:
        rows = conn.execute(
            """
            SELECT c.id, c.title, c.created_at, c.updated_at,
                   COUNT(m.id) AS message_count,
                   (SELECT m2.content FROM messages m2
                    WHERE m2.conversation_id = c.id
                    ORDER BY m2.created_at LIMIT 1) AS preview
            FROM conversations c
            LEFT JOIN messages m ON m.conversation_id = c.id
            WHERE c.user_id = ?
            GROUP BY c.id
            ORDER BY c.updated_at DESC
            """,
            (user_id,),
        ).fetchall()

        conversations = [
            {
                "id": r["id"],
                "title": r["title"] or "Untitled Chat",
                "message_count": r["message_count"],
                "preview": (r["preview"] or "")[:120],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
        return JSONResponse({"conversations": conversations})
    finally:
        conn.close()


@router.get("/{conversation_id}", summary="Fetch one conversation with all messages")
async def get_conversation(
    conversation_id: str,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        conv = conn.execute(
            "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        ).fetchone()

        if not conv:
            raise HTTPException(status_code=404, detail="Conversation not found")

        msgs = conn.execute(
            "SELECT role, content, metadata, created_at FROM messages WHERE conversation_id = ? ORDER BY created_at ASC",
            (conversation_id,),
        ).fetchall()

        messages = []
        for m in msgs:
            meta = {}
            try:
                if m["metadata"]:
                    meta = json.loads(m["metadata"])
            except Exception:
                pass
            messages.append({
                "role": m["role"],
                "content": m["content"],
                "timestamp": m["created_at"],
                **meta,
            })

        return JSONResponse({
            "id": conv["id"],
            "title": conv["title"] or "Untitled Chat",
            "created_at": conv["created_at"],
            "updated_at": conv["updated_at"],
            "messages": messages,
        })
    finally:
        conn.close()


@router.post("", summary="Create or update a conversation")
async def upsert_conversation(
    body: ConversationUpsertRequest,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    try:
        user_id = _require_user(authorization)
    except Exception as e:
        logger.error(f"Failed to authenticate user for upsert: {e}")
        raise e

    conn = get_db()
    try:
        conv_id = body.id or str(uuid.uuid4())
        logger.info(f"Upserting conversation {conv_id} for user {user_id}")

        existing = conn.execute(
            "SELECT id FROM conversations WHERE id = ? AND user_id = ?",
            (conv_id, user_id),
        ).fetchone()

        if existing:
            # Update title + timestamp
            conn.execute(
                "UPDATE conversations SET title = COALESCE(?, title), updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (body.title, conv_id),
            )
            # Delete old messages and rewrite (simple upsert strategy)
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conv_id,))
        else:
            # Insert new conversation
            title = body.title
            if not title and body.messages:
                first_user = next((m for m in body.messages if m.role == "user"), None)
                title = (first_user.content[:80] + "...") if first_user and len(first_user.content) > 80 else (first_user.content if first_user else "New Chat")
            
            logger.info(f"Creating new conversation: {title}")
            conn.execute(
                "INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)",
                (conv_id, user_id, title),
            )

        # Insert all messages
        for msg in body.messages:
            meta = None
            if msg.metadata:
                meta = json.dumps(msg.metadata)
            conn.execute(
                "INSERT INTO messages (conversation_id, role, content, metadata) VALUES (?, ?, ?, ?)",
                (conv_id, msg.role, msg.content, meta),
            )

        conn.commit()
        logger.info(f"Successfully saved conversation {conv_id} with {len(body.messages)} messages")
        return JSONResponse({"id": conv_id, "ok": True})
    except Exception as e:
        logger.exception("Error in upsert_conversation:")
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        conn.close()


@router.delete("/{conversation_id}", summary="Delete a conversation")
async def delete_conversation(
    conversation_id: str,
    authorization: Optional[str] = Header(None),
) -> JSONResponse:
    user_id = _require_user(authorization)
    conn = get_db()
    try:
        result = conn.execute(
            "DELETE FROM conversations WHERE id = ? AND user_id = ?",
            (conversation_id, user_id),
        )
        conn.commit()
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return JSONResponse({"ok": True})
    finally:
        conn.close()
