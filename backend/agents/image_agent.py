from __future__ import annotations

import base64
import io
import logging
import os
from dataclasses import dataclass
from typing import Optional, List

import requests
from PIL import Image

logger = logging.getLogger("medai.image_agent")

HF_API_KEY = os.getenv("HF_API_KEY")

if not HF_API_KEY:
    raise ValueError("HF_API_KEY not set")

MODEL_URL = "https://api-inference.huggingface.co/models/sentence-transformers/clip-ViT-B-32"

HEADERS = {
    "Authorization": f"Bearer {HF_API_KEY}"
}


# -------------------------------------------------------------------
# DATA MODEL
# -------------------------------------------------------------------

@dataclass
class ImageResult:
    modality: str
    embedding: List[float]
    structured_summary: str
    confidence: float
    disclaimer: str = "⚠️ AI-generated result. Not a medical diagnosis."


# -------------------------------------------------------------------
# AGENT
# -------------------------------------------------------------------

class ImageAgent:

    def analyze(self, image_data: bytes | str, modality_hint: str = "auto") -> ImageResult:
        image_bytes = self._prepare_image(image_data)

        try:
            response = requests.post(
                MODEL_URL,
                headers=HEADERS,
                data=image_bytes,
                timeout=30
            )

            if response.status_code != 200:
                raise Exception(response.text)

            data = response.json()

            # CLIP returns vector
            if isinstance(data, list):
                embedding = data
            else:
                embedding = data[0]

            summary = self._build_summary(modality_hint, len(embedding))

            return ImageResult(
                modality=modality_hint,
                embedding=embedding,
                structured_summary=summary,
                confidence=0.9
            )

        except Exception as e:
            logger.error("HF Image API failed: %s", e)
            return ImageResult(
                modality=modality_hint,
                embedding=[],
                structured_summary="Image processing failed",
                confidence=0.0
            )

    # ------------------------------------------------------------------

    def _prepare_image(self, image_data: bytes | str) -> bytes:
        if isinstance(image_data, str):
            if "base64," in image_data:
                image_data = image_data.split("base64,", 1)[1]
            image_data = base64.b64decode(image_data)

        image = Image.open(io.BytesIO(image_data)).convert("RGB")

        buffer = io.BytesIO()
        image.save(buffer, format="PNG")
        return buffer.getvalue()

    # ------------------------------------------------------------------

    def _build_summary(self, modality: str, dim: int) -> str:
        return (
            f"=== Image Embedding Analysis ===\n"
            f"Modality: {modality}\n"
            f"Embedding dimension: {dim}\n\n"
            f"This embedding represents semantic image features.\n"
            f"Use this with RAG + Groq for medical reasoning."
        )


# -------------------------------------------------------------------
# GLOBAL INSTANCE
# -------------------------------------------------------------------

_image_agent = ImageAgent()


def analyze_image(image_data: bytes | str, modality_hint: str = "auto") -> ImageResult:
    return _image_agent.analyze(image_data, modality_hint)