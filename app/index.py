import json
import pickle
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import faiss
from sentence_transformers import SentenceTransformer
from PIL import Image

from app.config import INDEX_DIR, SEMANTIC_MODEL, CLIP_MODEL


class SearchIndex:
    def __init__(self):
        self.pages_data: List[Dict[str, Any]] = []
        self.id_to_idx: Dict[str, int] = {}

        # Exact text index: word -> set of idx
        self.inverted_index: Dict[str, set] = {}

        # Semantic text
        self.semantic_model: Optional[SentenceTransformer] = None
        self.semantic_index: Optional[faiss.Index] = None
        self.semantic_vectors: Optional[np.ndarray] = None

        # Image / CLIP
        self.clip_model: Optional[SentenceTransformer] = None
        self.image_index: Optional[faiss.Index] = None
        self.image_vectors: Optional[np.ndarray] = None

        self._semantic_index_path = INDEX_DIR / "semantic_faiss.index"
        self._image_index_path = INDEX_DIR / "image_faiss.index"
        self._semantic_vectors_path = INDEX_DIR / "semantic_vectors.npy"
        self._image_vectors_path = INDEX_DIR / "image_vectors.npy"
        self._inverted_index_path = INDEX_DIR / "inverted_index.pkl"

    def load_models(self):
        print("[Index] Loading semantic model ...")
        self.semantic_model = SentenceTransformer(SEMANTIC_MODEL)
        print("[Index] Loading CLIP model ...")
        self.clip_model = SentenceTransformer(CLIP_MODEL)

    def build(self, pages_data: List[Dict[str, Any]]) -> None:
        self.pages_data = pages_data
        self.id_to_idx = {p["id"]: i for i, p in enumerate(pages_data)}

        # Build exact inverted index
        self._build_inverted_index()

        # Build semantic index
        self._build_semantic_index()

        # Build image index
        self._build_image_index()

        self.save()

    def _build_inverted_index(self):
        print("[Index] Building inverted text index ...")
        self.inverted_index = {}
        for idx, page in enumerate(self.pages_data):
            text = page.get("text", "").lower()
            # Simple tokenization
            words = set(text.split())
            for word in words:
                # strip punctuation
                clean = "".join(c for c in word if c.isalnum())
                if clean:
                    self.inverted_index.setdefault(clean, set()).add(idx)
        print(f"[Index] Inverted index: {len(self.inverted_index)} terms.")

    def _build_semantic_index(self):
        if self.semantic_model is None:
            self.load_models()
        texts = [p.get("text", "") for p in self.pages_data]
        print(f"[Index] Encoding {len(texts)} text pages for semantic search ...")
        vectors = self.semantic_model.encode(texts, show_progress_bar=True, convert_to_numpy=True)
        vectors = vectors.astype("float32")
        # Normalize for cosine similarity
        faiss.normalize_L2(vectors)
        dim = vectors.shape[1]
        self.semantic_index = faiss.IndexFlatIP(dim)  # Inner product = cosine on normalized vectors
        self.semantic_index.add(vectors)
        self.semantic_vectors = vectors
        print(f"[Index] Semantic index built: {self.semantic_index.ntotal} vectors, dim={dim}.")

    def _build_image_index(self):
        if self.clip_model is None:
            self.load_models()
        image_paths = [p.get("thumbnail_path", "") for p in self.pages_data]
        images = []
        print(f"[Index] Loading {len(image_paths)} thumbnails for CLIP encoding ...")
        for path in image_paths:
            try:
                img = Image.open(path).convert("RGB")
                images.append(img)
            except Exception as e:
                print(f"[Index] Warning: could not load image {path}: {e}")
                images.append(Image.new("RGB", (224, 224), (128, 128, 128)))
        print(f"[Index] Encoding {len(images)} images with CLIP ...")
        vectors = self.clip_model.encode(images, show_progress_bar=True, convert_to_numpy=True)
        vectors = vectors.astype("float32")
        faiss.normalize_L2(vectors)
        dim = vectors.shape[1]
        self.image_index = faiss.IndexFlatIP(dim)
        self.image_index.add(vectors)
        self.image_vectors = vectors
        print(f"[Index] Image index built: {self.image_index.ntotal} vectors, dim={dim}.")

    def save(self):
        if self.inverted_index:
            with open(self._inverted_index_path, "wb") as f:
                pickle.dump(self.inverted_index, f)
        if self.semantic_index:
            faiss.write_index(self.semantic_index, str(self._semantic_index_path))
            np.save(self._semantic_vectors_path, self.semantic_vectors)
        if self.image_index:
            faiss.write_index(self.image_index, str(self._image_index_path))
            np.save(self._image_vectors_path, self.image_vectors)
        print("[Index] Indices saved to disk.")

    def load(self, pages_data: List[Dict[str, Any]]) -> bool:
        self.pages_data = pages_data
        self.id_to_idx = {p["id"]: i for i, p in enumerate(pages_data)}

        loaded = True
        if self._inverted_index_path.exists():
            with open(self._inverted_index_path, "rb") as f:
                self.inverted_index = pickle.load(f)
        else:
            loaded = False

        if self._semantic_index_path.exists():
            self.semantic_index = faiss.read_index(str(self._semantic_index_path))
            self.semantic_vectors = np.load(self._semantic_vectors_path)
        else:
            loaded = False

        if self._image_index_path.exists():
            self.image_index = faiss.read_index(str(self._image_index_path))
            self.image_vectors = np.load(self._image_vectors_path)
        else:
            loaded = False

        if loaded:
            print("[Index] All indices loaded from disk.")
        return loaded

    def search_exact(self, query: str, top_k: int = 20) -> List[Tuple[int, float]]:
        query = query.lower()
        words = ["".join(c for c in w if c.isalnum()) for w in query.split() if "".join(c for c in w if c.isalnum())]
        if not words:
            return []
        # Find pages that contain ALL query words
        candidate_sets = [self.inverted_index.get(w, set()) for w in words]
        if not candidate_sets or any(len(s) == 0 for s in candidate_sets):
            return []
        candidates = set.intersection(*candidate_sets)
        # Score by number of word matches (simple)
        scores = []
        for idx in candidates:
            text = self.pages_data[idx].get("text", "").lower()
            score = sum(1 for w in words if w in text)
            scores.append((idx, float(score)))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def search_semantic(self, query: str, top_k: int = 20) -> List[Tuple[int, float]]:
        if self.semantic_model is None or self.semantic_index is None:
            return []
        vec = self.semantic_model.encode([query], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(vec)
        scores, indices = self.semantic_index.search(vec, top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            results.append((int(idx), float(score)))
        return results

    def search_image(self, query_image: Image.Image, top_k: int = 20) -> List[Tuple[int, float]]:
        if self.clip_model is None or self.image_index is None:
            return []
        vec = self.clip_model.encode([query_image], convert_to_numpy=True).astype("float32")
        faiss.normalize_L2(vec)
        scores, indices = self.image_index.search(vec, top_k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            results.append((int(idx), float(score)))
        return results
