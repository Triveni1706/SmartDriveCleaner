import hashlib
import os
from datetime import datetime
from pathlib import Path
from sqlalchemy.orm import Session
from database.models import ScannedFile
from services.pdf_analyzer import extract_pdf_info
from services.image_analyzer import extract_image_info, hamming_distance
from services.archive_analyzer import analyze_archive

EXTENSION_MAP = {
    "Documents": {".doc", ".docx", ".txt", ".ppt", ".pptx", ".xls", ".xlsx", ".odt"},
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"},
    "PDFs": {".pdf"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Videos": {".mp4", ".mkv", ".avi", ".mov", ".webm"},
    "Audio": {".mp3", ".wav", ".flac", ".aac"},
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}
HASH_CHUNK_SIZE = 65536
MAX_HASH_BYTES = 200 * 1024 * 1024
PARTIAL_HASH_BYTES = 50 * 1024 * 1024

SIMILAR_IMAGE_HAMMING_THRESHOLD = 5  # aHash bits differing; <=5/64 = visually near-identical


def categorize(extension: str) -> str:
    ext = extension.lower()
    for category, exts in EXTENSION_MAP.items():
        if ext in exts:
            return category
    return "Others"


def compute_sha256(filepath: str) -> str:
    sha256 = hashlib.sha256()
    try:
        size = os.path.getsize(filepath)
        with open(filepath, "rb") as f:
            if size > MAX_HASH_BYTES:
                sha256.update(f.read(PARTIAL_HASH_BYTES))
            else:
                while chunk := f.read(HASH_CHUNK_SIZE):
                    sha256.update(chunk)
        return sha256.hexdigest()
    except (PermissionError, OSError):
        return ""


def scan_single_file(full_path: str) -> dict:
    """
    Analyze one file and return a dict of ScannedFile column values (not yet
    a model instance — the caller decides whether to insert or update).
    Raises on files that can't be stat'd; caller should catch.
    """
    stat = os.stat(full_path)
    filename = os.path.basename(full_path)
    ext = Path(filename).suffix
    category = categorize(ext)
    file_hash = compute_sha256(full_path)

    record: dict = dict(
        name=filename,
        path=full_path,
        extension=ext,
        category=category,
        size_bytes=stat.st_size,
        created_at=datetime.fromtimestamp(stat.st_ctime),
        modified_at=datetime.fromtimestamp(stat.st_mtime),
        accessed_at=datetime.fromtimestamp(stat.st_atime),
        sha256=file_hash,
        is_duplicate=False,
        duplicate_group=None,
        similar_group=None,
    )

    if category == "PDFs":
        pdf_info = extract_pdf_info(full_path)
        record["pdf_page_count"] = pdf_info["page_count"]
        record["pdf_author"] = pdf_info["author"]
        record["pdf_title"] = pdf_info["title"]
        record["subcategory"] = pdf_info["subcategory"]
        record["subcategory_confidence"] = pdf_info["subcategory_confidence"]

    elif category == "Images":
        img_info = extract_image_info(full_path)
        record["image_width"] = img_info["width"]
        record["image_height"] = img_info["height"]
        record["blur_score"] = img_info["blur_score"]
        record["is_blurry"] = img_info["is_blurry"]
        record["perceptual_hash"] = img_info["perceptual_hash"]
        record["subcategory"] = img_info["subcategory"]
        record["subcategory_confidence"] = img_info["subcategory_confidence"]

    elif category == "Archives":
        arc_info = analyze_archive(full_path)
        record["archive_file_count"] = arc_info["file_count"]
        record["archive_uncompressed_bytes"] = arc_info["uncompressed_bytes"]

    return record


def scan_directory(root_path: str, db: Session, progress_callback=None) -> dict:
    root = Path(root_path)
    if not root.exists() or not root.is_dir():
        raise ValueError(f"Path does not exist or is not a directory: {root_path}")

    # This app tracks a single scanned location at a time. Clear ALL previous
    # results before scanning, not just rows under the new root — otherwise
    # scanning a different folder/drive just adds to the old data instead of
    # replacing it, and every page shows a mix of old + new folder contents.
    db.query(ScannedFile).delete(synchronize_session=False)
    db.commit()

    hash_to_paths: dict[str, list[str]] = {}
    phash_to_paths: dict[str, list[str]] = {}  # for near-dup grouping
    scanned_count = 0
    total_bytes = 0

    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]

        for filename in filenames:
            full_path = os.path.join(dirpath, filename)
            try:
                record_data = scan_single_file(full_path)
            except (PermissionError, OSError, FileNotFoundError):
                continue

            record = ScannedFile(**record_data)
            db.add(record)

            file_hash = record_data["sha256"]
            if file_hash:
                hash_to_paths.setdefault(file_hash, []).append(full_path)
            if record_data.get("perceptual_hash"):
                phash_to_paths.setdefault(record_data["perceptual_hash"], []).append(full_path)

            scanned_count += 1
            total_bytes += record_data["size_bytes"]

            if progress_callback and scanned_count % 50 == 0:
                progress_callback(scanned_count)

    db.commit()

    # Exact duplicates (SHA256)
    duplicate_wasted_bytes = 0
    for file_hash, paths in hash_to_paths.items():
        if len(paths) > 1:
            for dup_path in paths[1:]:
                record = db.query(ScannedFile).filter(ScannedFile.path == dup_path).first()
                if record:
                    record.is_duplicate = True
                    record.duplicate_group = file_hash
                    duplicate_wasted_bytes += record.size_bytes or 0
            original = db.query(ScannedFile).filter(ScannedFile.path == paths[0]).first()
            if original:
                original.duplicate_group = file_hash

    db.commit()

    # Near-duplicate images (perceptual hash, hamming distance clustering)
    # Simple greedy clustering: good enough for typical folder sizes.
    phashes = list(phash_to_paths.keys())
    assigned = set()
    similar_group_count = 0
    for i, h1 in enumerate(phashes):
        if h1 in assigned:
            continue
        cluster_paths = list(phash_to_paths[h1])
        cluster_hashes = {h1}
        for h2 in phashes[i + 1:]:
            if h2 in assigned:
                continue
            if hamming_distance(h1, h2) <= SIMILAR_IMAGE_HAMMING_THRESHOLD:
                cluster_paths.extend(phash_to_paths[h2])
                cluster_hashes.add(h2)

        # Only a "similar group" if it spans more than one file AND isn't
        # already fully covered by exact SHA256 duplicates
        distinct_paths = set(cluster_paths)
        if len(distinct_paths) > 1:
            group_id = f"sim_{h1}"
            for p in distinct_paths:
                record = db.query(ScannedFile).filter(ScannedFile.path == p).first()
                if record:
                    record.similar_group = group_id
            similar_group_count += 1
        assigned |= cluster_hashes

    db.commit()

    return {
        "scanned_files": scanned_count,
        "total_bytes": total_bytes,
        "duplicate_groups": sum(1 for p in hash_to_paths.values() if len(p) > 1),
        "duplicate_wasted_bytes": duplicate_wasted_bytes,
        "similar_image_groups": similar_group_count,
    }
