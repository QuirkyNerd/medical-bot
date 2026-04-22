"""
backend/agents/image_agent.py
==============================
Agent 4 — Multi-Modal Medical Image Analysis Agent

Responsibilities:
  - Accept a medical image (bytes or base64-encoded string)
  - Detect modality from metadata or file extension hint
  - Route to the appropriate CNN classifier:
      • XrayClassifier       — Chest X-ray (14-class NIH ChestX-ray14 labels)
      • BrainMriClassifier   — Brain Tumor MRI (4-class)
      • CtScanClassifier     — CT Scan (placeholder, extensible)
  - Return a structured ImageResult including:
      • label(s) with confidence scores
      • A structured medical summary string
      • (optional) GradCAM heatmap encoded as base64 PNG

Model loading:
  - Models are loaded lazily on first use (not at import time)
  - Custom weights can be provided via environment variables:
      XRAY_MODEL_PATH, BRAIN_MRI_MODEL_PATH, CT_MODEL_PATH
  - Falls back to ImageNet-pretrained weights with a disclaimer when
    custom weights are absent (academic prototype mode)
"""

from __future__ import annotations

import base64
import io
import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn.functional as F
import torchvision.transforms as T
from PIL import Image, UnidentifiedImageError
from torchvision import models

logger = logging.getLogger("medai.image_agent")

# ---------------------------------------------------------------------------
# Modality enum
# ---------------------------------------------------------------------------

class ImageModality(str, Enum):
    XRAY     = "xray"
    BRAIN_MRI = "brain_mri"
    CT_SCAN  = "ct_scan"
    UNKNOWN  = "unknown"


# ---------------------------------------------------------------------------
# Label sets
# ---------------------------------------------------------------------------

XRAY_LABELS = [
    "Atelectasis", "Cardiomegaly", "Effusion", "Infiltration",
    "Mass", "Nodule", "Pneumonia", "Pneumothorax",
    "Consolidation", "Edema", "Emphysema", "Fibrosis",
    "Pleural Thickening", "No Finding",
]

BRAIN_MRI_LABELS = ["Glioma", "Meningioma", "No Tumor", "Pituitary"]

CT_LABELS = ["Normal", "Abnormal", "Indeterminate"]   # placeholder


# ---------------------------------------------------------------------------
# Standard pre-processing transform for all models
# ---------------------------------------------------------------------------

def _build_transform() -> T.Compose:
    return T.Compose([
        T.Resize((224, 224)),
        T.Grayscale(num_output_channels=3),   # many medical images are greyscale
        T.ToTensor(),
        T.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ])


_TRANSFORM = _build_transform()


# ---------------------------------------------------------------------------
# Base classifier
# ---------------------------------------------------------------------------

class _BaseClassifier:
    """Shared inference logic for all CNN classifiers."""

    def __init__(self, num_classes: int, labels: List[str], weights_path: Optional[str]) -> None:
        self._labels = labels
        self._device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._model = self._build_model(num_classes, weights_path)
        self._model.eval()

    def _build_model(self, num_classes: int, weights_path: Optional[str]) -> torch.nn.Module:
        # Use ResNet-50 as backbone (pretrained on ImageNet)
        model = models.resnet50(weights=models.ResNet50_Weights.IMAGENET1K_V1)
        in_features = model.fc.in_features
        model.fc = torch.nn.Linear(in_features, num_classes)
        model = model.to(self._device)

        if weights_path and os.path.exists(weights_path):
            logger.info("Loading custom weights from: %s", weights_path)
            state = torch.load(weights_path, map_location=self._device)
            # Accept both raw state_dict and wrapped {"model": state_dict}
            state_dict = state.get("model", state) if isinstance(state, dict) else state
            model.load_state_dict(state_dict, strict=False)
        else:
            logger.warning(
                "Custom weights not found (%s). Using ImageNet pretrained — "
                "predictions are illustrative (academic prototype mode).",
                weights_path,
            )

        return model

    @torch.no_grad()
    def predict(self, pil_image: Image.Image) -> List[Tuple[str, float]]:
        """
        Run inference on a PIL image.

        Returns:
            Sorted list of (label, confidence) tuples, highest first.
        """
        tensor = _TRANSFORM(pil_image).unsqueeze(0).to(self._device)
        logits = self._model(tensor)
        probs  = F.softmax(logits, dim=1).squeeze(0).cpu().tolist()

        scored = sorted(
            zip(self._labels, probs),
            key=lambda x: x[1],
            reverse=True,
        )
        return [(label, round(prob, 4)) for label, prob in scored]


