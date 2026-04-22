"""
backend/api/auth_router.py
===========================
Production-grade JWT authentication using SQLite and bcrypt.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
import datetime
import random
import smtplib
from email.message import EmailMessage
from typing import Any, Dict, Optional
from dotenv import load_dotenv

load_dotenv()

import bcrypt
import jwt
from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from database import get_db

logger = logging.getLogger("medai.auth")

router = APIRouter()

JWT_SECRET = os.getenv("JWT_SECRET", "super_secret_dev_key_only_change_in_prod")
JWT_ALGORITHM = "HS256"

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)
    displayName: Optional[str] = None


class LoginRequest(BaseModel):
    email: str
    password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class VerifyEmailRequest(BaseModel):
    code: str

class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    newPassword: str = Field(..., min_length=6)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def create_jwt(user_id: int, email: str) -> str:
    """Generate a JWT valid for 24 hours."""
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

def send_reset_email(to_email: str, otp: str) -> bool:
    EMAIL_USER = os.getenv("EMAIL_USER")
    EMAIL_PASS = os.getenv("EMAIL_PASS")
    
    print("ENV EMAIL:", EMAIL_USER)
    
    if not EMAIL_USER or not EMAIL_PASS:
        print("❌ EMAIL ERROR: Email credentials not configured")
        return False
        
    print("EMAIL_USER:", EMAIL_USER)
    print("Sending email to:", to_email)
    
    msg = EmailMessage()
    msg["Subject"] = "Password Reset Code"
    msg["From"] = EMAIL_USER
    msg["To"] = to_email
    msg.set_content(f"Your password reset code is: {otp}\nThis code expires in 10 minutes.")
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
        server.quit()
        print("✅ EMAIL SENT SUCCESSFULLY")
        return True
    except Exception as e:
        print("❌ EMAIL ERROR:", str(e))
        raise e


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", summary="Create new user account")
async def register(body: RegisterRequest) -> JSONResponse:
    conn = get_db()
    cursor = conn.cursor()
    try:
        # Check if user exists
        cursor.execute("SELECT id FROM users WHERE email = ?", (body.email,))
        if cursor.fetchone():
            raise HTTPException(status_code=409, detail="Email already registered")

        # Hash password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(body.password.encode('utf-8'), salt).decode('utf-8')
        name = body.displayName or body.email.split("@")[0]

        # Insert user
        cursor.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, body.email, hashed)
        )
        conn.commit()
        user_id = cursor.lastrowid

        user_out = {
            "id": str(user_id),
            "email": body.email,
            "displayName": name,
            "emailVerified": True,
            "isAdmin": False
        }
        
        token = create_jwt(user_id, body.email)
        logger.info(f"Registered user: {body.email}")
        return JSONResponse({"message": "User registered successfully", "token": token, "user": user_out})
    finally:
        conn.close()


@router.post("/login", summary="Authenticate and receive JWT")
async def login(body: LoginRequest) -> JSONResponse:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, email, password_hash FROM users WHERE email = ?", (body.email,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=401, detail="Invalid email or password. Please try again.")

        if not bcrypt.checkpw(body.password.encode('utf-8'), row['password_hash'].encode('utf-8')):
            raise HTTPException(status_code=401, detail="Invalid email or password. Please try again.")

        user_out = {
            "id": str(row['id']),
            "email": row['email'],
            "displayName": row['name'],
            "emailVerified": True,
            "isAdmin": False
        }

        token = create_jwt(row['id'], row['email'])
        logger.info(f"Login success: {body.email}")
        return JSONResponse({"token": token, "user": user_out})
    finally:
        conn.close()


@router.get("/me", summary="Return current authenticated user")
async def me(authorization: Optional[str] = Header(None)) -> JSONResponse:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[7:].strip()
    payload = decode_jwt(token)
    email = payload.get("email")

    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id, name, email FROM users WHERE email = ?", (email,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="User not found")

        user_out = {
            "id": str(row['id']),
            "email": row['email'],
            "displayName": row['name'],
            "emailVerified": True,
            "isAdmin": False
        }
        return JSONResponse({"user": user_out})
    finally:
        conn.close()


@router.post("/logout", summary="Invalidate token (client-side only for stateless JWT)")
async def logout(authorization: Optional[str] = Header(None)) -> JSONResponse:
    # A fully stateless JWT system handles logout client-side by destroying the token.
    return JSONResponse({"ok": True, "message": "Logged out successfully"})


@router.post("/forgot-password", summary="Initiate password reset")
async def forgot_password(body: ForgotPasswordRequest) -> JSONResponse:
    print("🔥 Forgot password triggered")
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT id FROM users WHERE email = ?", (body.email,))
        if not cursor.fetchone():
            return JSONResponse({"ok": True, "message": "If that email exists, a reset code has been sent."})
            
        otp = str(random.randint(100000, 999999))
        
        cursor.execute('''
            INSERT INTO password_reset_tokens (email, otp_code, expires_at, is_used) 
            VALUES (?, ?, datetime('now', '+10 minutes'), 0)
        ''', (body.email, otp))
        conn.commit()
        
        send_reset_email(body.email, otp)
        
        return JSONResponse({
            "ok": True, 
            "message": "If that email exists, a reset code has been sent."
        })
    finally:
        conn.close()
        
        
@router.post("/verify-email", summary="Verify OTP")
async def verify_email(body: VerifyEmailRequest) -> JSONResponse:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT email FROM password_reset_tokens WHERE otp_code = ? AND is_used = 0 AND expires_at > datetime('now')", (body.code,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired code")
            
        return JSONResponse({"ok": True})
    finally:
        conn.close()


@router.post("/reset-password", summary="Reset password using OTP")
async def reset_password(body: ResetPasswordRequest) -> JSONResponse:
    conn = get_db()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            SELECT id FROM password_reset_tokens 
            WHERE email = ? AND otp_code = ? AND is_used = 0 AND expires_at > datetime('now')
        ''', (body.email, body.code))
        row = cursor.fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="Invalid or expired reset code")
            
        token_id = row['id']
            
        # Update user password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(body.newPassword.encode('utf-8'), salt).decode('utf-8')
        cursor.execute("UPDATE users SET password_hash = ? WHERE email = ?", (hashed, body.email))
        
        # Mark OTP as used
        cursor.execute("UPDATE password_reset_tokens SET is_used = 1 WHERE id = ?", (token_id,))
        conn.commit()
        
        return JSONResponse({"ok": True, "message": "Password reset successfully"})
    finally:
        conn.close()


@router.post("/resend-verification", summary="Resend verification (no-op in demo)")
async def resend_verification() -> JSONResponse:
    return JSONResponse({"ok": True})
