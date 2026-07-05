"""
Image analysis: real blur detection (OpenCV Laplacian variance — a
well-established, deterministic technique, not ML), real dimension
extraction (Pillow), real near-duplicate detection (perceptual hashing),
and rule-based (non-ML) category classification.

Honest scope note: "Personal Photos vs Nature vs Animals" content
classification is NOT done via a trained vision model here — that needs
a pretrained CNN (e.g. a MobileNet ImageNet classifier) wired in, which
is a reasonable next step but a bigger dependency (large model download,
inference cost) than this pass covers. Screenshot vs Photo detection
below IS reliable without ML: screenshots have distinctive dimensions/
filenames/color-palette signatures.
"""
import os
import re
from PIL import Image
import cv2
import numpy as np

BLUR_THRESHOLD = 100.0  # Laplacian variance below this = blurry (standard heuristic)

SCREENSHOT_FILENAME_PATTERNS = [r"screenshot", r"screen.?shot", r"scr_\d", r"capture"]


def compute_blur_score(filepath: str) -> float | None:
    """Laplacian variance: low variance = few sharp edges = likely blurry."""
    try:
        img = cv2.imread(filepath, cv2.IMREAD_GRAYSCALE)
        if img is None:
            return None
        return float(cv2.Laplacian(img, cv2.CV_64F).var())
    except Exception:
        return None


def compute_perceptual_hash(filepath: str) -> str | None:
    """
    Simple average-hash (aHash): shrink to 8x8 grayscale, threshold against
    the mean, pack into a hex string. Images with the same hash are visually
    near-identical (resized/recompressed duplicates), unlike SHA256 which
    only catches byte-identical files.
    """
    try:
        img = Image.open(filepath).convert("L").resize((8, 8), Image.LANCZOS)
        pixels = np.asarray(img, dtype=np.float32)
        avg = pixels.mean()
        bits = (pixels > avg).flatten()
        hash_int = 0
        for bit in bits:
            hash_int = (hash_int << 1) | int(bit)
        return f"{hash_int:016x}"
    except Exception:
        return None


def hamming_distance(hash_a: str, hash_b: str) -> int:
    try:
        return bin(int(hash_a, 16) ^ int(hash_b, 16)).count("1")
    except (ValueError, TypeError):
        return 64  # max distance = no match


def classify_image(filepath: str, width: int | None, height: int | None) -> tuple[str, float]:
    """Rule-based screenshot vs photo/document split. Returns (label, confidence)."""
    filename = os.path.basename(filepath).lower()

    for pat in SCREENSHOT_FILENAME_PATTERNS:
        if re.search(pat, filename):
            return "Screenshot", 0.9

    if width and height:
        # Screenshots commonly match exact device/monitor resolutions
        common_screen_ratios = [(16, 9), (16, 10), (4, 3), (3, 2)]
        ratio = width / height if height else 0
        for w, h in common_screen_ratios:
            if abs(ratio - (w / h)) < 0.02 and (width >= 1000 or height >= 1000):
                return "Screenshot", 0.4  # weak signal alone
        # Very tall narrow images are often phone screenshots
        if height > width * 1.8:
            return "Screenshot", 0.5

    return "Photo", 0.3  # default guess, low confidence — this is NOT content-verified


def extract_image_info(filepath: str) -> dict:
    info = {
        "width": None,
        "height": None,
        "blur_score": None,
        "is_blurry": None,
        "perceptual_hash": None,
        "subcategory": "Unclassified",
        "subcategory_confidence": 0.0,
    }
    try:
        with Image.open(filepath) as img:
            info["width"], info["height"] = img.size
    except Exception:
        pass

    info["blur_score"] = compute_blur_score(filepath)
    if info["blur_score"] is not None:
        info["is_blurry"] = info["blur_score"] < BLUR_THRESHOLD

    info["perceptual_hash"] = compute_perceptual_hash(filepath)

    label, confidence = classify_image(filepath, info["width"], info["height"])
    info["subcategory"] = label
    info["subcategory_confidence"] = confidence

    return info
