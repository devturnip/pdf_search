import os
import threading
from pathlib import Path
from typing import List
from datetime import datetime

from fastapi import FastAPI, Request, UploadFile, File, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import FileResponse, JSONResponse
from PIL import Image
import io
import rapidfuzz

from app.config import THUMBNAILS_DIR, BASE_DIR, PDFS_DIR
from app.ingestion import IngestionPipeline
from app.index import SearchIndex
from app.models import TextSearchRequest, SearchResponse, PageResult, IndexStatus, PdfListResponse, PdfInfo, UploadResponse, DeleteResponse, HighlightBox

app = FastAPI(title="PDF Search")

# Serve static files (thumbnails, css, js)
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/data", StaticFiles(directory="data"), name="data")

templates = Jinja2Templates(directory="templates")

# Global state
pipeline = IngestionPipeline()
search_index = SearchIndex()
index_lock = threading.Lock()


def startup_indexing():
    pages = pipeline.ingest()
    loaded = search_index.load(pages)
    if not loaded or search_index.semantic_index is None or search_index.image_index is None:
        search_index.load_models()
        search_index.build(pages)
    print("[Startup] Indexing complete.")


def _get_highlights(page: dict, query: str, mode: str) -> List[HighlightBox]:
    """Return bounding boxes of words matching the query terms."""
    words = page.get("word_bboxes", [])
    if not words or mode not in ("exact", "fuzzy"):
        return []

    query_terms = [t for t in query.lower().split() if len(t) > 1]
    if not query_terms:
        return []

    highlights = []
    seen_boxes = set()

    for w in words:
        word_text = w.get("text", "").lower()
        for term in query_terms:
            matched = False
            if mode == "exact" and term in word_text:
                matched = True
            elif mode == "fuzzy" and rapidfuzz.fuzz.partial_ratio(term, word_text) > 80:
                matched = True

            if matched:
                box_key = (w["x0"], w["y0"], w["x1"], w["y1"])
                if box_key not in seen_boxes:
                    seen_boxes.add(box_key)
                    highlights.append(HighlightBox(
                        x0=w["x0"], y0=w["y0"],
                        x1=w["x1"], y1=w["y1"],
                        text=w.get("text", "")
                    ))
                break

    return highlights


@app.on_event("startup")
def on_startup():
    startup_indexing()


@app.get("/")
def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/api/status", response_model=IndexStatus)
def get_status():
    return IndexStatus(
        total_pdfs=len(pipeline.manifest.get("pdfs", {})),
        total_pages=len(pipeline.pages_data),
        indexed_at=pipeline.manifest.get("last_indexed"),
        ready=search_index.semantic_index is not None and search_index.image_index is not None,
    )


@app.post("/api/search/text", response_model=SearchResponse)
def search_text(req: TextSearchRequest):
    if not search_index.pages_data:
        return SearchResponse(results=[], total=0, mode=req.mode, query=req.query)

    results: List[PageResult] = []
    seen = set()

    if req.mode == "exact":
        matches = search_index.search_exact(req.query, top_k=req.top_k)
    elif req.mode == "fuzzy":
        matches = []
        query_lower = req.query.lower()
        for idx, page in enumerate(search_index.pages_data):
            text = page.get("text", "")
            score = rapidfuzz.fuzz.partial_ratio(query_lower, text.lower())
            if score > 50:
                matches.append((idx, float(score) / 100.0))
        matches.sort(key=lambda x: x[1], reverse=True)
        matches = matches[:req.top_k]
    elif req.mode == "semantic":
        matches = search_index.search_semantic(req.query, top_k=req.top_k)
    else:
        raise HTTPException(status_code=400, detail="Invalid search mode")

    for idx, score in matches:
        if idx in seen:
            continue
        seen.add(idx)
        page = search_index.pages_data[idx]
        text = page.get("text", "")
        snippet = text[:300].replace("\n", " ")
        highlights = _get_highlights(page, req.query, req.mode)
        results.append(PageResult(
            pdf_name=page["pdf_name"],
            page_num=page["page_num"],
            score=round(score, 4),
            text_snippet=snippet,
            thumbnail_url=f"/data/thumbnails/{page['pdf_name']}_{page['page_num']}.png",
            full_image_url=f"/data/thumbnails/{page['pdf_name']}_{page['page_num']}_full.png",
            highlights=highlights,
            page_width=page.get("page_width", 0),
            page_height=page.get("page_height", 0),
        ))

    return SearchResponse(results=results, total=len(results), mode=req.mode, query=req.query)


