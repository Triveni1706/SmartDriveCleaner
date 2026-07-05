"""
Stage 2 — Deep Analysis.

Runs only on the categories the user selected in the dashboard, and only on
files whose Stage 1 quick scan marked them as new/changed (analyzed_at is
None). Unchanged files keep whatever analysis they already had — that's the
"skip unchanged files" incremental-scanning piece.

Work is fanned out across a thread pool: hashing and PDF/image parsing are
I/O- and C-extension-heavy (pypdf, OpenCV, zipfile all release the GIL for
the bulk of their work), so threads give real parallelism here without the
serialization overhead of a process pool.
"""
import os
import time
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from database.db import SessionLocal
from database.models import ScannedFile
from services.pdf_analyzer import extract_pdf_info
from services.image_analyzer import extract_image_info, hamming_distance
from services.archive_analyzer import analyze_archive
from services import job_manager

# Which categories get extra, category-specific analysis beyond hash + dup
# detection (per the product spec). Anything else selected (Videos, Audio,
# Documents, Others) still gets hashing + duplicate detection.
EXTRA_ANALYSIS = {"Images", "PDFs", "Archives"}

MAX_WORKERS = min(32, (os.cpu_count() or 4) * 4)
HASH_CHUNK_SIZE = 65536
MAX_HASH_BYTES = 200 * 1024 * 1024
PARTIAL_HASH_BYTES = 50 * 1024 * 1024
SIMILAR_IMAGE_HAMMING_THRESHOLD = 5

# Rough per-file cost used for the "estimated analysis time" shown in the
# Stage 1 dashboard, before any analysis has actually run. Calibrated
# loosely against typical consumer hardware — good enough for an ETA, not a
# guarantee.
ESTIMATED_SECONDS_PER_FILE = {
    "Images": 0.04,
    "PDFs": 0.06,
    "Archives": 0.08,
    "Documents": 0.02,
    "Videos": 0.05,
    "Audio": 0.02,
    "Others": 0.015,
}


def estimate_seconds(category: str, file_count: int) -> float:
    return round(ESTIMATED_SECONDS_PER_FILE.get(category, 0.02) * file_count, 1)


def _compute_sha256(filepath: str) -> str:
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


def _analyze_one(file_id: int, path: str, category: str) -> dict:
    """Runs on a worker thread. Pure computation + filesystem reads only —
    no DB session touches this thread, so results are handed back to the
    main thread to apply."""
    result: dict = {"id": file_id, "sha256": _compute_sha256(path)}

    if category == "Images":
        info = extract_image_info(path)
        result.update({
            "image_width": info["width"],
            "image_height": info["height"],
            "blur_score": info["blur_score"],
            "is_blurry": info["is_blurry"],
            "perceptual_hash": info["perceptual_hash"],
            "subcategory": info["subcategory"],
            "subcategory_confidence": info["subcategory_confidence"],
        })
    elif category == "PDFs":
        info = extract_pdf_info(path)
        result.update({
            "pdf_page_count": info["page_count"],
            "pdf_author": info["author"],
            "pdf_title": info["title"],
            "subcategory": info["subcategory"],
            "subcategory_confidence": info["subcategory_confidence"],
        })
    elif category == "Archives":
        info = analyze_archive(path)
        result.update({
            "archive_file_count": info["file_count"],
            "archive_uncompressed_bytes": info["uncompressed_bytes"],
        })

    return result


def _detect_duplicates_for_category(db, category: str) -> tuple[int, int]:
    """SHA256 exact-duplicate grouping, scoped to one category so a Deep
    Analysis run on 'PDFs' never touches Images rows, etc."""
    rows = db.query(ScannedFile).filter(ScannedFile.category == category, ScannedFile.sha256 != "").all()
    by_hash: dict[str, list[ScannedFile]] = {}
    for row in rows:
        by_hash.setdefault(row.sha256, []).append(row)
        row.is_duplicate = False
        row.duplicate_group = None

    dup_groups = 0
    wasted_bytes = 0
    for file_hash, group in by_hash.items():
        if len(group) > 1:
            dup_groups += 1
            group.sort(key=lambda r: r.id)
            group[0].duplicate_group = file_hash
            for dup in group[1:]:
                dup.is_duplicate = True
                dup.duplicate_group = file_hash
                wasted_bytes += dup.size_bytes or 0
    return dup_groups, wasted_bytes


