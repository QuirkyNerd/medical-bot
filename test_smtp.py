import os
import sqlite3
import datetime
import random
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv
import bcrypt

load_dotenv(r"d:\Desktop\newone\ai-medical-chatbot\backend\.env")

DB_PATH = r"d:\Desktop\newone\ai-medical-chatbot\backend\database.db"

def test_db_setup():
    print("Setting up DB tables and test user...")
    conn = sqlite3.connect(DB_PATH)
    try:
        # Just in case the server isn't running and hasn't created the table
        conn.execute('''
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL,
                otp_code TEXT NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                is_used BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        email = os.getenv("EMAIL_USER", "test@example.com")
        
        # Check if user exists
        user = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if not user:
            salt = bcrypt.gensalt()
            hashed = bcrypt.hashpw(b"oldpassword", salt).decode('utf-8')
            conn.execute("INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)", ("Test User", email, hashed))
        
        conn.commit()
        return email
    finally:
        conn.close()

def simulate_forgot_password(email):
    print(f"\n--- Simulating forgot password for {email} ---")
    conn = sqlite3.connect(DB_PATH)
    try:
        otp = str(random.randint(100000, 999999))
        expires_at = datetime.datetime.utcnow() + datetime.timedelta(minutes=10)
        
        conn.execute('''
            INSERT INTO password_reset_tokens (email, otp_code, expires_at, is_used) 
            VALUES (?, ?, ?, 0)
        ''', (email, otp, expires_at))
        conn.commit()
        
        # Attempt to send email
        email_user = os.getenv("EMAIL_USER")
        email_pass = os.getenv("EMAIL_PASS")
        print(f"SMTP Configured: User={email_user is not None}, Pass={email_pass is not None}")
        
        if email_user and email_pass:
            try:
                msg = EmailMessage()
                msg.set_content(f"Your password reset code is: {otp}\nThis code expires in 10 minutes.")
                msg['Subject'] = "Password Reset Code"
                msg['From'] = email_user
                msg['To'] = email
                
                print(f"Sending SMTP email from {email_user} to {email}...")
                with smtplib.SMTP("smtp.gmail.com", 587) as server:
                    server.starttls()
                    server.login(email_user, email_pass)
                    server.send_message(msg)
                print("✅ Email sent successfully via SMTP!")
                return otp
            except Exception as e:
                print(f"❌ Failed to send email: {e}")
                return otp # return anyway for testing
        else:
            print("❌ No SMTP credentials found.")
            return otp
    finally:
        conn.close()

def simulate_reset_password(email, otp):
    print(f"\n--- Simulating reset password for {email} with OTP {otp} ---")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        # Validate OTP
        row = conn.execute('''
            SELECT id FROM password_reset_tokens 
            WHERE email = ? AND otp_code = ? AND is_used = 0 AND expires_at > ?
        ''', (email, otp, datetime.datetime.utcnow())).fetchone()
        
        if not row:
            print("❌ Validation Failed: Invalid or expired reset code")
            return
            
        token_id = row['id']
        
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(b"newpassword123", salt).decode('utf-8')
        conn.execute("UPDATE users SET password_hash = ? WHERE email = ?", (hashed, email))
        conn.execute("UPDATE password_reset_tokens SET is_used = 1 WHERE id = ?", (token_id,))
        conn.commit()
        
        print("✅ Password reset successfully. Token marked as used.")
        
        # Test reuse prevention
        print("\n--- Testing Reuse Prevention ---")
        row = conn.execute('''
            SELECT id FROM password_reset_tokens 
            WHERE email = ? AND otp_code = ? AND is_used = 0 AND expires_at > ?
        ''', (email, otp, datetime.datetime.utcnow())).fetchone()
        if not row:
            print("✅ OTP cannot be reused. Success.")
        else:
            print("❌ OTP reuse prevention failed!")
            
    finally:
        conn.close()

if __name__ == "__main__":
    email = test_db_setup()
    otp = simulate_forgot_password(email)
    simulate_reset_password(email, otp)
    
    print("\n--- Testing Invalid OTP ---")
    simulate_reset_password(email, "000000")
