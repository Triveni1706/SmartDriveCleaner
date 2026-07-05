"""
PDF analysis: real metadata extraction via PyPDF2, plus rule-based
(non-ML) category classification using filename patterns and extracted text.

Honest scope note: this is NOT a trained ML classifier. A real Resume vs
Invoice vs Research Paper model needs labeled training data. This uses
keyword/pattern heuristics against the filename + first-page text, which
works reasonably well for common cases but will misclassify edge cases.
Confidence score reflects how many independent signals agreed.
"""
import re
from pypdf import PdfReader

# (subcategory, filename patterns, content keywords)
PDF_RULES = [
    ("Resume", [r"resume", r"\bcv\b", r"curriculum.?vitae"], ["work experience", "education", "skills", "objective", "references"]),
    ("Invoice", [r"invoice", r"receipt", r"bill"], ["invoice number", "total due", "amount due", "bill to", "payment terms", "subtotal"]),
    ("Certificate", [r"certificate", r"certification", r"award"], ["certificate of", "awarded to", "has successfully completed", "this is to certify"]),
    ("Research Paper", [r"paper", r"research", r"arxiv", r"journal"], ["abstract", "references", "introduction", "methodology", "et al"]),
    ("Book", [r"book", r"ebook", r"novel"], ["chapter 1", "table of contents", "isbn"]),
    ("Notes", [r"notes?", r"lecture", r"summary"], []),
]


def extract_pdf_info(filepath: str) -> dict:
    """Returns metadata + best-guess subcategory with confidence. Never raises."""
    info = {
        "page_count": None,
        "author": None,
        "title": None,
        "subcategory": "Unclassified",
        "subcategory_confidence": 0.0,
    }
    try:
        reader = PdfReader(filepath)
        info["page_count"] = len(reader.pages)

        meta = reader.metadata
        if meta:
            info["author"] = meta.author
            info["title"] = meta.title

        first_page_text = ""
        if reader.pages:
            try:
                first_page_text = (reader.pages[0].extract_text() or "").lower()
            except Exception:
                first_page_text = ""

        import os
        filename = os.path.basename(filepath).lower()

        best_category, best_score = "Unclassified", 0
        for category, filename_patterns, keywords in PDF_RULES:
            score = 0
            for pat in filename_patterns:
                if re.search(pat, filename):
                    score += 2
            for kw in keywords:
                if kw in first_page_text:
                    score += 1
            if score > best_score:
                best_category, best_score = category, score

        if best_score > 0:
            # normalize confidence: cap contributing signals at 5 for a 0-1 scale
            info["subcategory"] = best_category
            info["subcategory_confidence"] = round(min(best_score / 5, 1.0), 2)

    except Exception:
        pass  # encrypted/corrupt PDFs: leave metadata as None, subcategory Unclassified

    return info
