# Smart Drive Cleaner — Phase 1 + Phase 2 + Phase 3 + Phase 4

## Phase 4 — direct file management, safe delete, collections, and sharper recommendations

Gap analysis against the master spec found the two-stage scan, persistent
search, real-time monitoring, incremental scanning, and Docker/Postgres
support already fully implemented (Phase 3). This pass fills in what was
missing, without touching any of that:

| Feature | Files | Notes |
|---|---|---|
| **Direct file management** | `services/file_ops.py`, `api/file_ops.py`, `FileExplorer.tsx` | Open file, open containing folder, rename, move, copy — all act on the real filesystem and keep the DB row in sync, no rescan needed. Bulk select in File Explorer. |
| **Safe Delete System** | same + `TrashItem` model | Deleting from File Explorer / Duplicates / Image Manager / Recommendations now moves files into `SmartDriveCleaner_Trash` at the scan root instead of `os.remove()`. The old hard-delete endpoint (`DELETE /api/files`) still exists for backward compatibility but the UI no longer calls it directly. |
| **Recovery Center** | `Trash.tsx`, `/api/trash*` | View trashed files, restore individually or in bulk, permanently delete, or empty the whole trash. |
| **Collection Manager** | `services/collections.py`, `api/collections.py`, `Collections.tsx` | Create/rename/delete named collections, add/remove files (from File Explorer's bulk toolbar or per-row), view a collection's contents and total size. |
| **ZIP backup detection** | `archive_analyzer.detect_zip_backups()` | Flags an archive when a same-named folder still sits next to it on disk (the `Project/` + `Project.zip` case from the spec) — filesystem check, since folders aren't indexed as files. Surfaced as a recommendation with one-click "move to trash." |
| **Empty folder detection** | `file_ops.find_empty_folders()` | Bottom-up walk of the last scanned root; a folder counts as empty only if it and every subfolder have no files. Surfaced as a recommendation with a "delete folders" action. |
| **Sharper recommendations** | `services/recommendations.py` | Added tiered large-file call-outs (>100MB / >500MB / >1GB, each file counted once in its highest tier), a stricter "not modified in 1 year" tier alongside the existing 6-month one, plus the two rules above. |
| **Persistent search status strip** | `/api/search/status`, `SmartSearch.tsx` | "Indexed Files / Last Scan / Status: Ready" strip from the spec, backed by a real count + the most recent completed scan job — search itself was already fully DB-indexed and rescan-free. |

Every new backend route was exercised against a real scratch filesystem
(quick scan → deep scan → zip-backup pairing → empty-folder walk →
recommendations → rename → safe-delete → restore → collections) before
being handed off, and the frontend passes a clean `tsc --noEmit` and
production `vite build`.

## Phase 3 — two-stage scan architecture (speed redesign)

Scanning a 15GB–100GB+ drive used to hash every file, open every PDF,
run OpenCV on every image, and detect duplicates immediately during a
single blocking `POST /api/scan` call. On a real drive that's minutes to
hours before the user sees anything. This redesign splits scanning in two:

**Stage 1 — Quick Scan** (`services/quick_scan.py`, `POST /api/quick-scan`)
Walks the folder/drive and records only `name / extension / size / path /
created_at / modified_at`. No hashing, no PDF/image opening, no AI, no
duplicate detection. Runs as a background job (`GET /api/jobs/{id}` to
poll), and is incremental: a file whose size+modified-time haven't changed
since the last scan is left alone; files removed from disk since the last
scan of that root are removed from the DB.

Once it finishes, `GET /api/category-stats` returns per-category file
counts, storage used, and an estimated analysis time — this is what powers
the checkbox dashboard ("Images 12,000 files / ~480s estimated", etc).

**Stage 2 — Deep Analysis** (`services/deep_analysis.py`, `POST
/api/deep-scan {categories: [...]}`) Runs ONLY on the categories the user
checked, and only on files Stage 1 flagged as new/changed — unchanged files
keep their previous analysis (`analyzed_at` bookkeeping on `ScannedFile`).
Work is fanned out across a `ThreadPoolExecutor` (hashing, pypdf, OpenCV,
and zipfile all release the GIL for the bulk of their work). Duplicate
detection, near-duplicate image clustering, blur detection, PDF
classification, and archive analysis all happen here, scoped per category.
This is also a background job with `current_task` / `percent` /
`eta_seconds` progress you can poll.

`GET /api/recommendations?categories=Images,PDFs` scopes the rule-based
recommendation engine to just the categories that were actually analyzed.

All the existing Phase 1/2 endpoints (`/api/files`, `/api/duplicates`,
`/api/pdfs`, `/api/blurry-images`, etc.) are unchanged — they just return
empty/partial results for categories that haven't been deep-analyzed yet.
The original single-shot `POST /api/scan` (`services/scanner.py`) is left
in place for backward compatibility but the dashboard (`Overview.tsx`) now
drives the two-stage flow instead.

**Known trade-off:** job progress lives in a `scan_jobs` DB table but the
background threads themselves are in-process (`threading.Thread`, not a
task queue) — fine for a single local backend process, but won't
survive a server restart mid-scan or scale across multiple workers.



A real local file scanner and analyzer. Every feature below was tested
against actual files (real PDFs, real images, a real ZIP) before being
handed off — not just import-checked.

## Phase 1 (unchanged)

- Real filesystem scan (`os.walk`), SHA256 exact-duplicate detection,
  extension-based categorization, storage dashboard, delete-from-disk.

## Phase 2 — what's real

| Feature | How it works | Verified with |
|---|---|---|
| PDF metadata | `pypdf` — real page count, author, title | 3 test PDFs |
| PDF classification | Rule-based: filename + first-page keyword matching against Resume/Invoice/Certificate/Research Paper/Book/Notes. **Not a trained ML model.** Confidence badge = how many independent signals agreed. | Correctly tagged an invoice-shaped PDF as Invoice (1.0 confidence) and a resume-shaped PDF as Resume (1.0), left an unrelated PDF Unclassified (0.0) |
| Blur detection | OpenCV Laplacian variance (standard CV technique, deterministic, no training data) | Sharp test image scored 12,079; blurred version of the same image scored 7.2 |
| Near-duplicate images | Average-hash (aHash) perceptual hashing + Hamming-distance clustering — catches resized/recompressed copies that SHA256 misses | Correctly grouped a sharp image with its blurred variant |
| Screenshot detection | Rule-based: filename patterns + aspect-ratio heuristics | — |
| Archive analytics | `zipfile` stdlib for ZIP (full file listing + uncompressed size); optional `py7zr`/`rarfile` for 7Z/RAR if those system tools are present | Correctly read a 2-file ZIP's contents and size |
| Recommendation engine | Rule-based, fully explainable — each recommendation names its rule and exact file IDs, no black box | Generated correct recommendations from all of the above |

## Honest limitations (read before relying on this)

- **PDF/image "classification" is heuristic, not deep learning.** A resume
  with no matching keywords, or a PDF where text extraction fails (scanned
  image PDFs), will land in "Unclassified." This is the tradeoff for not
  needing labeled training data — it's a reasonable v1, not a claim of ML accuracy.
- **Blur detection scores flat/low-detail images as "blurry" too** — the
  Laplacian-variance technique measures edge density, so a screenshot of a
  solid-color UI can score similarly to an actually out-of-focus photo.
  Treat low scores as "worth a look," not gospel.
- **"Personal Photos vs Nature vs Animals" content classification is NOT
  implemented.** That needs a pretrained vision model (e.g. a CNN classifier)
  wired in — a real next step, but a bigger dependency than this pass covers.
- **"Unwanted File Detection" (Frequently/Rarely/Unused/Archive Candidate
  via ML) is NOT implemented** — same reason: needs either labeled usage
  data or a defensible rule you'd want reviewed first. The Recommendations
  page's "old files" rule (unmodified 180+ days) is a reasonable rule-based
  substitute, done transparently rather than dressed up as ML.
- **RAR/7Z** need `py7zr`/`rarfile` (in requirements.txt) — 7Z works out of
  the box; RAR needs the `unrar` system binary installed separately, which
  isn't in the Python install path. Without it, RAR files still show up
  with their file size, just not internal contents.

## Run it

**Backend**
```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8811
```

**Frontend** (separate terminal)
```bash
cd frontend
npm install
npm run dev
```

Scan a real folder from the Overview page, then check PDF Manager, Image
Manager, Archives, and Recommendations.

## API additions (Phase 2)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/pdfs?subcategory=Resume` | PDFs, optionally filtered by classification |
| GET | `/api/blurry-images` | images flagged blurry, sorted sharpest-first among blurry |
| GET | `/api/similar-images` | images grouped by perceptual near-duplicate |
| GET | `/api/archives` | ZIP/RAR/7Z with content analytics |
| GET | `/api/recommendations` | rule-based suggestions, each with exact file IDs |

## Structure

```
backend/
  services/scanner.py           walk + hash + dispatch to type analyzers
  services/pdf_analyzer.py      PyPDF2 metadata + rule-based classification
  services/image_analyzer.py    OpenCV blur + aHash + rule-based classification
  services/archive_analyzer.py  zipfile/py7zr/rarfile content analysis
  services/recommendations.py   rule-based recommendation engine

frontend/src/pages/
  PdfManager.tsx        classified PDF browser with confidence badges
  ImageManager.tsx       blurry / similar-group tabs, delete blurry
  Archives.tsx            archive content table
  Recommendations.tsx     actionable, explainable suggestions
```
