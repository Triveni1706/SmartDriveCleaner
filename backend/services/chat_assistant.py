"""
AI Chat Assistant: answers questions about the scanned drive by running real
DB queries — "which files consume the most storage", "which files are
unused", "which files should I delete" — and returning grounded, accurate
answers rather than a general-purpose LLM guessing at your filesystem.

Design: intent is matched with a rule-based router (fast, deterministic, no
hallucination about your actual files) with smart_search.py handling
anything free-form ("show me invoices from 2025"). This is intentionally NOT
wired to an external LLM API by default — it needs no API key and never
sends your filenames/paths to a third party. If you want more natural
phrasing on top of these grounded answers, see the note at the bottom of
this file for how to add an optional Anthropic API layer.
"""
import re
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func

from database.models import ScannedFile
from services.smart_search import run_search
from services.recommendations import generate_recommendations

UNUSED_DAYS = 180


def _fmt_bytes(b: int) -> str:
    if not b:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i, val = 0, float(b)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    return f"{val:.1f} {units[i]}"


def answer(db: Session, message: str) -> dict:
    q = message.lower().strip()

    # --- "Which files consume the most storage?" ---
    if re.search(r"(most storage|biggest|largest|consume.*most|take up.*most|hog)", q):
        top = db.query(ScannedFile).order_by(ScannedFile.size_bytes.desc()).limit(10).all()
        if not top:
            return _reply("No scanned files yet — run a scan from the Overview page first.")
        lines = [f"{i+1}. {f.name} — {_fmt_bytes(f.size_bytes)}" for i, f in enumerate(top)]
        return _reply(
            "Your biggest files are:\n" + "\n".join(lines),
            file_ids=[f.id for f in top],
        )

    # --- "Which files are unused?" ---
    if re.search(r"(unused|not.*used|haven'?t (been )?(used|opened|touched)|never (used|opened))", q):
        cutoff = datetime.now() - timedelta(days=UNUSED_DAYS)
        unused = (
            db.query(ScannedFile)
            .filter(ScannedFile.accessed_at < cutoff)
            .order_by(ScannedFile.size_bytes.desc())
            .limit(15)
            .all()
        )
        if not unused:
            return _reply(f"Nothing looks unused — every scanned file has been accessed within the last {UNUSED_DAYS} days.")
        total = sum(f.size_bytes or 0 for f in unused)
        lines = [f"{f.name} — last accessed {f.accessed_at.strftime('%b %Y') if f.accessed_at else 'unknown'}" for f in unused]
        return _reply(
            f"{len(unused)} files haven't been accessed in {UNUSED_DAYS}+ days ({_fmt_bytes(total)} total):\n"
            + "\n".join(lines),
            file_ids=[f.id for f in unused],
        )

    # --- "Which files should I delete?" ---
    if re.search(r"(should i delete|what.*delete|safe to (delete|remove)|clean.?up)", q):
        recs = generate_recommendations(db)
        if not recs:
            return _reply("Nothing stands out — no duplicates, blurry images, or stale files found. Your drive looks clean.")
        lines = [f"• {r['title']} — {r['detail']}" for r in recs]
        all_ids = [fid for r in recs for fid in r["file_ids"]]
        return _reply(
            "Based on what's actually in your scan, here's what I'd flag:\n" + "\n".join(lines),
            file_ids=all_ids,
        )

    # --- Duplicate summary ---
    if re.search(r"duplicate", q):
        count = db.query(func.count(ScannedFile.id)).filter(ScannedFile.is_duplicate == True).scalar() or 0
        wasted = db.query(func.sum(ScannedFile.size_bytes)).filter(ScannedFile.is_duplicate == True).scalar() or 0
        if count == 0:
            return _reply("No duplicate files found in the current scan.")
        return _reply(f"You have {count} duplicate files wasting {_fmt_bytes(wasted)}. Check the Duplicates page to review and delete them.")

    # --- Overall storage summary ---
    if re.search(r"(how much (space|storage)|total (size|storage|files)|overview|summary)", q):
        total_files = db.query(func.count(ScannedFile.id)).scalar() or 0
        total_bytes = db.query(func.sum(ScannedFile.size_bytes)).scalar() or 0
        if total_files == 0:
            return _reply("No scan data yet — run a scan from the Overview page first.")
        return _reply(f"You've scanned {total_files:,} files totaling {_fmt_bytes(total_bytes)}.")

    # --- Fall through to smart search for anything else specific ---
    search_result = run_search(db, message, limit=10)
    if search_result["filters"]:
        results = search_result["results"]
        if not results:
            return _reply(f"I searched for {search_result['interpreted_as']}, but found nothing matching.")
        lines = [f"{f.name} — {_fmt_bytes(f.size_bytes)}" for f in results]
        return _reply(
            f"Interpreted as: {search_result['interpreted_as']}\n\n" + "\n".join(lines),
            file_ids=[f.id for f in results],
        )

    return _reply(
        "I can answer things like: 'which files consume the most storage', "
        "'which files are unused', 'which files should I delete', "
        "'how many duplicates do I have', or a search like 'show invoices from 2025'."
    )


def _reply(text: str, file_ids: list[int] | None = None) -> dict:
    return {"reply": text, "file_ids": file_ids or []}


# --- Optional: natural-language phrasing layer ---
# If you want the assistant to phrase these grounded answers more
# conversationally (rather than the direct, structured text above), you can
# route `text` through the Anthropic API before returning it — pass the
# grounded facts as context so the model rephrases rather than invents:
#
#   from anthropic import Anthropic
#   client = Anthropic()  # reads ANTHROPIC_API_KEY from env
#   resp = client.messages.create(
#       model="claude-sonnet-4-6", max_tokens=300,
#       messages=[{"role": "user", "content": f"Rephrase this drive-cleanup answer conversationally, don't add facts not present: {text}"}],
#   )
#
# Intentionally left out of the default path so this feature works fully
# offline with zero API keys or costs for local/daily use.
