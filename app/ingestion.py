import fitz  # PyMuPDF
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional
import os

from app.config import (
    PDFS_DIR,
    THUMBNAILS_DIR,
    INDEX_DIR,
    THUMBNAIL_WIDTH,
    MIN_TEXT_LENGTH_FOR_OCR_FALLBACK,
    FULL_IMAGE_DPI,
)


def get_pdf_hash(pdf_path: Path) -> str:
    """Return MD5 hash of file contents for change detection."""
    h = hashlib.md5()
    with open(pdf_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def extract_text_from_page(doc: fitz.Document, page_num: int) -> tuple:
    """Extract text, word bounding boxes, and page dimensions from a PDF page."""
    page = doc.load_page(page_num)
    text = page.get_text().strip()
    rect = page.rect
    words = page.get_text("words")
    word_bboxes = []
    for w in words:
        x0, y0, x1, y1, word_text, *_ = w
        word_bboxes.append({
            "text": word_text,
            "x0": round(x0, 2),
            "y0": round(y0, 2),
            "x1": round(x1, 2),
            "y1": round(y1, 2),
        })
    return text, word_bboxes, rect.width, rect.height


def ocr_page(pdf_path: Path, page_num: int) -> str:
    """OCR a specific page of a PDF using pdf2image + pytesseract."""
    images = convert_from_path(
        pdf_path,
        first_page=page_num + 1,
        last_page=page_num + 1,
        dpi=200,
    )
    if not images:
        return ""
    text = pytesseract.image_to_string(images[0], lang="eng+deu")
    return text.strip()


def render_page_image(doc: fitz.Document, page_num: int, max_width: int = THUMBNAIL_WIDTH) -> Image.Image:
    """Render a PDF page to a PIL Image."""
    page = doc.load_page(page_num)
    zoom = max_width / page.rect.width
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img


def render_full_page_image(doc: fitz.Document, page_num: int, dpi: int = FULL_IMAGE_DPI) -> Image.Image:
    """Render a full-resolution page image."""
    page = doc.load_page(page_num)
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return img


class IngestionPipeline:
    def __init__(self):
        self.manifest_path = INDEX_DIR / "manifest.json"
        self.pages_data_path = INDEX_DIR / "pages_data.json"
        self.manifest: Dict[str, Any] = self._load_manifest()
        self.pages_data: List[Dict[str, Any]] = self._load_pages_data()

    def _load_manifest(self) -> Dict[str, Any]:
        if self.manifest_path.exists():
            with open(self.manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"pdfs": {}, "last_indexed": None}

    def _load_pages_data(self) -> List[Dict[str, Any]]:
        if self.pages_data_path.exists():
            with open(self.pages_data_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _save_manifest(self):
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest, f, indent=2)

    def _save_pages_data(self):
        with open(self.pages_data_path, "w", encoding="utf-8") as f:
            json.dump(self.pages_data, f, indent=2)

    def get_pdf_files(self) -> List[Path]:
        """List all PDF files in the PDFs directory."""
        if not PDFS_DIR.exists():
            return []
        return sorted([p for p in PDFS_DIR.iterdir() if p.suffix.lower() == ".pdf"])

    def needs_reindex(self, pdf_files: List[Path]) -> bool:
        """Check if any PDF has changed or if new PDFs were added/removed."""
        current = {p.name: get_pdf_hash(p) for p in pdf_files}
        stored = self.manifest.get("pdfs", {})
        return current != stored

    def _process_pdf(self, pdf_path: Path) -> List[Dict[str, Any]]:
        """Process a single PDF and return its page records."""
        pdf_name = pdf_path.name
        pages = []
        print(f"[Ingestion] Processing {pdf_name} ...")

        doc = fitz.open(pdf_path)
        for page_num in range(len(doc)):
            text, word_bboxes, page_width, page_height = extract_text_from_page(doc, page_num)
            if len(text) < MIN_TEXT_LENGTH_FOR_OCR_FALLBACK:
                text = ocr_page(pdf_path, page_num)
                # OCR doesn't give us word positions; leave bboxes empty
                word_bboxes = []

            thumb_filename = f"{pdf_name}_{page_num}.png"
            thumb_path = THUMBNAILS_DIR / thumb_filename
            if not thumb_path.exists():
                img = render_page_image(doc, page_num)
                img.save(thumb_path, "PNG")

            full_filename = f"{pdf_name}_{page_num}_full.png"
            full_path = THUMBNAILS_DIR / full_filename
            if not full_path.exists():
                img = render_full_page_image(doc, page_num)
                img.save(full_path, "PNG")

            page_record = {
                "id": f"{pdf_name}_{page_num}",
                "pdf_name": pdf_name,
                "page_num": page_num,
                "text": text,
                "word_bboxes": word_bboxes,
                "page_width": round(page_width, 2),
                "page_height": round(page_height, 2),
                "thumbnail_path": str(thumb_path.relative_to(Path(__file__).resolve().parent.parent)),
                "full_image_path": str(full_path.relative_to(Path(__file__).resolve().parent.parent)),
            }
            pages.append(page_record)

        doc.close()
        return pages

    def ingest(self) -> List[Dict[str, Any]]:
        pdf_files = self.get_pdf_files()
        if not pdf_files:
            self.pages_data = []
            self.manifest = {"pdfs": {}, "last_indexed": None}
            self._save_manifest()
            self._save_pages_data()
            return []

        current_hashes = {p.name: get_pdf_hash(p) for p in pdf_files}
        stored_hashes = self.manifest.get("pdfs", {})

        if current_hashes == stored_hashes:
            return self.pages_data

        # Determine new, changed, removed
        new_names = {p.name for p in pdf_files} - set(stored_hashes.keys())
        removed_names = set(stored_hashes.keys()) - {p.name for p in pdf_files}
        changed_names = {
            p.name for p in pdf_files
            if p.name in stored_hashes and stored_hashes[p.name] != current_hashes[p.name]
        }

        to_process_names = new_names | changed_names

        # Keep pages for unchanged PDFs
        pages_data = [p for p in self.pages_data if p["pdf_name"] not in removed_names and p["pdf_name"] not in changed_names]

        # Process new and changed PDFs
        for pdf_path in pdf_files:
            if pdf_path.name in to_process_names:
                pages_data.extend(self._process_pdf(pdf_path))

        # Sort by pdf_name then page_num for consistency
        pages_data.sort(key=lambda p: (p["pdf_name"], p["page_num"]))

        self.pages_data = pages_data
        self.manifest = {
            "pdfs": current_hashes,
            "last_indexed": __import__("datetime").datetime.utcnow().isoformat()
        }
        self._save_manifest()
        self._save_pages_data()
        print(f"[Ingestion] Indexed {len(pages_data)} pages from {len(pdf_files)} PDFs. New: {len(new_names)}, Changed: {len(changed_names)}, Removed: {len(removed_names)}.")
        return pages_data
