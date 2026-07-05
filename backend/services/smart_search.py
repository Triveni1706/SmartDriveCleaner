"""
Smart search: turns natural-language queries like "show invoices from 2025"
or "screenshots older than 6 months" into a structured filter against
ScannedFile, then runs it.

Honest scope note: this is NOT semantic/embedding search (no vector DB, no
sentence-transformers) — it's a rule-based NL-to-filter parser. That's a
deliberate choice for a local single-user tool: it's instant, needs no model
download, and covers the query patterns that actually matter here (category,
subcategory, date range, size, duplicate/blur status) far more reliably than
a small local embedding model would. The parser is transparent about what it
matched so results are explainable, not a black box.
"""
import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import or_

from database.models import ScannedFile

SUBCATEGORY_ALIASES = {
    "resume": "Resume", "resumes": "Resume", "cv": "Resume",
    "invoice": "Invoice", "invoices": "Invoice", "receipt": "Invoice", "receipts": "Invoice", "bill": "Invoice", "bills": "Invoice",
    "certificate": "Certificate", "certificates": "Certificate", "certification": "Certificate",
    "research paper": "Research Paper", "research papers": "Research Paper", "paper": "Research Paper", "papers": "Research Paper",
    "book": "Book", "books": "Book", "ebook": "Book", "ebooks": "Book",
    "note": "Notes", "notes": "Notes",
    "screenshot": "Screenshot", "screenshots": "Screenshot",
    "photo": "Photo", "photos": "Photo", "picture": "Photo", "pictures": "Photo",
}

CATEGORY_ALIASES = {
    "pdf": "PDFs", "pdfs": "PDFs",
    "image": "Images", "images": "Images", "picture": "Images", "pictures": "Images",
    "document": "Documents", "documents": "Documents", "doc": "Documents", "docs": "Documents",
    "archive": "Archives", "archives": "Archives", "zip": "Archives", "zips": "Archives",
    "video": "Videos", "videos": "Videos",
    "audio": "Audio", "song": "Audio", "songs": "Audio", "music": "Audio",
}

MONTH_UNITS = {"month": 30, "months": 30, "week": 7, "weeks": 7, "day": 1, "days": 1, "year": 365, "years": 365}


def parse_query(query: str) -> dict:
    """Returns a structured, human-readable-back filter spec."""
    q = query.lower().strip()
    filters: dict = {"raw_query": query}

    # Subcategory (check before generic category — "invoices" should not
    # also match nothing, and is more specific than "documents")
    for alias, subcat in SUBCATEGORY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", q):
            filters["subcategory"] = subcat
            break

    # Category
    if "subcategory" not in filters:
        for alias, cat in CATEGORY_ALIASES.items():
            if re.search(rf"\b{re.escape(alias)}\b", q):
                filters["category"] = cat
                break

    # Year, e.g. "from 2025", "in 2024"
    year_match = re.search(r"\b(20\d{2})\b", q)
    if year_match:
        filters["year"] = int(year_match.group(1))

    # Relative age: "older than 6 months", "older than 1 year"
    age_match = re.search(r"older than (\d+)\s*(day|days|week|weeks|month|months|year|years)", q)
    if age_match:
        n, unit = int(age_match.group(1)), age_match.group(2)
        filters["older_than_days"] = n * MONTH_UNITS[unit]

    newer_match = re.search(r"(newer than|added in the last|from the last)\s*(\d+)\s*(day|days|week|weeks|month|months|year|years)", q)
    if newer_match:
        n, unit = int(newer_match.group(2)), newer_match.group(3)
        filters["newer_than_days"] = n * MONTH_UNITS[unit]

    # Size, e.g. "larger than 100mb", "bigger than 1gb"
    size_match = re.search(r"(larger than|bigger than|over|above)\s*(\d+(?:\.\d+)?)\s*(kb|mb|gb)", q)
    if size_match:
        n, unit = float(size_match.group(2)), size_match.group(3)
        mult = {"kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3}[unit]
        filters["min_bytes"] = int(n * mult)

    if "duplicate" in q or "duplicates" in q:
        filters["is_duplicate"] = True
    if "blurry" in q or "blur" in q:
        filters["is_blurry"] = True

    # Free-text fallback: whatever's left after stripping recognized tokens,
    # matched against filename (handles "find my resume.pdf" style queries).
    stripped = q
    for pattern in [r"show", r"find", r"my", r"from \d{4}", r"older than.*", r"newer than.*",
                     r"the last.*", r"larger than.*", r"bigger than.*"]:
        stripped = re.sub(pattern, "", stripped)
    stripped = stripped.strip(" .,!?")
    if stripped and "subcategory" not in filters and "category" not in filters:
        filters["name_contains"] = stripped

    return filters


def run_search(db: Session, query: str, limit: int = 100) -> dict:
    filters = parse_query(query)
    qs = db.query(ScannedFile)

    if "subcategory" in filters:
        qs = qs.filter(ScannedFile.subcategory == filters["subcategory"])
    if "category" in filters:
        qs = qs.filter(ScannedFile.category == filters["category"])
    if "year" in filters:
        start = datetime(filters["year"], 1, 1)
        end = datetime(filters["year"] + 1, 1, 1)
        qs = qs.filter(ScannedFile.modified_at >= start, ScannedFile.modified_at < end)
    if "older_than_days" in filters:
        cutoff = datetime.now() - timedelta(days=filters["older_than_days"])
        qs = qs.filter(ScannedFile.modified_at < cutoff)
    if "newer_than_days" in filters:
        cutoff = datetime.now() - timedelta(days=filters["newer_than_days"])
        qs = qs.filter(ScannedFile.modified_at >= cutoff)
    if "min_bytes" in filters:
        qs = qs.filter(ScannedFile.size_bytes >= filters["min_bytes"])
    if filters.get("is_duplicate"):
        qs = qs.filter(ScannedFile.is_duplicate == True)
    if filters.get("is_blurry"):
        qs = qs.filter(ScannedFile.is_blurry == True)
    if "name_contains" in filters:
        term = f"%{filters['name_contains']}%"
        qs = qs.filter(or_(ScannedFile.name.ilike(term), ScannedFile.path.ilike(term)))

    results = qs.order_by(ScannedFile.size_bytes.desc()).limit(limit).all()

    return {
        "interpreted_as": _describe(filters),
        "filters": {k: v for k, v in filters.items() if k != "raw_query"},
        "results": results,
    }


def _describe(filters: dict) -> str:
    parts = []
    if "subcategory" in filters:
        parts.append(f"subcategory = {filters['subcategory']}")
    if "category" in filters:
        parts.append(f"category = {filters['category']}")
    if "year" in filters:
        parts.append(f"modified in {filters['year']}")
    if "older_than_days" in filters:
        parts.append(f"older than {filters['older_than_days']} days")
    if "newer_than_days" in filters:
        parts.append(f"newer than {filters['newer_than_days']} days")
    if "min_bytes" in filters:
        parts.append(f"size ≥ {filters['min_bytes']:,} bytes")
    if filters.get("is_duplicate"):
        parts.append("is duplicate")
    if filters.get("is_blurry"):
        parts.append("is blurry")
    if "name_contains" in filters:
        parts.append(f"name/path contains '{filters['name_contains']}'")
    return "; ".join(parts) if parts else "no specific filters recognized — showing all files"
