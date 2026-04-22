import sqlite3
import requests
import json
import uuid
import time
import os

DB_PATH = r"d:\Desktop\newone\ai-medical-chatbot\backend\database.db"

# 1. Direct DB check for existing user or create one
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("SELECT id, email FROM users LIMIT 1")
user = cursor.fetchone()
if not user:
    cursor.execute("INSERT INTO users (name, email, password_hash) VALUES ('Test', 'test@example.com', 'hashed')")
    conn.commit()
    user_id = cursor.lastrowid
    email = 'test@example.com'
else:
    user_id = user['id']
    email = user['email']

print(f"Testing with User ID: {user_id}, Email: {email}")

try:
    cursor.execute("INSERT INTO conversations (id, user_id, title) VALUES (?, ?, ?)", ("test-conv", user_id, "Test Chat"))
    conn.commit()
    print("Conversation table insert: SUCCESS")
except Exception as e:
    print("Conversation table insert: FAILED", e)

cursor.execute("SELECT * FROM conversations")
print("Conversations rows:", [dict(r) for r in cursor.fetchall()])

try:
    cursor.execute("INSERT INTO medication_schedules (id, user_id, medication_name, dosage, time, frequency) VALUES (?, ?, ?, ?, ?, ?)", ("test-sched", user_id, "Test Med", "100mg", "08:00", "daily"))
    conn.commit()
    print("Medication Schedule insert: SUCCESS")
except Exception as e:
    print("Medication Schedule insert: FAILED", e)

cursor.execute("SELECT * FROM medication_schedules")
print("Schedules rows:", [dict(r) for r in cursor.fetchall()])

conn.close()
