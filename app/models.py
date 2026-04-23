from pydantic import BaseModel
from typing import Literal, List, Optional

class TextSearchRequest(BaseModel):
    query: str
    mode: Literal["exact", "fuzzy", "semantic"] = "exact"
    top_k: int = 20

class ImageSearchRequest(BaseModel):
    top_k: int = 20

class HighlightBox(BaseModel):
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

class PageResult(BaseModel):
    pdf_name: str
    page_num: int
    score: float
    text_snippet: str
    thumbnail_url: str
    full_image_url: str
    highlights: List[HighlightBox] = []
    page_width: float = 0
    page_height: float = 0

class SearchResponse(BaseModel):
    results: List[PageResult]
    total: int
    mode: str
    query: Optional[str] = None

class IndexStatus(BaseModel):
    total_pdfs: int
    total_pages: int
    indexed_at: Optional[str] = None
    ready: bool

class PdfInfo(BaseModel):
    name: str
    indexed: bool
    pages: int
    hash: Optional[str] = None
    last_indexed: Optional[str] = None

class PdfListResponse(BaseModel):
    pdfs: List[PdfInfo]

class UploadResponse(BaseModel):
    status: str
    filename: str
    message: str

class DeleteResponse(BaseModel):
    status: str
    message: str

class TaskResponse(BaseModel):
    status: str
    task_id: str
    message: str

class TaskStatus(BaseModel):
    id: str
    type: str
    status: str
    message: str
    result: Optional[dict] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
