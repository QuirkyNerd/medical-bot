"""
Image Agent (Render-safe, No Torch, Groq-compatible)

- No heavy ML dependencies
- Keeps structured pipeline design
- Provides detailed image metadata + heuristic analysis
- Ready for LLM (Groq) downstream reasoning
"""

from __future__ import annotations

import base64
import io
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

from PIL import Image, ImageStat

logger = logging.getLogger("medai.image_agent")


# -------------------------------------------------------------------
# DATA MODEL
# -------------------------------------------------------------------

@dataclass
class ImageResult:
    modality: str
    width: int
    height: int
    aspect_ratio: float
    color_mode: str
    brightness: float
    contrast: float
    top_label: str
    top_confidence: float
    structured_summary: str
    metadata: Dict[str, Any]
    disclaimer: str = (
        "⚠️ No CNN model used. This is heuristic + metadata analysis only."
    )


# -------------------------------------------------------------------
# IMAGE AGENT
# -------------------------------------------------------------------

class ImageAgent:
    """
    Lightweight Image Analysis Agent

    Replaces heavy CNN pipeline with:
    - Image decoding
    - Statistical analysis
    - Structured summary for LLM reasoning
    """

    # ---------------------------------------------------------------
    # MAIN ENTRY
    # ---------------------------------------------------------------

    def analyze(self, image_data: bytes | str, modality_hint: str = "auto") -> ImageResult:
        logger.info("Starting image analysis")

        image = self._decode_image(image_data)

        width, height = image.size
        aspect_ratio = round(width / height, 2)
        color_mode = image.mode

        brightness, contrast = self._analyze_image_stats(image)

        label, confidence = self._infer_basic_pattern(brightness, contrast)

        summary = self._build_summary(
            modality_hint,
            width,
            height,
            color_mode,
            brightness,
            contrast,
            label
        )

        metadata = {
            "resolution": f"{width}x{height}",
            "aspect_ratio": aspect_ratio,
            "color_mode": color_mode,
            "brightness": brightness,
            "contrast": contrast,
        }

        logger.info("Image analysis completed")

        return ImageResult(
            modality=modality_hint,
            width=width,
            height=height,
            aspect_ratio=aspect_ratio,
            color_mode=color_mode,
            brightness=brightness,
            contrast=contrast,
            top_label=label,
            top_confidence=confidence,
            structured_summary=summary,
            metadata=metadata,
        )

    # ---------------------------------------------------------------
    # IMAGE DECODING
    # ---------------------------------------------------------------

    def _decode_image(self, image_data: bytes | str) -> Image.Image:
        if isinstance(image_data, str):
            if "base64," in image_data:
                image_data = image_data.split("base64,", 1)[1]
            image_data = base64.b64decode(image_data)

        return Image.open(io.BytesIO(image_data)).convert("RGB")

    # ---------------------------------------------------------------
    # BASIC IMAGE STATISTICS
    # ---------------------------------------------------------------

    def _analyze_image_stats(self, image: Image.Image) -> tuple[float, float]:
        stat = ImageStat.Stat(image)

        # Average brightness (0–255)
        brightness = sum(stat.mean) / len(stat.mean)

        # Contrast approximation
        contrast = sum(stat.stddev) / len(stat.stddev)

        return round(brightness, 2), round(contrast, 2)

    # ---------------------------------------------------------------
    # SIMPLE HEURISTIC LABELING
    # ---------------------------------------------------------------

    def _infer_basic_pattern(self, brightness: float, contrast: float) -> tuple[str, float]:
        """
        Very rough heuristic just to keep pipeline alive
        """

        if brightness < 60:
            return "Very Dark Image", 0.4
        elif brightness > 190:
            return "Very Bright Image", 0.4
        elif contrast < 20:
            return "Low Contrast Image", 0.5
        elif contrast > 80:
            return "High Contrast Image", 0.5

        return "Normal Image Pattern", 0.3

    # ---------------------------------------------------------------
    # SUMMARY BUILDER
    # ---------------------------------------------------------------

    def _build_summary(
        self,
        modality: str,
        width: int,
        height: int,
        color_mode: str,
        brightness: float,
        contrast: float,
        label: str
    ) -> str:

        return (
            f"=== Image Analysis Report ===\n"
            f"Modality: {modality}\n"
            f"Resolution: {width} x {height}\n"
            f"Color Mode: {color_mode}\n\n"
            f"Brightness Level: {brightness}\n"
            f"Contrast Level: {contrast}\n\n"
            f"Inferred Pattern: {label}\n\n"
            f"Note:\n"
            f"- No deep learning model was used.\n"
            f"- This data is intended for downstream AI (Groq) reasoning.\n"
        )


# -------------------------------------------------------------------
# GLOBAL INSTANCE
# -------------------------------------------------------------------

_image_agent = ImageAgent()


def analyze_image(image_data: bytes | str, modality_hint: str = "auto") -> ImageResult:
    return _image_agent.analyze(image_data, modality_hint)