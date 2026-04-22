FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# ✅ 1. Install system deps (cached forever)
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

# ✅ 2. COPY ONLY requirements FIRST (THIS IS KEY 🔥)
COPY requirements.txt .

# ✅ 3. Install deps (cached unless requirements.txt changes)
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ✅ 4. Pre-download the sentence transformer model (layer caching 🔥)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"

# ✅ 5. THEN copy code (this won't break cache)
COPY . .

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]