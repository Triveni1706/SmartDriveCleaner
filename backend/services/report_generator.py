"""
Generates PDF reports (real PDFs via reportlab, not HTML-to-PDF) summarizing
the current scan: storage breakdown, duplicate files, and recommendations.
Used by both the manual "Generate report" action and the scheduler.
"""
import os
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak

from database.models import ScannedFile
from services.recommendations import generate_recommendations

REPORTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "reports")


def _fmt_bytes(b: int) -> str:
    if not b:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    i, val = 0, float(b)
    while val >= 1024 and i < len(units) - 1:
        val /= 1024
        i += 1
    return f"{val:.1f} {units[i]}"


def generate_pdf_report(db: Session) -> str:
    """Builds a PDF report and returns its filepath."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(REPORTS_DIR, f"drive_report_{timestamp}.pdf")

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], spaceAfter=4)
    h2 = styles["Heading2"]
    normal = styles["Normal"]

    doc = SimpleDocTemplate(filepath, pagesize=letter, topMargin=0.7 * inch, bottomMargin=0.7 * inch)
    story = []

    story.append(Paragraph("Smart Drive Cleaner — Storage Report", title_style))
    story.append(Paragraph(datetime.now().strftime("Generated %B %d, %Y at %I:%M %p"), normal))
    story.append(Spacer(1, 0.25 * inch))

    # --- Storage summary ---
    total_files = db.query(func.count(ScannedFile.id)).scalar() or 0
    total_bytes = db.query(func.sum(ScannedFile.size_bytes)).scalar() or 0
    dup_files = db.query(func.count(ScannedFile.id)).filter(ScannedFile.is_duplicate == True).scalar() or 0
    dup_bytes = db.query(func.sum(ScannedFile.size_bytes)).filter(ScannedFile.is_duplicate == True).scalar() or 0

    story.append(Paragraph("Storage Summary", h2))
    summary_data = [
        ["Metric", "Value"],
        ["Total files scanned", f"{total_files:,}"],
        ["Total size", _fmt_bytes(total_bytes)],
        ["Duplicate files", f"{dup_files:,}"],
        ["Recoverable space", _fmt_bytes(dup_bytes)],
    ]
    summary_table = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    summary_table.setStyle(_table_style())
    story.append(summary_table)
    story.append(Spacer(1, 0.3 * inch))

    # --- By category ---
    story.append(Paragraph("Storage by Category", h2))
    rows = (
        db.query(ScannedFile.category, func.count(ScannedFile.id), func.sum(ScannedFile.size_bytes))
        .group_by(ScannedFile.category)
        .order_by(func.sum(ScannedFile.size_bytes).desc())
        .all()
    )
    cat_data = [["Category", "Files", "Size"]] + [
        [cat, f"{count:,}", _fmt_bytes(size or 0)] for cat, count, size in rows
    ]
    cat_table = Table(cat_data, colWidths=[2.5 * inch, 1.5 * inch, 2 * inch])
    cat_table.setStyle(_table_style())
    story.append(cat_table)
    story.append(Spacer(1, 0.3 * inch))

    # --- Duplicate files (top 25 by size) ---
    story.append(Paragraph("Duplicate Files (largest first)", h2))
    dups = (
        db.query(ScannedFile)
        .filter(ScannedFile.is_duplicate == True)
        .order_by(ScannedFile.size_bytes.desc())
        .limit(25)
        .all()
    )
    if dups:
        dup_data = [["File", "Size"]] + [[_truncate(f.path), _fmt_bytes(f.size_bytes)] for f in dups]
        dup_table = Table(dup_data, colWidths=[4.5 * inch, 1.5 * inch])
        dup_table.setStyle(_table_style())
        story.append(dup_table)
    else:
        story.append(Paragraph("No duplicate files found.", normal))
    story.append(PageBreak())

    # --- Recommendations ---
    story.append(Paragraph("Recommendations", h2))
    recs = generate_recommendations(db)
    if recs:
        for rec in recs:
            story.append(Paragraph(f"<b>{rec['title']}</b>", normal))
            story.append(Paragraph(rec["detail"], normal))
            story.append(Spacer(1, 0.12 * inch))
    else:
        story.append(Paragraph("No recommendations — drive looks clean.", normal))

    doc.build(story)
    return filepath


def _truncate(path: str, max_len: int = 70) -> str:
    return path if len(path) <= max_len else "…" + path[-(max_len - 1):]


def _table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2A3A33")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#444444")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F4F4F4")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ])
