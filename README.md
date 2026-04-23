# PDF Search

A containerized web application for searching inside PDF documents. Supports text search (exact, fuzzy, semantic) and reverse image search across all pages.

Built with **FastAPI**, **Sentence Transformers**, **CLIP**, **FAISS**, **Tesseract OCR**, and a vanilla JavaScript frontend. Runs entirely offline.

---

## Features

| Feature | Description |
|---------|-------------|
| **Exact Search** | Keyword/substring match using an inverted index |
| **Fuzzy Search** | Typo-tolerant matching via RapidFuzz |
| **Semantic Search** | Meaning-based search using `all-MiniLM-L6-v2` embeddings + FAISS |
| **Image Search** | Upload an image to find visually similar pages using CLIP embeddings |
| **OCR Fallback** | Automatically runs Tesseract on scanned/image-heavy pages |
| **Incremental Re-index** | Only new, changed, or removed PDFs are reprocessed |
| **PDF Library** | View all PDFs, see indexed vs not-indexed status, download or delete files |
| **PDF Upload** | Upload new PDFs directly through the web UI |
| **PDF Delete** | Remove a PDF and all its associated data (thumbnails, embeddings) instantly |

---

## Architecture

```
┌─────────────┐      ┌──────────────┐      ┌─────────────────────┐
│   Browser   │──────▶│  FastAPI     │──────▶│  Ingestion Pipeline │
│  (Vanilla)  │◀──────│   Backend    │◀──────│  (PyMuPDF / OCR)    │
└─────────────┘      └──────────────┘      └─────────────────────┘
                             │                       │
                             ▼                       ▼
                      ┌──────────────┐      ┌─────────────────────┐
                      │   Search     │      │   FAISS Indices     │
                      │   Index      │      │  (Semantic + CLIP)  │
                      └──────────────┘      └─────────────────────┘
```

### Stack
- **Backend:** FastAPI (Python 3.12)
- **Frontend:** Vanilla HTML / CSS / JavaScript
- **Text Extraction:** PyMuPDF
- **OCR:** Tesseract (eng + deu)
- **Text Embeddings:** `sentence-transformers/all-MiniLM-L6-v2`
- **Image Embeddings:** `sentence-transformers/clip-ViT-B-32`
- **Vector Search:** FAISS CPU
- **Container:** Docker + Docker Compose

---

## Quick Start

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)

### 1. Clone & Place PDFs

```bash
git clone <repo-url>
cd pdf_search
```

Place your PDF files in the `pdfs/` directory:

```bash
mkdir -p pdfs
cp ~/Documents/*.pdf pdfs/
```

### 2. Build & Run

```bash
docker-compose up -d --build
```

The first startup will:
1. Extract text from all PDF pages
2. OCR any scanned pages
3. Generate thumbnails and full-page images
4. Build semantic text and CLIP image indices

This may take several minutes depending on the number and size of your PDFs.

### 3. Open the App

Navigate to **http://localhost:8000**

### 4. Stop

```bash
docker-compose down
```

---

## Usage

### Search Modes

1. **Exact** — finds pages containing all query words
2. **Fuzzy** — typo-tolerant; useful for OCR'd text with errors
3. **Semantic** — finds conceptually related pages even without keyword overlap
4. **Image** — upload an image to find visually similar PDF pages

Click any result thumbnail to open a full-resolution page viewer.

### Managing PDFs

Click **"Manage PDFs"** to open the library panel:
- **Upload** new PDFs via the "+ Upload PDF" button
- See which PDFs are indexed vs not yet indexed
- **Download** any PDF via the download button
- Click **"Re-index"** to incrementally process new/changed files

### Adding New PDFs

**Option A:** Drop files into the `pdfs/` folder on disk, then click **"Re-index"** in the UI.

**Option B:** Upload directly through the web UI's "+ Upload PDF" button, then click **"Re-index"**.

Re-indexing is incremental — existing PDFs that haven't changed are skipped.

---

## API Reference

All endpoints are served from `http://localhost:8000`.

### Search

```http
POST /api/search/text
Content-Type: application/json

{
  "query": "surgical instruments",
  "mode": "semantic",
  "top_k": 20
}
```

Modes: `exact`, `fuzzy`, `semantic`

```http
POST /api/search/image?top_k=20
Content-Type: multipart/form-data

file: <image_file>
```

### PDF Management

```http
GET /api/status
```

Returns total PDFs, pages, and index readiness.

```http
GET /api/pdfs
```

Returns all PDFs with indexed/not-indexed status and page counts.

```http
POST /api/upload
Content-Type: multipart/form-data

file: <pdf_file>
```

