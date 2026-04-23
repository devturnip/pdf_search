import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

PDFS_DIR = Path(os.environ.get("PDFS_DIR", BASE_DIR / "pdfs"))
DATA_DIR = Path(os.environ.get("DATA_DIR", BASE_DIR / "data"))
THUMBNAILS_DIR = DATA_DIR / "thumbnails"
INDEX_DIR = DATA_DIR / "index"

THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)
INDEX_DIR.mkdir(parents=True, exist_ok=True)

THUMBNAIL_WIDTH = 300
FULL_IMAGE_DPI = 150

MIN_TEXT_LENGTH_FOR_OCR_FALLBACK = 20

SEMANTIC_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
CLIP_MODEL = "sentence-transformers/clip-ViT-B-32"

TOP_K_DEFAULT = 20
TOP_K_IMAGE = 20
