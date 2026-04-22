FROM python:3.10-slim

# Prevent Python from buffering logs
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ✅ 1. Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    gcc \
    curl \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# ✅ 2. Copy requirements first (for caching)
COPY requirements.txt .

# ✅ 3. Install Python dependencies
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ✅ 4. Pre-download embedding model (optional but good)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"

# ✅ 5. Copy full backend code
COPY . .

# ✅ 6. Start FastAPI with dynamic port (RENDER FIX)
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port $PORT"]