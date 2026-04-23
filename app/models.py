from pydantic import BaseModel
from typing import Literal, List, Optional

class TextSearchRequest(BaseModel):
    query: str
    mode: Literal["exact", "fuzzy", "semantic"] = "exact"
    top_k: int = 20

class ImageSearchRequest(BaseModel):
    top_k: int = 20

class PageResult(BaseModel):
    pdf_name: str
    page_num: int
    score: float
    text_snippet: str
    thumbnail_url: str
    full_image_url: str

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
