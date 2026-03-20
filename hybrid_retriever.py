"""
OpenClaw Hybrid Retrieval: Unified SQLite Virtual Table Prototype
==================================================================

This is a proof-of-concept implementation of the interleaved FTS5/vector
search operator described in the research proposal.

Phase 1 Goal: Demonstrate dual-cursor iteration with basic score fusion.
"""

import sqlite3
import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass
import time


@dataclass
class SearchResult:
    """Unified search result combining lexical and semantic scores."""
    doc_id: int
    content: str
    bm25_score: float
    vector_score: float
    hybrid_score: float
    metadata: dict
    timestamp: float


class HybridRetriever:
    """
    Interleaved retrieval engine that fuses FTS5 and vector search.
    
    This is the Python prototype. Production version will be implemented
    as a native SQLite extension in C for performance.
    """
    
    def __init__(
        self,
        db_path: str,
        alpha: float = 0.3,  # BM25 weight
        beta: float = 0.5,   # Vector weight
        gamma: float = 0.2,  # Temporal weight
        decay_lambda: float = 0.01
    ):
        self.conn = sqlite3.connect(db_path)
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.decay_lambda = decay_lambda
        
    def _temporal_decay(self, timestamp: float) -> float:
        """Calculate decay factor based on age."""
        age_days = (time.time() - timestamp) / 86400
        return np.exp(-self.decay_lambda * age_days)
    
    def _normalize_scores(self, scores: List[float]) -> List[float]:
        """Min-max normalization to [0, 1] range."""
        if not scores or max(scores) == min(scores):
            return [0.5] * len(scores)
        min_s, max_s = min(scores), max(scores)
        return [(s - min_s) / (max_s - min_s) for s in scores]
    
    def search_fts5(self, query: str, limit: int = 50) -> List[Tuple[int, float]]:
        """Execute FTS5 keyword search."""
        cursor = self.conn.execute("""
            SELECT rowid, rank 
            FROM memory_fts 
            WHERE memory_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))
        
        results = cursor.fetchall()
        # Convert FTS5 rank (negative) to positive score
        scores = [-r[1] for r in results]
        normalized = self._normalize_scores(scores)
        
        return [(r[0], normalized[i]) for i, r in enumerate(results)]
    
    def search_vector(
        self, 
        query_embedding: np.ndarray, 
        limit: int = 50
    ) -> List[Tuple[int, float]]:
        """Execute vector similarity search."""
        # Assuming sqlite-vec is loaded
        cursor = self.conn.execute("""
            SELECT rowid, distance
            FROM vec_memory
            WHERE embedding MATCH ?
            ORDER BY distance
            LIMIT ?
        """, (query_embedding.tobytes(), limit))
        
        results = cursor.fetchall()
        # Convert distance to similarity score
        scores = [1 - r[1] for r in results]
        normalized = self._normalize_scores(scores)
        
        return [(r[0], normalized[i]) for i, r in enumerate(results)]
    
    def hybrid_search(
        self,
        query_text: str,
        query_embedding: np.ndarray,
        top_k: int = 10,
        fts_limit: int = 50,
        vec_limit: int = 50
    ) -> List[SearchResult]:
        """
        Unified hybrid search with interleaved scoring.
        
        This is the core algorithm that will be ported to C.
        """
        # Step 1: Retrieve from both indexes
        fts_results = dict(self.search_fts5(query_text, fts_limit))
        vec_results = dict(self.search_vector(query_embedding, vec_limit))
        
        # Step 2: Find union of document IDs
        all_doc_ids = set(fts_results.keys()) | set(vec_results.keys())
        
        # Step 3: Fetch metadata for all candidates
        placeholders = ','.join('?' * len(all_doc_ids))
        cursor = self.conn.execute(f"""
            SELECT rowid, content, created_at, metadata
            FROM memory_core
            WHERE rowid IN ({placeholders})
        """, tuple(all_doc_ids))
        
        doc_metadata = {row[0]: row[1:] for row in cursor.fetchall()}
        
        # Step 4: Calculate hybrid scores
        scored_results = []
        for doc_id in all_doc_ids:
            bm25_score = fts_results.get(doc_id, 0.0)
            vector_score = vec_results.get(doc_id, 0.0)
            
            content, created_at, metadata = doc_metadata[doc_id]
            temporal_factor = self._temporal_decay(created_at)
            
            # Unified scoring function
            hybrid_score = (
                self.alpha * bm25_score +
                self.beta * vector_score +
                self.gamma * temporal_factor
            )
            
            scored_results.append(SearchResult(
                doc_id=doc_id,
                content=content,
                bm25_score=bm25_score,
                vector_score=vector_score,
                hybrid_score=hybrid_score,
                metadata=metadata,
                timestamp=created_at
            ))
        
        # Step 5: Sort by hybrid score and return top-k
        scored_results.sort(key=lambda x: x.hybrid_score, reverse=True)
        return scored_results[:top_k]
    
    def hybrid_search_optimized(
        self,
        query_text: str,
        query_embedding: np.ndarray,
        top_k: int = 10,
        early_termination: bool = True
    ) -> List[SearchResult]:
        """
        Optimized version with early termination.
        
        Uses a priority queue to interleave cursors and stop early
        when top-k results stabilize.
        """
        import heapq
        
        # Initialize dual cursors
        fts_cursor = self.conn.execute("""
            SELECT rowid, rank FROM memory_fts 
            WHERE memory_fts MATCH ?
            ORDER BY rank
        """, (query_text,))
        
        vec_cursor = self.conn.execute("""
            SELECT rowid, distance FROM vec_memory
            WHERE embedding MATCH ?
            ORDER BY distance
        """, (query_embedding.tobytes(),))
        
        # Priority queue: (-hybrid_score, doc_id, result)
        top_k_heap = []
        seen_docs = set()
        
        fts_batch = fts_cursor.fetchmany(10)
        vec_batch = vec_cursor.fetchmany(10)
        
        iterations = 0
        max_iterations = 100  # Safety limit
        
        while (fts_batch or vec_batch) and iterations < max_iterations:
            # Process FTS5 batch
            for rowid, rank in fts_batch:
                if rowid not in seen_docs:
                    seen_docs.add(rowid)
                    # Fetch full document
                    doc = self._fetch_document(rowid)
                    if doc:
                        heapq.heappush(top_k_heap, (-doc.hybrid_score, rowid, doc))
            
            # Process vector batch
            for rowid, distance in vec_batch:
                if rowid not in seen_docs:
                    seen_docs.add(rowid)
                    doc = self._fetch_document(rowid)
                    if doc:
                        heapq.heappush(top_k_heap, (-doc.hybrid_score, rowid, doc))
            
            # Early termination check
            if early_termination and len(top_k_heap) >= top_k * 3:
                # If we have 3x candidates, likely found the best
                break
            
            fts_batch = fts_cursor.fetchmany(10)
            vec_batch = vec_cursor.fetchmany(10)
            iterations += 1
        
        # Extract top-k results
        results = [heapq.heappop(top_k_heap)[2] for _ in range(min(top_k, len(top_k_heap)))]
        return results
    
    def _fetch_document(self, doc_id: int) -> Optional[SearchResult]:
        """Helper to fetch and score a single document."""
        cursor = self.conn.execute("""
            SELECT content, created_at, metadata
            FROM memory_core
            WHERE rowid = ?
        """, (doc_id,))
        
        row = cursor.fetchone()
        if not row:
            return None
        
        content, created_at, metadata = row
        temporal_factor = self._temporal_decay(created_at)
        
        # Note: In real implementation, we'd have the scores from cursors
        # This is simplified for the prototype
        return SearchResult(
            doc_id=doc_id,
            content=content,
            bm25_score=0.5,  # Placeholder
            vector_score=0.5,  # Placeholder
            hybrid_score=temporal_factor,
            metadata=metadata,
            timestamp=created_at
        )
    
    def explain_query_plan(self, query_text: str) -> dict:
        """
        Analyze and explain the query execution plan.
        Useful for debugging and optimization.
        """
        fts_plan = self.conn.execute(
            "EXPLAIN QUERY PLAN SELECT * FROM memory_fts WHERE memory_fts MATCH ?",
            (query_text,)
        ).fetchall()
        
        return {
            "fts5_plan": fts_plan,
            "estimated_fts_cost": len(query_text.split()),  # Rough estimate
            "estimated_vec_cost": 768,  # Embedding dimension
            "recommendation": "Use hybrid search for queries with both keywords and semantic intent"
        }


class NeurosymolicRanker:
    """
    Advanced ranking layer that applies symbolic rules to neural scores.
    
    This implements the "reasoning layer" described in the proposal.
    """
    
    def __init__(self, rules: Optional[List[dict]] = None):
        self.rules = rules or self._default_rules()
    
    def _default_rules(self) -> List[dict]:
        """Default symbolic ranking rules."""
        return [
            {
                "name": "trusted_source_boost",
                "condition": lambda doc: doc.metadata.get("source") == "TRUSTED",
                "boost": 1.5
            },
            {
                "name": "recent_memory_boost",
                "condition": lambda doc: (time.time() - doc.timestamp) < 7 * 86400,
                "boost": 1.3
            },
            {
                "name": "user_confirmed_boost",
                "condition": lambda doc: doc.metadata.get("user_confirmed") is True,
                "boost": 1.4
            },
            {
                "name": "deprecated_penalty",
                "condition": lambda doc: doc.metadata.get("deprecated") is True,
                "boost": 0.5
            }
        ]
    
    def rerank(self, results: List[SearchResult]) -> List[SearchResult]:
        """Apply symbolic rules to rerank results."""
        for result in results:
            boost_factor = 1.0
            
            for rule in self.rules:
                if rule["condition"](result):
                    boost_factor *= rule["boost"]
            
            result.hybrid_score *= boost_factor
        
        results.sort(key=lambda x: x.hybrid_score, reverse=True)
        return results


# Example usage and benchmarking
if __name__ == "__main__":
    # This would be run against a real OpenClaw database
    print("OpenClaw Hybrid Retrieval Prototype")
    print("=" * 50)
    print("\nThis prototype demonstrates:")
    print("1. Dual-cursor iteration (FTS5 + vector)")
    print("2. Unified scoring function")
    print("3. Temporal decay weighting")
    print("4. Neuro-symbolic reranking")
    print("\nNext step: Port to C as SQLite extension")