@app.post("/api/search/image", response_model=SearchResponse)
def search_image(file: UploadFile = File(...), top_k: int = 20):
    if not search_index.pages_data:
        return SearchResponse(results=[], total=0, mode="image")

    contents = file.file.read()
    try:
        img = Image.open(io.BytesIO(contents)).convert("RGB")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid image: {e}")

    matches = search_index.search_image(img, top_k=top_k)
    results: List[PageResult] = []
    seen = set()
    for idx, score in matches:
        if idx in seen:
            continue
        seen.add(idx)
        page = search_index.pages_data[idx]
        text = page.get("text", "")
        snippet = text[:300].replace("\n", " ")
        results.append(PageResult(
            pdf_name=page["pdf_name"],
            page_num=page["page_num"],
            score=round(score, 4),
            text_snippet=snippet,
            thumbnail_url=f"/data/thumbnails/{page['pdf_name']}_{page['page_num']}.png",
            full_image_url=f"/data/thumbnails/{page['pdf_name']}_{page['page_num']}_full.png",
            highlights=[],
            page_width=page.get("page_width", 0),
            page_height=page.get("page_height", 0),
        ))

    return SearchResponse(results=results, total=len(results), mode="image")


@app.get("/api/pdfs", response_model=PdfListResponse)
def list_pdfs():
    """List all PDFs in the system with indexed vs not-indexed status."""
    pdf_files = pipeline.get_pdf_files()
    indexed_names = set(pipeline.manifest.get("pdfs", {}).keys())
    pages_per_pdf = {}
    for p in pipeline.pages_data:
        pages_per_pdf[p["pdf_name"]] = pages_per_pdf.get(p["pdf_name"], 0) + 1

    pdfs: List[PdfInfo] = []
    for pdf_path in pdf_files:
        name = pdf_path.name
        pdfs.append(PdfInfo(
            name=name,
            indexed=name in indexed_names,
            pages=pages_per_pdf.get(name, 0),
            hash=pipeline.manifest.get("pdfs", {}).get(name),
            last_indexed=pipeline.manifest.get("last_indexed") if name in indexed_names else None,
        ))

    return PdfListResponse(pdfs=pdfs)


@app.get("/api/download/{pdf_name}")
def download_pdf(pdf_name: str):
    """Download a PDF file by name."""
    pdf_path = PDFS_DIR / pdf_name
    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(
        path=pdf_path,
        media_type="application/pdf",
        filename=pdf_name,
    )


@app.post("/api/upload", response_model=UploadResponse)
def upload_pdf(file: UploadFile = File(...)):
    """Upload a new PDF to the pdfs folder."""
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are allowed")

    safe_name = Path(file.filename).name
    dest_path = PDFS_DIR / safe_name

    # Prevent overwriting by appending a number if needed
    counter = 1
    original_dest = dest_path
    while dest_path.exists():
        stem = original_dest.stem
        suffix = original_dest.suffix
        dest_path = PDFS_DIR / f"{stem}_{counter}{suffix}"
        counter += 1

    try:
        with open(dest_path, "wb") as f:
            f.write(file.file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {e}")

    return UploadResponse(
        status="ok",
        filename=dest_path.name,
        message=f"Uploaded {dest_path.name}",
    )


@app.delete("/api/pdfs/{pdf_name}", response_model=DeleteResponse)
def delete_pdf(pdf_name: str):
    """Delete a PDF and all associated data, then rebuild indices."""
    global search_index

    pdf_path = PDFS_DIR / pdf_name
    if not pdf_path.exists() or not pdf_path.is_file():
        raise HTTPException(status_code=404, detail="PDF not found")

    with index_lock:
        # 1. Delete the PDF file
        pdf_path.unlink()

        # 2. Delete thumbnails and full images for this PDF
        prefix = pdf_name + "_"
        for img_file in THUMBNAILS_DIR.iterdir():
            if img_file.name.startswith(prefix) and img_file.suffix == ".png":
                img_file.unlink()

        # 3. Remove from pages_data and manifest
        pipeline.pages_data = [p for p in pipeline.pages_data if p["pdf_name"] != pdf_name]
        if pdf_name in pipeline.manifest.get("pdfs", {}):
            del pipeline.manifest["pdfs"][pdf_name]
        pipeline._save_pages_data()
        pipeline._save_manifest()

        # 4. Rebuild indices from remaining pages
        search_index = SearchIndex()
        search_index.load_models()
        search_index.build(pipeline.pages_data)

    return DeleteResponse(status="ok", message=f"Deleted {pdf_name}")


@app.post("/api/reindex")
def reindex():
    global pipeline, search_index
    with index_lock:
        pipeline = IngestionPipeline()
        pages = pipeline.ingest()
        search_index = SearchIndex()
        search_index.load_models()
        search_index.build(pages)
    return {"status": "ok", "total_pages": len(pages)}
