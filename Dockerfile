FROM python:3.12-slim-bookworm

# Install system dependencies: Tesseract OCR, Poppler, build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-deu \
    libtesseract-dev \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY app/ ./app/
COPY static/ ./static/
COPY templates/ ./templates/

# Create directories for data
RUN mkdir -p /app/data/thumbnails /app/data/index

# Pre-download ML models so they are cached for the non-root user
ENV HF_HOME=/app/.cache/huggingface
ENV TRANSFORMERS_CACHE=/app/.cache/huggingface
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')" \
    && python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/clip-ViT-B-32')"

# Mount point for PDFs
VOLUME ["/app/pdfs"]

# Run as non-root user (UID 1000 matches common host user)
RUN groupadd -g 1000 appuser && useradd -u 1000 -g appuser appuser \
    && chown -R appuser:appuser /app

EXPOSE 8000

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