Uploads a new PDF to the `pdfs/` folder.

```http
GET /api/download/{pdf_name}
```

Downloads the specified PDF file.

```http
DELETE /api/pdfs/{pdf_name}
```

Deletes the PDF file, all associated thumbnails, and rebuilds the indices **in the background**. Returns a `task_id` for polling.

```http
POST /api/reindex
```

Triggers incremental re-indexing of all PDFs in the `pdfs/` folder **in the background**. Returns a `task_id` for polling.

```http
GET /api/tasks/{task_id}
```

Returns the status of a background task:

```json
{
  "id": "...",
  "type": "reindex",
  "status": "running",
  "message": "Running",
  "result": null,
  "error": null,
  "created_at": "...",
  "updated_at": "..."
}
```

Status values: `queued`, `running`, `completed`, `failed`.

---

## Project Structure

```
.
├── app/
│   ├── __init__.py
│   ├── main.py           # FastAPI routes
│   ├── tasks.py          # Background task manager
│   ├── ingestion.py      # PDF text extraction, OCR, thumbnail generation
│   ├── index.py          # FAISS semantic + CLIP index management
│   ├── models.py         # Pydantic request/response schemas
│   └── config.py         # Paths and constants
├── templates/
│   └── index.html        # Main UI
├── static/
│   ├── style.css         # App styles
│   └── app.js            # Frontend logic
├── pdfs/                 # Place PDFs here (mounted into container)
├── data/                 # Generated thumbnails + indices (persisted)
│   ├── thumbnails/
│   └── index/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── README.md
```

---

## Configuration

Edit `app/config.py` to tune behavior:

| Setting | Default | Description |
|---------|---------|-------------|
| `THUMBNAIL_WIDTH` | `300` | Width of result thumbnails in pixels |
| `FULL_IMAGE_DPI` | `150` | Resolution of full-page viewer images |
| `MIN_TEXT_LENGTH_FOR_OCR_FALLBACK` | `20` | If extracted text is shorter than this, run OCR |
| `SEMANTIC_MODEL` | `all-MiniLM-L6-v2` | Sentence transformer for semantic search |
| `CLIP_MODEL` | `clip-ViT-B-32` | CLIP model for image search |

Environment variables (set in `docker-compose.yml`):
- `PDFS_DIR` — path to PDF folder (default: `/app/pdfs`)
- `DATA_DIR` — path for thumbnails and indices (default: `/app/data`)

---

## Data Persistence

The `data/` directory is mounted as a Docker volume. Thumbnails, extracted page images, and FAISS indices are stored here and persist across container restarts. Subsequent starts will load indices from disk and only reprocess changed PDFs.

---

## Limitations

| Limitation | Details |
|------------|---------|
| **Single-machine only** | FAISS indices and ML models live in memory on one container. No horizontal scaling or distributed search. |
| **Memory-bound** | All text embeddings, image embeddings, and indices are held in RAM. Expect ~2–4 GB for ~1,000 pages; scales linearly. |
| **Synchronous indexing** | Re-indexing rebuilds FAISS indices in a background thread. The API no longer blocks, but only one indexing task runs at a time. |
| **No incremental FAISS updates** | Adding one new PDF triggers a full rebuild of both the semantic text and CLIP image FAISS indices. |
| **OCR quality varies** | Tesseract struggles with poor scans, handwritten text, complex multi-column layouts, or low-resolution images. Pages that required OCR do not have highlight boxes. |
| **Page-level only** | Search returns individual pages, not consolidated document-level results. There is no "open PDF at page N" feature. |
| **Brute-force fuzzy search** | Fuzzy mode scans every indexed page with RapidFuzz. It works fine for thousands of pages but will slow down at 10,000+ pages. |
| **No authentication** | The app has no user accounts or access control. Anyone with network access can upload, delete, or search all PDFs. |
| **Semantic model limits** | `all-MiniLM-L6-v2` is fast and small but less nuanced than larger models (e.g., `all-mpnet-base-v2` or GPT-based embeddings). |
| **CLIP image search limits** | Image similarity is based on high-level visual concepts, not fine-grained detail. It may miss small objects or precise text matches. |

---

## Notes

- **OCR Language:** Tesseract is configured with English (`eng`) and German (`deu`) language packs.
- **First Startup:** Initial indexing of large PDF catalogs (hundreds of pages) may take 5–15 minutes. The UI will show "Loading..." until ready.
- **Memory:** The app loads sentence-transformer and CLIP models into memory. Expect ~2–4 GB RAM usage depending on PDF count.
- **No External APIs:** All processing — OCR, embeddings, vector search — happens locally inside the container.

---

## License

MIT
