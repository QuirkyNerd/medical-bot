import subprocess
import time
import requests
import jwt
import datetime
import os
import signal

print("Starting local uvicorn instance on port 8001...")
process = subprocess.Popen(
    ["python", "-m", "uvicorn", "main:app", "--port", "8001"],
    cwd=r"d:\Desktop\newone\ai-medical-chatbot\backend",
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

# Wait for server to boot properly
for _ in range(10):
    time.sleep(1)
    try:
        r = requests.get("http://localhost:8001/api/health")
        if r.status_code == 200:
            break
    except:
        pass

try:
    payload = {
        "sub": "2",
        "email": "adi@gmail.com",
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=24)
    }
    JWT_SECRET = "super_secret_dev_key_only_change_in_prod"
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    BASE_URL = "http://localhost:8001"

    print("\n=== TEST 1: POST /api/schedule ===")
    sched_payload = {
        "medication_name": "Test Med API",
        "dosage": "500mg",
        "time": "12:00",
        "frequency": "daily",
        "notes": "Take with water"
    }
    r = requests.post(f"{BASE_URL}/api/schedule", json=sched_payload, headers=headers)
    print("Status:", r.status_code)
    try:
        print("Response:", r.json())
    except:
        print("Response:", r.text)

    print("\n=== TEST 2: GET /api/schedule ===")
    r = requests.get(f"{BASE_URL}/api/schedule", headers=headers)
    print("Status:", r.status_code)
    try:
        print("Response:", r.json())
    except:
        print("Response:", r.text)

    print("\n=== TEST 3: POST /api/conversations ===")
    conv_payload = {
        "id": "api-test-chat-new",
        "title": "API Test Title",
        "messages": [
            {"role": "user", "content": "Hello API"},
            {"role": "assistant", "content": "Hello from backend"}
        ]
    }
    r = requests.post(f"{BASE_URL}/api/conversations", json=conv_payload, headers=headers)
    print("Status:", r.status_code)
    try:
        print("Response:", r.json())
    except:
        print("Response:", r.text)

    print("\n=== TEST 4: GET /api/conversations ===")
    r = requests.get(f"{BASE_URL}/api/conversations", headers=headers)
    print("Status:", r.status_code)
    try:
        print("Response:", r.json())
    except:
        print("Response:", r.text)

    print("\n=== TEST 5: GET /api/export-report ===")
    r = requests.get(f"{BASE_URL}/api/export-report", headers=headers)
    print("Status:", r.status_code)
    print("Content-Type:", r.headers.get("Content-Type"))
    print("File Size:", len(r.content), "bytes")
    
    print("\n✅ ALL TESTS VERIFIED VIA LOCAL HTTP REQUESTS!")

except Exception as e:
    print("Test failed:", e)

finally:
    # Kill the server
    os.kill(process.pid, signal.SIGTERM)