def _detect_similar_images(db) -> int:
    rows = (
        db.query(ScannedFile)
        .filter(ScannedFile.category == "Images", ScannedFile.perceptual_hash.isnot(None))
        .all()
    )
    for row in rows:
        row.similar_group = None

    phash_to_rows: dict[str, list[ScannedFile]] = {}
    for row in rows:
        phash_to_rows.setdefault(row.perceptual_hash, []).append(row)

    phashes = list(phash_to_rows.keys())
    assigned: set[str] = set()
    groups = 0
    for i, h1 in enumerate(phashes):
        if h1 in assigned:
            continue
        cluster_rows = list(phash_to_rows[h1])
        cluster_hashes = {h1}
        for h2 in phashes[i + 1:]:
            if h2 in assigned:
                continue
            if hamming_distance(h1, h2) <= SIMILAR_IMAGE_HAMMING_THRESHOLD:
                cluster_rows.extend(phash_to_rows[h2])
                cluster_hashes.add(h2)

        distinct = {r.id: r for r in cluster_rows}
        if len(distinct) > 1:
            group_id = f"sim_{h1}"
            for r in distinct.values():
                r.similar_group = group_id
            groups += 1
        assigned |= cluster_hashes

    return groups


def run_deep_scan(job_id: str, categories: list[str]):
    db = SessionLocal()
    try:
        job_manager.update_job(job_id, status="running", current_task="Preparing analysis…")

        to_process = (
            db.query(ScannedFile)
            .filter(ScannedFile.category.in_(categories), ScannedFile.analyzed_at.is_(None))
            .all()
        )
        total = len(to_process)
        job_manager.update_job(job_id, total_items=total, completed_items=0)

        completed = 0
        last_update = time.perf_counter()

        if total > 0:
            with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
                futures = {
                    pool.submit(_analyze_one, row.id, row.path, row.category): row
                    for row in to_process
                }
                for future in as_completed(futures):
                    row = futures[future]
                    try:
                        data = future.result()
                    except Exception:
                        data = {"id": row.id, "sha256": ""}

                    for key, value in data.items():
                        if key == "id":
                            continue
                        setattr(row, key, value)
                    row.analyzed_at = datetime.utcnow()
                    row.content_signature = f"{row.size_bytes}:{row.modified_at.isoformat() if row.modified_at else ''}"

                    completed += 1
                    now = time.perf_counter()
                    if completed % 25 == 0 or now - last_update > 0.3:
                        db.commit()
                        job_manager.update_job(
                            job_id,
                            completed_items=completed,
                            percent=round(completed / total * 100, 1),
                            current_task=f"Analyzing {row.category}: {row.name}",
                        )
                        last_update = now

            db.commit()

        # Duplicate detection (and similar-image clustering) runs over the
        # FULL category, not just newly-analyzed files, because a new file
        # can duplicate one that was analyzed in an earlier run.
        summary = {}
        for category in categories:
            job_manager.update_job(job_id, current_task=f"Finding duplicates in {category}…")
            dup_groups, wasted = _detect_duplicates_for_category(db, category)
            db.commit()
            summary[category] = {"duplicate_groups": dup_groups, "duplicate_wasted_bytes": wasted}

        if "Images" in categories:
            job_manager.update_job(job_id, current_task="Grouping similar images…")
            similar_groups = _detect_similar_images(db)
            db.commit()
            summary["Images"]["similar_image_groups"] = similar_groups

        job_manager.update_job(job_id, completed_items=total, total_items=total)
        job_manager.finish_job(
            job_id,
            status="completed",
            result={
                "categories": categories,
                "files_analyzed": total,
                "by_category": summary,
            },
        )
    except Exception as e:  # noqa: BLE001
        db.rollback()
        job_manager.finish_job(job_id, status="error", error=str(e))
    finally:
        db.close()
