"""
backend/api/export_router.py
==============================
PDF export endpoint — generates a human-readable health report using reportlab.

Endpoint:
  GET /api/export-report   → returns a PDF file download
"""

from __future__ import annotations

import io
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Header, HTTPException
from fastapi.responses import StreamingResponse

from database import get_db
from api.auth_router import decode_jwt

logger = logging.getLogger("medai.export")
router = APIRouter()


def _require_user(authorization: Optional[str]) -> tuple[int, str]:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization[7:].strip()
    payload = decode_jwt(token)
    return int(payload["sub"]), payload.get("email", "")


@router.get("", summary="Export health report as PDF")
async def export_report(authorization: Optional[str] = Header(None)) -> StreamingResponse:
    user_id, email = _require_user(authorization)

    conn = get_db()
    try:
        # Fetch user info
        user_row = conn.execute(
            "SELECT name, email FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        user_name = user_row["name"] if user_row else email

        # Fetch schedules
        schedules = conn.execute(
            "SELECT medication_name, dosage, time, frequency, status FROM medication_schedules WHERE user_id = ? ORDER BY time ASC",
            (user_id,),
        ).fetchall()

        # Fetch recent conversations count
        conv_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM conversations WHERE user_id = ?", (user_id,)
        ).fetchone()["cnt"]

    finally:
        conn.close()

    # ── Build PDF ─────────────────────────────────────────────────────────────
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import cm
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
    except ImportError:
        raise HTTPException(
            status_code=500,
            detail="reportlab is not installed. Run: pip install reportlab"
        )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title", parent=styles["Title"], fontSize=20, spaceAfter=6, textColor=colors.HexColor("#1a56db")
    )
    h2_style = ParagraphStyle(
        "H2", parent=styles["Heading2"], fontSize=13, spaceBefore=14, spaceAfter=4,
        textColor=colors.HexColor("#1e3a5f")
    )
    body_style = styles["Normal"]

    today = datetime.now().strftime("%B %d, %Y")
    story = []

    # Header
    story.append(Paragraph("🏥 MedOS Health Report", title_style))
    story.append(Paragraph(f"<b>Patient:</b> {user_name} &nbsp;&nbsp; <b>Date:</b> {today}", body_style))
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#1a56db")))
    story.append(Spacer(1, 0.4 * cm))

    # Summary
    story.append(Paragraph("Summary", h2_style))
    story.append(Paragraph(f"Total medication schedule entries: <b>{len(schedules)}</b>", body_style))
    story.append(Paragraph(f"Total chat conversations: <b>{conv_count}</b>", body_style))
    story.append(Spacer(1, 0.4 * cm))

    # Medication Schedule Table
    story.append(Paragraph("Medication Schedule", h2_style))

    if schedules:
        table_data = [["Medication", "Dosage", "Time", "Frequency", "Status"]]
        for s in schedules:
            status_text = "✅ Done" if s["status"] == "done" else "⏳ Pending"
            table_data.append([
                s["medication_name"],
                s["dosage"],
                s["time"],
                s["frequency"] or "daily",
                status_text,
            ])

        tbl = Table(table_data, colWidths=[4.5 * cm, 3 * cm, 2.5 * cm, 3 * cm, 3 * cm])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a56db")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f0f4ff")]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#c7d2fe")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(tbl)
    else:
        story.append(Paragraph("No medication schedules recorded.", body_style))

    story.append(Spacer(1, 0.6 * cm))

    # Footer
    story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
    story.append(Spacer(1, 0.2 * cm))
    footer_style = ParagraphStyle("footer", parent=body_style, fontSize=8, textColor=colors.grey)
    story.append(Paragraph(
        f"Generated by MedOS Medical AI System on {today}. This report is for informational purposes only and does not constitute medical advice.",
        footer_style,
    ))

    try:
        doc.build(story)
        buffer.seek(0)

        filename = f"medos-report-{datetime.now().strftime('%Y%m%d')}.pdf"
        logger.info(f"Successfully generated PDF report for {email}")
        return StreamingResponse(
            buffer,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        logger.exception("Failed to build PDF:")
        raise HTTPException(status_code=500, detail="Failed to build PDF")