# ---------------------------------------------------------------------------
# Specialised classifier subclasses
# ---------------------------------------------------------------------------

class XrayClassifier(_BaseClassifier):
    def __init__(self) -> None:
        weights = os.getenv("XRAY_MODEL_PATH")
        super().__init__(len(XRAY_LABELS), XRAY_LABELS, weights)
        logger.info("XrayClassifier ready (device=%s)", self._device)


class BrainMriClassifier(_BaseClassifier):
    def __init__(self) -> None:
        weights = os.getenv("BRAIN_MRI_MODEL_PATH")
        super().__init__(len(BRAIN_MRI_LABELS), BRAIN_MRI_LABELS, weights)
        logger.info("BrainMriClassifier ready (device=%s)", self._device)


class CtScanClassifier(_BaseClassifier):
    """
    Placeholder CT classifier.
    Provide custom weights via environment variable CT_MODEL_PATH.
    """
    def __init__(self) -> None:
        weights = os.getenv("CT_MODEL_PATH")
        super().__init__(len(CT_LABELS), CT_LABELS, weights)
        logger.info("CtScanClassifier ready (device=%s) [placeholder]", self._device)


# ---------------------------------------------------------------------------
# Lazy model registries (loaded on first use per modality)
# ---------------------------------------------------------------------------

_classifiers: Dict[ImageModality, Optional[_BaseClassifier]] = {
    ImageModality.XRAY:      None,
    ImageModality.BRAIN_MRI: None,
    ImageModality.CT_SCAN:   None,
}
_classifier_classes = {
    ImageModality.XRAY:      XrayClassifier,
    ImageModality.BRAIN_MRI: BrainMriClassifier,
    ImageModality.CT_SCAN:   CtScanClassifier,
}


def _get_classifier(modality: ImageModality) -> Optional[_BaseClassifier]:
    if modality == ImageModality.UNKNOWN:
        return None
    if _classifiers[modality] is None:
        logger.info("Lazy-loading classifier for modality: %s", modality.value)
        _classifiers[modality] = _classifier_classes[modality]()
    return _classifiers[modality]


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ImageResult:
    modality: ImageModality
    top_predictions: List[Tuple[str, float]]    # [(label, confidence), ...]
    top_label: str
    top_confidence: float
    structured_summary: str                      # Text block passed to LLM Agent
    heatmap_b64: Optional[str] = None            # GradCAM (future implementation)
    disclaimer: str = (
        "⚠️ This prediction uses a prototype model (ImageNet pretrained backbone). "
        "For clinical decisions, always use validated, FDA/CE-approved diagnostic tools."
    )


# ---------------------------------------------------------------------------
# ImageAgent class
# ---------------------------------------------------------------------------

