"""
Vector Store implementation using FAISS with an in-memory normalized cosine search fallback.
Stores rich municipal document metadata for source citations and confidence estimation.
"""

import math
from typing import List, Dict, Any, Tuple, Optional
from src.schemas import SourceCitation

class VectorStore:
    def __init__(self, dimension: int = 384, similarity_threshold: float = 0.25):
        self.dimension = dimension
        self.similarity_threshold = similarity_threshold
        self.documents: List[Dict[str, Any]] = []
        self.embeddings: List[List[float]] = []
        self.faiss_index = None
        self._init_faiss()

    def _init_faiss(self):
        try:
            import faiss
            # FAISS IndexFlatIP computes inner product (equivalent to cosine similarity on L2-normalized vectors)
            self.faiss_index = faiss.IndexFlatIP(self.dimension)
        except Exception:
            self.faiss_index = None

    def add_documents(self, documents: List[Dict[str, Any]], embeddings: List[List[float]]):
        """
        Add normalized municipal documents and their vector embeddings.
        Each doc must have:
        - source_file
        - record_id
        - domain
        - title
        - text
        - original_record
        """
        if not documents or not embeddings or len(documents) != len(embeddings):
            raise ValueError("Documents and embeddings must be non-empty and of matching lengths.")

        start_idx = len(self.documents)
        self.documents.extend(documents)
        self.embeddings.extend(embeddings)

        if self.faiss_index is not None:
            try:
                import numpy as np
                matrix = np.array(embeddings, dtype=np.float32)
                # Normalize just in case
                norms = np.linalg.norm(matrix, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                matrix = matrix / norms
                self.faiss_index.add(matrix)
            except Exception:
                pass

    def similarity_search(self, query_embedding: List[float], top_k: int = 3) -> List[SourceCitation]:
        """
        Performs semantic similarity vector search. Returns top_k results exceeding similarity_threshold.
        """
        if not self.documents:
            return []

        # If FAISS is active and initialized
        if self.faiss_index is not None and self.faiss_index.ntotal == len(self.documents):
            try:
                import numpy as np
                q = np.array([query_embedding], dtype=np.float32)
                q_norm = np.linalg.norm(q)
                if q_norm > 0:
                    q = q / q_norm
                distances, indices = self.faiss_index.search(q, min(top_k * 2, len(self.documents)))

                results = []
                for score, idx in zip(distances[0], indices[0]):
                    if idx < 0 or idx >= len(self.documents):
                        continue
                    if score < self.similarity_threshold:
                        continue
                    doc = self.documents[idx]
                    results.append(
                        SourceCitation(
                            source_file=doc["source_file"],
                            record_id=doc["record_id"],
                            domain=doc["domain"],
                            title=doc["title"],
                            relevance_score=float(score),
                            text_snippet=doc["text"][:260] + ("..." if len(doc["text"]) > 260 else ""),
                            full_text=doc["text"],
                            metadata=doc.get("original_record", {})
                        )
                    )
                return results[:top_k]
            except Exception:
                pass

        # In-memory cosine similarity fallback
        scored: List[Tuple[float, Dict[str, Any]]] = []
        q_norm = math.sqrt(sum(x * x for x in query_embedding))
        if q_norm == 0:
            q_norm = 1.0

        for doc, emb in zip(self.documents, self.embeddings):
            dot = sum(a * b for a, b in zip(query_embedding, emb))
            e_norm = math.sqrt(sum(x * x for x in emb))
            if e_norm == 0:
                e_norm = 1.0
            cos_sim = dot / (q_norm * e_norm)

            if cos_sim >= self.similarity_threshold:
                scored.append((cos_sim, doc))

        # Sort descending by score
        scored.sort(key=lambda x: x[0], reverse=True)

        citations = []
        for score, doc in scored[:top_k]:
            citations.append(
                SourceCitation(
                    source_file=doc["source_file"],
                    record_id=doc["record_id"],
                    domain=doc["domain"],
                    title=doc["title"],
                    relevance_score=float(score),
                    text_snippet=doc["text"][:260] + ("..." if len(doc["text"]) > 260 else ""),
                    full_text=doc["text"],
                    metadata=doc.get("original_record", {})
                )
            )

        return citations
