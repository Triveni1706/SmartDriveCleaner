# 🚀 Smart Drive Cleaner & Organizer

<p align="center">
  <img src="https://img.shields.io/badge/React-18+-61DAFB?logo=react" />
  <img src="https://img.shields.io/badge/TypeScript-3178C6?logo=typescript" />
  <img src="https://img.shields.io/badge/FastAPI-009688?logo=fastapi" />
  <img src="https://img.shields.io/badge/Python-3776AB?logo=python" />
  <img src="https://img.shields.io/badge/SQLite-003B57?logo=sqlite" />
  <img src="https://img.shields.io/badge/PostgreSQL-336791?logo=postgresql" />
  <img src="https://img.shields.io/badge/Docker-2496ED?logo=docker" />
</p>

> **Smart Drive Cleaner & Organizer** is an AI-powered storage optimization and intelligent file management system that scans, analyzes, organizes, and cleans local drives efficiently. It combines real-time monitoring, two-stage scanning, duplicate detection, smart recommendations, PDF & image analysis, archive management, and safe recovery into one modern application.

---

# 🌐 Live Demo

[![Live Demo](https://img.shields.io/badge/Live-Demo-success?style=for-the-badge)](https://smart-drive-cleaner.vercel.app)

---

# ✨ Features

## 📂 Smart Drive Management

- Scan entire drives or selected folders
- High-speed Two-Stage Scan Architecture
- Incremental scanning
- Real-time filesystem monitoring
- Storage usage analytics
- Persistent indexed search

---

## 🔍 Intelligent File Analysis

### Duplicate Detection

- SHA256 exact duplicate detection
- Near-duplicate image detection using perceptual hashing
- Duplicate recommendations

### PDF Analysis

- Metadata extraction
- Resume detection
- Invoice detection
- Certificate detection
- Notes detection
- Research paper detection
- Confidence scoring

### Image Analysis

- Blur detection
- Screenshot detection
- Similar image clustering

### Archive Analysis

- ZIP analytics
- RAR analytics
- 7Z analytics
- ZIP backup detection

---

## 📁 Smart Organization

- Collection Manager
- File Explorer
- PDF Manager
- Image Manager
- Archive Manager
- Smart Search
- Persistent Search Database

---

## 🗑️ Cleanup & Recovery

- Safe Delete System
- Recovery Center
- Restore deleted files
- Empty folder detection
- Large file detection
- Old file recommendations
- ZIP backup recommendations
- Permanent delete

---

## 🤖 AI Recommendations

Rule-based intelligent recommendations including:

- Duplicate cleanup
- Large files
- Old unused files
- Empty folders
- ZIP backups
- Storage optimization
- Category-based recommendations

---

# 🚀 Phase-wise Implementation

---

# ✅ Phase 1

Core Storage Scanner

- Real filesystem scanning
- SHA256 duplicate detection
- File categorization
- Storage dashboard
- Delete files

---

# ✅ Phase 2

Advanced File Intelligence

### PDF Analyzer

- Metadata extraction
- Classification
- Confidence scoring

### Image Analyzer

- Blur detection
- Near duplicate detection
- Screenshot detection

### Archive Analyzer

- ZIP analysis
- RAR analysis
- 7Z analysis

### Recommendation Engine

- Explainable rule-based recommendations

---

# ✅ Phase 3

## High-Speed Two Stage Scan Architecture

### Stage 1 — Quick Scan

- Extremely fast filesystem scan
- Stores

  - filename
  - extension
  - size
  - path
  - timestamps

- Incremental scanning
- Background jobs
- Job progress tracking

### Stage 2 — Deep Analysis

Runs only on selected categories.

Includes

- Duplicate detection
- Image analysis
- PDF analysis
- Archive analysis
- Recommendations

Only new or modified files are processed.

---

# ✅ Phase 4

## Smart File Management

### Direct File Operations

- Open file
- Open folder
- Rename
- Move
- Copy
- Bulk operations

### Safe Delete System

Instead of permanently deleting files,

files are moved into

```
SmartDriveCleaner_Trash/
```

allowing recovery anytime.

### Recovery Center

- Restore files
- Restore multiple files
- Permanently delete
- Empty trash

### Collection Manager

- Create collections
- Rename collections
- Delete collections
- Add files
- Remove files
- Collection statistics

### Improved Recommendations

Added

- Large files (>100MB, >500MB, >1GB)
- Files not modified in 6 months
- Files not modified in 1 year
- Empty folders
- ZIP backup detection

---

# 🏗 System Architecture

```text
                     User
                       │
                       ▼
        React + TypeScript Frontend
                       │
                       ▼
               FastAPI Backend
                       │
      ┌────────────────────────────────────┐
      │                                    │
      │  Quick Scan Engine                 │
      │  Deep Analysis Engine              │
      │  Duplicate Detector                │
      │  PDF Analyzer                      │
      │  Image Analyzer                    │
      │  Archive Analyzer                  │
      │  Recommendation Engine             │
      │  File Operations                   │
      │  Recovery Manager                  │
      │  Collection Manager                │
      └────────────────────────────────────┘
                       │
                       ▼
          SQLite / PostgreSQL Database
                       │
                       ▼
             Local File System
```

---

# 🛠 Tech Stack

| Category | Technology |
|-----------|------------|
| Frontend | React.js |
| Language | TypeScript |
| Styling | Tailwind CSS |
| Animation | Framer Motion |
| Charts | Recharts |
| Backend | FastAPI |
| Language | Python |
| Database | SQLite / PostgreSQL |
| Image Processing | OpenCV |
| PDF Processing | PyPDF |
| Monitoring | Watchdog |
| Duplicate Detection | SHA256 Hashing |
| Search | Indexed Search |
| Containerization | Docker |

---

# 📂 Project Structure

```text
smart-drive-cleaner/
│
├── backend/
│   ├── api/
│   ├── database/
│   ├── models/
│   ├── services/
│   │     ├── scanner.py
│   │     ├── quick_scan.py
│   │     ├── deep_analysis.py
│   │     ├── pdf_analyzer.py
│   │     ├── image_analyzer.py
│   │     ├── archive_analyzer.py
│   │     ├── recommendations.py
│   │     ├── collections.py
│   │     └── file_ops.py
│   └── main.py
│
├── frontend/
│   ├── src/
│   ├── pages/
│   ├── components/
│   └── services/
│
├── docker-compose.yml
├── README.md
└── screenshots/
```

---

# ⚙ Installation

## Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8811
```

---

## Frontend

```bash
cd frontend
npm install
npm run dev
```

---

# 📊 API Highlights

| Method | Endpoint | Description |
|----------|----------|-------------|
| POST | `/api/quick-scan` | Quick filesystem scan |
| POST | `/api/deep-scan` | Deep category analysis |
| GET | `/api/jobs/{id}` | Scan progress |
| GET | `/api/pdfs` | PDF Manager |
| GET | `/api/blurry-images` | Blur detection |
| GET | `/api/similar-images` | Similar images |
| GET | `/api/archives` | Archive analytics |
| GET | `/api/recommendations` | Smart recommendations |
| GET | `/api/search` | Indexed search |
| GET | `/api/trash` | Recovery Center |
| GET | `/api/collections` | Collection Manager |

---

# 🚀 Highlights

- High-Speed Two Stage Scanning
- Incremental Analysis
- SHA256 Duplicate Detection
- Near Duplicate Image Detection
- Blur Detection
- PDF Classification
- Archive Analytics
- Smart Recommendation Engine
- Safe Delete System
- Recovery Center
- Collection Manager
- Persistent Search
- Real-Time Monitoring
- Docker Support
- PostgreSQL Support

---

# 🔮 Future Enhancements

- Google Drive Integration
- OneDrive Integration
- AI Chat Assistant
- Natural Language Search
- Face Recognition
- Object Recognition
- ML-Based Cleanup Prediction
- Automatic Cleanup Scheduler
- PDF Reports
- Multi-user Support
- Authentication & Roles

---

# 👩‍💻 Author

## Triveni Manjunath

**Bachelor of Engineering (Computer Science)**


---