class ImageAgent:
    """
    Processes uploaded medical images through the appropriate CNN classifier
    and returns a structured summary for downstream LLM reasoning.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(
        self,
        image_data: bytes | str,
        modality_hint: str = "auto",
    ) -> ImageResult:
        """
        Analyse a medical image.

        Args:
            image_data:    Raw image bytes OR a base64-encoded string (with or without data URI header).
            modality_hint: One of "xray", "brain_mri", "ct_scan", or "auto".

        Returns:
            ImageResult with predictions and structured medical summary.
        """
        # 1. Decode image
        pil_image = self._decode_image(image_data)

        # 2. Determine modality
        modality = self._resolve_modality(modality_hint)

        # 3. Load classifier and predict
        classifier = _get_classifier(modality)
        if classifier is None:
            return self._unknown_modality_result()

        predictions = classifier.predict(pil_image)
        top_label, top_conf = predictions[0]
        top3 = predictions[:3]

        # 4. Build structured summary for LLM
        summary = self._build_summary(modality, top_label, top_conf, top3)

        logger.info(
            "Image analysis: modality=%s | top=%s (%.1f%%)",
            modality.value, top_label, top_conf * 100,
        )

        return ImageResult(
            modality=modality,
            top_predictions=top3,
            top_label=top_label,
            top_confidence=top_conf,
            structured_summary=summary,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _decode_image(image_data: bytes | str) -> Image.Image:
        """Convert bytes or base64 string to PIL Image."""
        if isinstance(image_data, str):
            # Strip data URI header if present: "data:image/jpeg;base64,<data>"
            if "base64," in image_data:
                image_data = image_data.split("base64,", 1)[1]
            raw_bytes = base64.b64decode(image_data)
        else:
            raw_bytes = image_data

        try:
            return Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        except UnidentifiedImageError as e:
            raise ValueError(f"Cannot decode image: {e}") from e

    @staticmethod
    def _resolve_modality(hint: str) -> ImageModality:
        """Map a string hint to ImageModality enum."""
        mapping = {
            "xray": ImageModality.XRAY,
            "x-ray": ImageModality.XRAY,
            "x_ray": ImageModality.XRAY,
            "chest": ImageModality.XRAY,
            "brain_mri": ImageModality.BRAIN_MRI,
            "brain": ImageModality.BRAIN_MRI,
            "mri": ImageModality.BRAIN_MRI,
            "ct": ImageModality.CT_SCAN,
            "ct_scan": ImageModality.CT_SCAN,
            "ctscan": ImageModality.CT_SCAN,
        }
        return mapping.get(hint.lower().strip(), ImageModality.XRAY)  # default to X-ray

    @staticmethod
    def _build_summary(
        modality: ImageModality,
        top_label: str,
        top_conf: float,
        top3: List[Tuple[str, float]],
    ) -> str:
        """Generate a human-readable structured summary for downstream LLM."""
        modality_name = {
            ImageModality.XRAY: "Chest X-Ray",
            ImageModality.BRAIN_MRI: "Brain MRI",
            ImageModality.CT_SCAN: "CT Scan",
        }.get(modality, "Medical Image")

        top3_text = "\n".join(
            f"  - {label}: {conf * 100:.1f}% confidence"
            for label, conf in top3
        )

        confidence_level = (
            "HIGH" if top_conf >= 0.75 else
            "MODERATE" if top_conf >= 0.50 else
            "LOW"
        )

        return (
            f"=== CNN Image Analysis Report ===\n"
            f"Modality: {modality_name}\n"
            f"Primary Prediction: {top_label}\n"
            f"Prediction Confidence: {top_conf * 100:.1f}% ({confidence_level})\n\n"
            f"Top-3 Differential Predictions:\n{top3_text}\n\n"
            f"Note: This is a computer-aided detection output intended to support, "
            f"NOT replace, clinical evaluation by a qualified radiologist."
        )

    @staticmethod
    def _unknown_modality_result() -> ImageResult:
        return ImageResult(
            modality=ImageModality.UNKNOWN,
            top_predictions=[],
            top_label="Unknown",
            top_confidence=0.0,
            structured_summary=(
                "Image modality could not be determined. "
                "Please specify: xray, brain_mri, or ct_scan."
            ),
        )


# ---------------------------------------------------------------------------
# Module-level convenience instance
# ---------------------------------------------------------------------------

_image_agent = ImageAgent()


def analyze_image(
    image_data: bytes | str,
    modality_hint: str = "auto",
) -> ImageResult:
    """Module-level shortcut for image analysis."""
    return _image_agent.analyze(image_data, modality_hint=modality_hint)
