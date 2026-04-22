"""
backend/api/auth_router.py
===========================
Production-grade JWT authentication using PostgreSQL and bcrypt.
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
from sqlalchemy import text

from database import engine

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
    
    if not EMAIL_USER or not EMAIL_PASS:
        logger.error("Email credentials not configured")
        return False
        
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
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/register", summary="Create new user account")
async def register(body: RegisterRequest) -> JSONResponse:
    logger.info(f"POST /register | email: {body.email}")
    
    # Use engine.begin() for automatic transaction management (commit on success, rollback on error)
    with engine.begin() as conn:
        try:
            # 1. Check if user exists
            existing = conn.execute(
                text("SELECT id FROM users WHERE email = :email"),
                {"email": body.email}
            ).fetchone()
            
            if existing:
                logger.warning(f"Registration failed: Email {body.email} already exists")
                return JSONResponse(
                    status_code=409,
                    content={"error": "Email already registered"}
                )

            # 2. Hash password
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(body.password.encode('utf-8'), salt).decode('utf-8')
            name = body.displayName or body.email.split("@")[0]

            # 3. Insert user using RETURNING id
            logger.info(f"Inserting new user: {body.email}")
            result = conn.execute(
                text("INSERT INTO users (name, email, password_hash) VALUES (:name, :email, :password_hash) RETURNING id"),
                {"name": name, "email": body.email, "password_hash": hashed}
            )
            
            # Fetch the generated ID
            row = result.fetchone()
            if not row:
                raise Exception("Failed to retrieve new user ID after insert")
            
            user_id = row[0]
            logger.info(f"User created successfully with ID: {user_id}")

            user_out = {
                "id": str(user_id),
                "email": body.email,
                "displayName": name,
                "emailVerified": True,
                "isAdmin": False
            }
            
            token = create_jwt(user_id, body.email)
            return JSONResponse({
                "message": "User registered successfully", 
                "token": token, 
                "user": user_out
            })
            
        except Exception as e:
            logger.exception(f"Unexpected error during registration for {body.email}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Internal server error: {str(e)}"}
            )


@router.post("/login", summary="Authenticate and receive JWT")
async def login(body: LoginRequest) -> JSONResponse:
    logger.info(f"POST /login | email: {body.email}")
    with engine.connect() as conn:
        try:
            row = conn.execute(
                text("SELECT id, name, email, password_hash FROM users WHERE email = :email"),
                {"email": body.email}
            ).fetchone()

            if not row:
                logger.warning(f"Login failed: User {body.email} not found")
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid email or password."}
                )

            # row is a tuple-like object: (id, name, email, password_hash)
            # row[3] is password_hash
            if not bcrypt.checkpw(body.password.encode('utf-8'), row[3].encode('utf-8')):
                logger.warning(f"Login failed: Incorrect password for {body.email}")
                return JSONResponse(
                    status_code=401,
                    content={"error": "Invalid email or password."}
                )

            user_out = {
                "id": str(row[0]),
                "email": row[2],
                "displayName": row[1],
                "emailVerified": True,
                "isAdmin": False
            }

            token = create_jwt(row[0], row[2])
            logger.info(f"Login successful: {body.email}")
            return JSONResponse({"token": token, "user": user_out})
        except Exception as e:
            logger.exception(f"Unexpected error during login for {body.email}")
            return JSONResponse(
                status_code=500,
                content={"error": f"Internal server error: {str(e)}"}
            )


@router.get("/me", summary="Return current authenticated user")
async def me(authorization: Optional[str] = Header(None)) -> JSONResponse:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")

    token = authorization[7:].strip()
    try:
        payload = decode_jwt(token)
    except Exception as e:
        return JSONResponse(status_code=401, content={"error": str(e)})
        
    email = payload.get("email")

    with engine.connect() as conn:
        try:
            row = conn.execute(
                text("SELECT id, name, email FROM users WHERE email = :email"),
                {"email": email}
            ).fetchone()
            
            if not row:
                return JSONResponse(status_code=401, content={"error": "User not found"})

            user_out = {
                "id": str(row[0]),
                "email": row[2],
                "displayName": row[1],
                "emailVerified": True,
                "isAdmin": False
            }
            return JSONResponse({"user": user_out})
        except Exception as e:
            return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/logout", summary="Invalidate token")
async def logout() -> JSONResponse:
    return JSONResponse({"ok": True, "message": "Logged out successfully"})


@router.post("/forgot-password", summary="Initiate password reset")
async def forgot_password(body: ForgotPasswordRequest) -> JSONResponse:
    with engine.connect() as conn:
        user = conn.execute(
            text("SELECT id FROM users WHERE email = :email"),
            {"email": body.email}
        ).fetchone()
        
        if not user:
            return JSONResponse({"ok": True, "message": "If that email exists, a reset code has been sent."})
            
        otp = str(random.randint(100000, 999999))
        
        conn.execute(text('''
            INSERT INTO password_reset_tokens (email, otp_code, expires_at, is_used) 
            VALUES (:email, :otp, NOW() + INTERVAL '10 minutes', FALSE)
        '''), {"email": body.email, "otp": otp})
        conn.commit()
        
        send_reset_email(body.email, otp)
        
        return JSONResponse({"ok": True, "message": "If that email exists, a reset code has been sent."})
        
        
@router.post("/verify-email", summary="Verify OTP")
async def verify_email(body: VerifyEmailRequest) -> JSONResponse:
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT email FROM password_reset_tokens 
            WHERE otp_code = :code AND is_used = FALSE AND expires_at > NOW()
        """), {"code": body.code}).fetchone()
        
        if not row:
            raise HTTPException(status_code=400, detail="Invalid or expired code")
            
        return JSONResponse({"ok": True})


@router.post("/reset-password", summary="Reset password using OTP")
async def reset_password(body: ResetPasswordRequest) -> JSONResponse:
    with engine.connect() as conn:
        row = conn.execute(text('''
            SELECT id FROM password_reset_tokens 
            WHERE email = :email AND otp_code = :code AND is_used = FALSE AND expires_at > NOW()
        '''), {"email": body.email, "code": body.code}).fetchone()
        
        if not row:
            raise HTTPException(status_code=401, detail="Invalid or expired reset code")
            
        token_id = row[0]
            
        # Update user password
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(body.newPassword.encode('utf-8'), salt).decode('utf-8')
        conn.execute(
            text("UPDATE users SET password_hash = :hash WHERE email = :email"),
            {"hash": hashed, "email": body.email}
        )
        
        # Mark OTP as used
        conn.execute(
            text("UPDATE password_reset_tokens SET is_used = TRUE WHERE id = :id"),
            {"id": token_id}
        )
        conn.commit()
        
        return JSONResponse({"ok": True, "message": "Password reset successfully"})


@router.post("/resend-verification", summary="Resend verification")
async def resend_verification() -> JSONResponse:
    return JSONResponse({"ok": True})
