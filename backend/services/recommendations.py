"""
Recommendation engine: rule-based (not ML) suggestions derived from data
already in the database. Each recommendation is fully explainable —
it names the exact rule and the exact files it applies to.
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from database.models import ScannedFile

OLD_FILE_DAYS = 180
UNUSED_1_YEAR_DAYS = 365

# Large-file tiers, biggest first — a file is bucketed into the highest
# tier it qualifies for so it's never double-counted across tiers.
LARGE_FILE_TIERS = [
    (1024 ** 3, "1 GB"),
    (500 * 1024 ** 2, "500 MB"),
    (100 * 1024 ** 2, "100 MB"),
]


def generate_recommendations(db: Session, categories: list[str] | None = None) -> list[dict]:
    """
    Rule-based recommendations. If `categories` is given, every rule is
    scoped to those categories — since Stage 2 (deep analysis) only ever
    populates is_duplicate/is_blurry/subcategory for categories the user
    actually selected, recommendations naturally stay scoped to what was
    analyzed even without this filter, but passing it explicitly avoids
    surfacing stale results from a previous deep-analysis run.
    """
    recs = []
    cat_filter = (lambda q: q.filter(ScannedFile.category.in_(categories))) if categories else (lambda q: q)

    # 1. Duplicate files
    dup_query = cat_filter(db.query(ScannedFile)).filter(ScannedFile.is_duplicate == True)
    dup_files = dup_query.all()
    dup_bytes = sum(f.size_bytes or 0 for f in dup_files)
    if dup_files:
        recs.append({
            "type": "duplicates",
            "title": f"Remove {len(dup_files)} duplicate file{'s' if len(dup_files) != 1 else ''}",
            "detail": f"Frees up {_fmt(dup_bytes)}. Exact byte-for-byte copies detected via SHA256.",
            "file_ids": [f.id for f in dup_files],
            "bytes_recoverable": dup_bytes,
        })

    # 2. Similar (near-duplicate) images — only relevant if Images was analyzed
    if categories is None or "Images" in categories:
        similar_files = db.query(ScannedFile).filter(ScannedFile.similar_group.isnot(None)).all()
        similar_groups = len({f.similar_group for f in similar_files})
        if similar_groups > 0:
            recs.append({
                "type": "similar_images",
                "title": f"Review {similar_groups} group(s) of visually similar images",
                "detail": "Detected via perceptual hashing (resized/recompressed copies, not byte-identical).",
                "file_ids": [f.id for f in similar_files],
                "bytes_recoverable": 0,
            })

        # 3. Blurry screenshots/photos
        blurry = db.query(ScannedFile).filter(ScannedFile.is_blurry == True).all()
        if blurry:
            blurry_bytes = sum(f.size_bytes or 0 for f in blurry)
            recs.append({
                "type": "blurry_images",
                "title": f"Delete {len(blurry)} blurry image{'s' if len(blurry) != 1 else ''}",
                "detail": f"Low sharpness score (OpenCV edge-variance below threshold). Frees {_fmt(blurry_bytes)}.",
                "file_ids": [f.id for f in blurry],
                "bytes_recoverable": blurry_bytes,
            })

    # 4. Old, unmodified large files
    cutoff = datetime.now() - timedelta(days=OLD_FILE_DAYS)
    old_query = cat_filter(db.query(ScannedFile)).filter(
        ScannedFile.modified_at < cutoff, ScannedFile.is_duplicate == False
    )
    old_files = old_query.order_by(ScannedFile.size_bytes.desc()).limit(50).all()
    if old_files:
        old_bytes = sum(f.size_bytes or 0 for f in old_files)
        recs.append({
            "type": "old_files",
            "title": f"Archive {len(old_files)} file{'s' if len(old_files) != 1 else ''} untouched for 6+ months",
            "detail": f"Not modified since {cutoff.strftime('%b %Y')}. Combined size {_fmt(old_bytes)}.",
            "file_ids": [f.id for f in old_files],
            "bytes_recoverable": 0,  # archiving, not deleting
        })

    # 4b. Files untouched for a full year — a stricter, separate tier from
    # the 6-month "old files" rule above (spec explicitly calls out both
    # "not used for 6 months" and "not used for 1 year").
    cutoff_1y = datetime.now() - timedelta(days=UNUSED_1_YEAR_DAYS)
    unused_1y = cat_filter(db.query(ScannedFile)).filter(
        ScannedFile.modified_at < cutoff_1y, ScannedFile.is_duplicate == False
    ).order_by(ScannedFile.size_bytes.desc()).limit(50).all()
    if unused_1y:
        unused_bytes = sum(f.size_bytes or 0 for f in unused_1y)
        recs.append({
            "type": "unused_1_year",
            "title": f"{len(unused_1y)} file{'s' if len(unused_1y) != 1 else ''} not used in over a year",
            "detail": f"Not modified since {cutoff_1y.strftime('%b %Y')}. Strong archive/delete candidates. Combined size {_fmt(unused_bytes)}.",
            "file_ids": [f.id for f in unused_1y],
            "bytes_recoverable": 0,  # archiving, not auto-deleting
        })

    # 4c. Large files, tiered (>1GB, >500MB, >100MB) — each file lands in
    # only its highest-qualifying tier so totals don't overlap.
    seen_large_ids: set[int] = set()
    for threshold, label in LARGE_FILE_TIERS:
        q = cat_filter(db.query(ScannedFile)).filter(ScannedFile.size_bytes >= threshold)
        files = [f for f in q.order_by(ScannedFile.size_bytes.desc()).limit(100).all() if f.id not in seen_large_ids]
        if files:
            seen_large_ids.update(f.id for f in files)
            total_bytes = sum(f.size_bytes or 0 for f in files)
            recs.append({
                "type": f"large_files_{label.replace(' ', '_').lower()}",
                "title": f"{len(files)} file{'s' if len(files) != 1 else ''} larger than {label}",
                "detail": f"Storage-heavy files worth reviewing individually. Combined size {_fmt(total_bytes)}.",
                "file_ids": [f.id for f in files],
                "bytes_recoverable": 0,  # review, not auto-deleting large personal files
            })

    # 4d. Empty folders (filesystem check, not DB-backed — folders aren't
    # indexed as ScannedFile rows).
    most_recent_root = db.query(ScannedFile.scan_root).order_by(ScannedFile.id.desc()).first()
    if most_recent_root and most_recent_root[0]:
        from services.file_ops import find_empty_folders
        empty_dirs = find_empty_folders(most_recent_root[0])
        if empty_dirs:
            recs.append({
                "type": "empty_folders",
                "title": f"{len(empty_dirs)} empty folder{'s' if len(empty_dirs) != 1 else ''} found",
                "detail": "Folders with no files (and no non-empty subfolders). Safe to remove.",
                "file_ids": [],
                "bytes_recoverable": 0,
                "folder_paths": [d["path"] for d in empty_dirs],
            })

    # 4e. ZIP backups — an archive that shadows a same-named folder already
    # on disk (e.g. "Project/" and "Project.zip" both present).
    if categories is None or "Archives" in categories:
        from services.archive_analyzer import detect_zip_backups
        archives = db.query(ScannedFile).filter(ScannedFile.category == "Archives").all()
        pairs = detect_zip_backups(archives)
        if pairs:
            pairs_bytes = sum(p["archive_bytes"] for p in pairs)
            recs.append({
                "type": "zip_backups",
                "title": f"{len(pairs)} ZIP backup{'s' if len(pairs) != 1 else ''} of folders that still exist",
                "detail": f"Archive and original folder both present — safe to remove one copy. Frees {_fmt(pairs_bytes)} if archives are deleted.",
                "file_ids": [p["archive_id"] for p in pairs],
                "bytes_recoverable": pairs_bytes,
            })

    # 5. Unclassified/low-confidence PDFs worth a manual look
    if categories is None or "PDFs" in categories:
        low_conf_pdfs = (
            db.query(ScannedFile)
            .filter(ScannedFile.category == "PDFs", ScannedFile.subcategory_confidence < 0.3)
            .count()
        )
        if low_conf_pdfs > 0:
            recs.append({
                "type": "unclassified_pdfs",
                "title": f"{low_conf_pdfs} PDF(s) could not be confidently categorized",
                "detail": "Heuristic classifier found no strong filename/content match — manual review suggested.",
                "file_ids": [],
                "bytes_recoverable": 0,
            })

    recs.sort(key=lambda r: r["bytes_recoverable"], reverse=True)
    return recs


def _fmt(b: int) -> str:
    if not b:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    val = float(b)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    return f"{val:.1f} {units[i]}"
