# Plan: PDF Search Web Application

## 1. Goal
Build a containerized web application that enables users to search through a collection of PDFs.  
- **Phase 1 (Required):** Text/string search across PDF pages with multiple search modes.  
- **Phase 2 (Required):** Reverse image search—upload an image, find visually similar PDF pages ranked by relevance.  
- Users can click result thumbnails to view the full page content.

## 2. Constraints
| Constraint | Value |
|------------|-------|
| **Stack** | Python backend (FastAPI) + vanilla HTML/JS frontend; chosen for strong PDF/ML ecosystem |
| **Runtime** | Docker containerized, runs 100 % locally/offline |
| **Data** | `pdfs/` folder with 3 large PDFs (~40–50 MB each); medical/surgical catalog content |
| **PDF types** | Mixture of text-based and scanned-image pages |
| **Privacy** | No external APIs; all processing (OCR, embeddings, vector search) stays inside the container |
| **Scalability** | Architecture should support automatic ingestion when new PDFs are added to `pdfs/` |

## 3. Requirements
- Extract text from text-based PDF pages directly.
- Perform OCR on scanned/image-based PDF pages using Tesseract.
- Render each PDF page to a thumbnail image for UI display.
- Provide three toggle-able text search modes:
  1. **Exact** – substring/keyword match.
  2. **Fuzzy** – typo-tolerant match (e.g., via `thefuzz` or RapidFuzz).
  3. **Semantic** – vector similarity using local sentence-transformers.
- Provide image search using local CLIP embeddings (image-to-image similarity).
- Return ranked results showing page thumbnails, match scores, and metadata.
- Clicking a thumbnail opens a full-page viewer.
- Auto-detect new PDFs in `pdfs/` and rebuild/update indices accordingly.

## 4. High-Level Breakdown
1. **Project Bootstrap & Containerization**
   - Initialize Python project with FastAPI, dependencies.
   - Create `Dockerfile` with Tesseract OCR, Python, and ML libraries.
   - Set up `docker-compose.yml` mounting `pdfs/` as a volume.

2. **PDF Ingestion Pipeline**
   - Walk `pdfs/` and detect all `.pdf` files.
   - For each page:
     - Try direct text extraction (PyMuPDF / `fitz`).
     - Fallback to OCR (pdf2image → pytesseract) if little/no text found.
     - Render page to PNG thumbnail (PyMuPDF).
   - Store extracted text, OCR text, thumbnail path, and page metadata.

3. **Indexing & Embeddings**
   - **Text index:** Build an in-memory/per-file index mapping terms → pages for exact/fuzzy search.
   - **Semantic text index:** Compute text embeddings with `sentence-transformers/all-MiniLM-L6-v2`; store in FAISS or simple numpy index.
   - **Image index:** Compute image embeddings for every page thumbnail with local CLIP (`openai-clip` or `sentence-transformers` CLIP model); store in FAISS or numpy index.
   - Persist indices to disk so container restarts are fast.

4. **Search API (FastAPI)**
   - `POST /search/text` – accepts query string + mode (`exact`, `fuzzy`, `semantic`); returns ranked page results.
   - `POST /search/image` – accepts uploaded image file; computes CLIP embedding and queries image index; returns ranked similar pages.
   - `GET /page/{pdf_name}/{page_num}` – returns full-resolution page image.
   - `GET /thumbnail/{pdf_name}/{page_num}` – returns thumbnail.
   - `POST /reindex` – trigger manual re-indexing of `pdfs/` folder.

5. **Web UI**
   - Single-page vanilla HTML/JS app (served via FastAPI static files / Jinja2).
   - Search bar with toggle buttons for Exact / Fuzzy / Semantic / Image.
   - Image upload widget (visible when Image mode is selected).
   - Results grid: thumbnails + score + PDF name + page number.
   - Click thumbnail → modal/lightbox showing full page image.

6. **Auto-Watch / Re-indexing**
   - On startup, compare `pdfs/` contents against persisted index manifest.
   - If new, modified, or removed PDFs detected, automatically rebuild affected indices.
   - Expose manual re-index trigger via UI button and API endpoint.

7. **Testing & Validation**
   - Verify OCR quality on scanned pages.
   - Verify text search accuracy across all three modes.
   - Verify image search returns sensible rankings.
   - Test container build and runtime end-to-end.

## 5. Next Steps
1. Review and approve this plan.
2. Implement modules in order: Bootstrap → Ingestion → Indexing → API → UI → Auto-watch.
3. After each module, run quick validation tests.
4. Final integration test inside Docker.

## 6. TODO Checklist
- [x] Bootstrap Python project with FastAPI and dependency management (`requirements.txt`).
- [x] Create `Dockerfile` with Tesseract, Poppler, Python ML libraries.
- [x] Create `docker-compose.yml` mounting `pdfs/` volume and exposing the web port.
- [x] Build PDF ingestion pipeline: text extraction, OCR fallback, thumbnail generation.
- [x] Implement exact text search index and API endpoint.
- [x] Implement fuzzy text search index and API endpoint.
- [x] Implement semantic text search with sentence-transformers + vector index.
- [x] Implement image search with CLIP embeddings + vector index.
- [x] Persist indices to disk for fast container restarts.
- [x] Build web UI: search bar, mode toggles, image upload, results grid.
- [x] Add full-page viewer modal on thumbnail click.
- [x] Implement auto-detect on startup + manual re-index trigger (UI button + API endpoint).
- [x] Final integration test and README documentation.

## 7. Success Criteria
- [x] Container builds and starts successfully.
- [x] 2 PDFs ingested and indexed without errors (1 duplicate removed by user).
- [x] Exact, fuzzy, and semantic text searches return relevant pages.
- [x] Image search returns visually similar pages with sensible ranking.
- [x] UI is responsive and allows viewing full pages from thumbnails.
- [x] Adding a new PDF to `pdfs/` and restarting (or triggering re-index) updates the search results.
