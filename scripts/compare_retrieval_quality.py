#!/usr/bin/env python3
"""
Retrieval Quality Comparison: RRF vs Interleaved

Shows actual retrieved documents for each query so you can manually evaluate quality.
Displays side-by-side comparison with document content previews.

Usage:
    python3 scripts/compare_retrieval_quality.py
"""

import sqlite3
import json
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass

DB_PATH = Path.home() / ".openclaw" / "memory" / "main.sqlite"

# 10 diverse test queries
TEST_QUERIES = [
    "memory workflow",
    "SQLite database",
    "session February 2026",
    "LLM request handling",
    "xiaohongshu project",
    "triangle DDS system",
    "regulation annotations",
    "Python script",
    "embedding cache",
    "user authentication",
]

@dataclass
class RetrievalResult:
    """Single retrieval result"""
    id: str
    path: str
    text: str
    bm25_score: float = 0.0
    vector_score: float = 0.0
    hybrid_score: float = 0.0
    rank: int = 0

def connect_db():
    """Connect to OpenClaw database"""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    return sqlite3.connect(str(DB_PATH))

# ============================================================================
# RRF Implementation
# ============================================================================

def search_fts5(conn, query: str, limit: int = 100) -> List[RetrievalResult]:
    """FTS5 keyword search with BM25 scoring"""
    cursor = conn.execute("""
        SELECT 
            id,
            path,
            text,
            bm25(chunks_fts) as bm25_score
        FROM chunks_fts
        WHERE chunks_fts MATCH ?
        ORDER BY bm25_score ASC
        LIMIT ?
    """, [query, limit])
    
    results = []
    for row in cursor:
        normalized_score = 1.0 / (1.0 + abs(row[3]))
        results.append(RetrievalResult(
            id=row[0],
            path=row[1],
            text=row[2],
            bm25_score=normalized_score
        ))
    return results

def search_vector_fallback(conn, limit: int = 100) -> List[RetrievalResult]:
    """Fallback vector search (simulated)"""
    cursor = conn.execute("""
        SELECT id, path, text
        FROM chunks
        ORDER BY updated_at DESC
        LIMIT ?
    """, [limit])
    
    results = []
    for i, row in enumerate(cursor):
        sim_score = 1.0 - (i / limit)
        results.append(RetrievalResult(
            id=row[0],
            path=row[1],
            text=row[2],
            vector_score=sim_score
        ))
    return results

def rrf_fusion(fts_results: List[RetrievalResult], 
               vec_results: List[RetrievalResult],
               vector_weight: float = 0.5,
               text_weight: float = 0.3) -> List[RetrievalResult]:
    """RRF-style weighted fusion"""
    by_id = {}
    
    for result in fts_results:
        by_id[result.id] = RetrievalResult(
            id=result.id,
            path=result.path,
            text=result.text,
            bm25_score=result.bm25_score,
            vector_score=0.0
        )
    
    for result in vec_results:
        if result.id in by_id:
            by_id[result.id].vector_score = result.vector_score
        else:
            by_id[result.id] = RetrievalResult(
                id=result.id,
                path=result.path,
                text=result.text,
                bm25_score=0.0,
                vector_score=result.vector_score
            )
    
    for doc_id, doc in by_id.items():
        doc.hybrid_score = (vector_weight * doc.vector_score + 
                           text_weight * doc.bm25_score)
    
    ranked = sorted(by_id.values(), key=lambda x: x.hybrid_score, reverse=True)
    
    for i, doc in enumerate(ranked):
        doc.rank = i + 1
    
    return ranked

def retrieve_rrf(conn, query: str, top_k: int = 10) -> List[RetrievalResult]:
    """RRF retrieval"""
    fts_results = search_fts5(conn, query, limit=100)
    vec_results = search_vector_fallback(conn, limit=100)
    merged = rrf_fusion(fts_results, vec_results)
    return merged[:top_k]

# ============================================================================
# Interleaved Implementation
# ============================================================================

class InterleavedRetriever:
    """Interleaved retrieval with early termination"""
    
    def __init__(self, conn, vector_weight: float = 0.5, text_weight: float = 0.3):
        self.conn = conn
        self.vector_weight = vector_weight
        self.text_weight = text_weight
    
    def retrieve(self, query: str, top_k: int = 10) -> List[RetrievalResult]:
        """Interleaved retrieval"""
        fts_cursor = self.conn.execute("""
            SELECT id, path, text, bm25(chunks_fts) as bm25_score
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY bm25_score ASC
        """, [query])
        
        vec_cursor = self.conn.execute("""
            SELECT id, path, text
            FROM chunks
            ORDER BY updated_at DESC
        """)
        
        by_id = {}
        candidates = []
        
        fts_exhausted = False
        vec_exhausted = False
        fts_count = 0
        vec_count = 0
        max_fetch = 100
        
        stable_count = 0
        stability_threshold = 10
        
        while (not fts_exhausted or not vec_exhausted) and (fts_count + vec_count) < max_fetch:
            prev_top_k = [r.id for r in sorted(candidates, key=lambda x: x.hybrid_score, reverse=True)[:top_k]]
            
            if not fts_exhausted:
                for _ in range(2):
                    row = fts_cursor.fetchone()
                    if row is None:
                        fts_exhausted = True
                        break
                    
                    doc_id = row[0]
                    bm25_norm = 1.0 / (1.0 + abs(row[3]))
                    
                    if doc_id not in by_id:
                        by_id[doc_id] = RetrievalResult(
                            id=doc_id,
                            path=row[1],
                            text=row[2],
                            bm25_score=bm25_norm,
                            vector_score=0.0
                        )
                    else:
                        by_id[doc_id].bm25_score = bm25_norm
                    
                    fts_count += 1
            
            if not vec_exhausted:
                row = vec_cursor.fetchone()
                if row is None:
                    vec_exhausted = True
                else:
                    doc_id = row[0]
                    vec_score = 1.0 - (vec_count / max_fetch)
                    
                    if doc_id not in by_id:
                        by_id[doc_id] = RetrievalResult(
                            id=doc_id,
                            path=row[1],
                            text=row[2],
                            bm25_score=0.0,
                            vector_score=vec_score
                        )
                    else:
                        by_id[doc_id].vector_score = vec_score
                    
                    vec_count += 1
            
            candidates = []
            for doc in by_id.values():
                doc.hybrid_score = (self.vector_weight * doc.vector_score + 
                                   self.text_weight * doc.bm25_score)
                candidates.append(doc)
            
            current_top_k = [r.id for r in sorted(candidates, key=lambda x: x.hybrid_score, reverse=True)[:top_k]]
            
            if current_top_k == prev_top_k:
                stable_count += 1
                if stable_count >= stability_threshold:
                    break
            else:
                stable_count = 0
        
        ranked = sorted(candidates, key=lambda x: x.hybrid_score, reverse=True)
        for i, doc in enumerate(ranked):
            doc.rank = i + 1
        
        return ranked[:top_k]

def retrieve_interleaved(conn, query: str, top_k: int = 10) -> List[RetrievalResult]:
    """Interleaved retrieval"""
    retriever = InterleavedRetriever(conn)
    return retriever.retrieve(query, top_k)

# ============================================================================
# Display Functions
# ============================================================================

def print_header(text: str):
    """Print section header"""
    print("\n" + "=" * 100)
    print(f"  {text}")
    print("=" * 100)

def print_query_header(query_num: int, query: str):
    """Print query header"""
    print(f"\n{'─' * 100}")
    print(f"Query #{query_num}: \"{query}\"")
    print('─' * 100)

def print_result(result: RetrievalResult, rank: int, method: str):
    """Print a single result with details"""
    print(f"\n[{method} Rank {rank}]")
    print(f"  Path:         {result.path}")
    print(f"  ID:           {result.id[:40]}...")
    print(f"  Hybrid Score: {result.hybrid_score:.4f} (BM25: {result.bm25_score:.4f}, Vector: {result.vector_score:.4f})")
    print(f"  Content Preview:")
    
    # Show first 200 chars of content
    preview = result.text[:200].replace('\n', ' ')
    print(f"    {preview}...")

def compare_results(rrf_results: List[RetrievalResult], 
                   interleaved_results: List[RetrievalResult]) -> Dict:
    """Compare two result sets"""
    rrf_ids = [r.id for r in rrf_results]
    interleaved_ids = [r.id for r in interleaved_results]
    
    overlap = len(set(rrf_ids) & set(interleaved_ids))
    overlap_pct = (overlap / len(rrf_ids)) * 100 if rrf_ids else 0
    
    only_rrf = set(rrf_ids) - set(interleaved_ids)
    only_interleaved = set(interleaved_ids) - set(rrf_ids)
    
    return {
        'overlap_count': overlap,
        'overlap_pct': overlap_pct,
        'only_rrf': list(only_rrf),
        'only_interleaved': list(only_interleaved),
        'top1_match': rrf_ids[0] == interleaved_ids[0] if rrf_ids and interleaved_ids else False
    }

def print_side_by_side_comparison(rrf_results: List[RetrievalResult], 
                                  interleaved_results: List[RetrievalResult],
                                  max_show: int = 10):
    """Print side-by-side comparison of results"""
    print("\n" + "┌" + "─" * 48 + "┬" + "─" * 48 + "┐")
    print("│" + " " * 18 + "RRF" + " " * 27 + "│" + " " * 14 + "Interleaved" + " " * 23 + "│")
    print("├" + "─" * 48 + "┼" + "─" * 48 + "┤")
    
    for i in range(max_show):
        rrf_result = rrf_results[i] if i < len(rrf_results) else None
        int_result = interleaved_results[i] if i < len(interleaved_results) else None
        
        # Rank and score
        rrf_text = f"#{i+1} Score: {rrf_result.hybrid_score:.4f}" if rrf_result else "—"
        int_text = f"#{i+1} Score: {int_result.hybrid_score:.4f}" if int_result else "—"
        print(f"│ {rrf_text:<46} │ {int_text:<46} │")
        
        # Path
        rrf_path = rrf_result.path[:44] if rrf_result else "—"
        int_path = int_result.path[:44] if int_result else "—"
        print(f"│ {rrf_path:<46} │ {int_path:<46} │")
        
        # Match indicator
        match = "✓ SAME" if (rrf_result and int_result and rrf_result.id == int_result.id) else "✗ DIFFERENT"
        match_color = match
        print(f"│ {match_color:<46} │ {'':46} │")
        
        if i < max_show - 1:
            print("├" + "─" * 48 + "┼" + "─" * 48 + "┤")
    
    print("└" + "─" * 48 + "┴" + "─" * 48 + "┘")

def main():
    print_header("🔍 Retrieval Quality Comparison: RRF vs Interleaved")
    print("\nThis report shows the actual retrieved documents for each query.")
    print("You can manually evaluate which method returns more relevant results.")
    
    # Connect to database
    try:
        conn = connect_db()
        print(f"\n✅ Connected to: {DB_PATH}")
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        return
    
    # Count chunks
    cursor = conn.execute("SELECT COUNT(*) FROM chunks")
    chunk_count = cursor.fetchone()[0]
    print(f"📊 Total chunks in database: {chunk_count}")
    print(f"📝 Test queries: {len(TEST_QUERIES)}")
    
    # Store all results for summary
    all_comparisons = []
    
    # Process each query
    for i, query in enumerate(TEST_QUERIES, 1):
        print_query_header(i, query)
        
        # Retrieve with both methods
        rrf_results = retrieve_rrf(conn, query, top_k=10)
        interleaved_results = retrieve_interleaved(conn, query, top_k=10)
        
        # Compare
        comparison = compare_results(rrf_results, interleaved_results)
        all_comparisons.append(comparison)
        
        # Print summary
        print(f"\n📊 Quick Stats:")
        print(f"  Overlap:      {comparison['overlap_count']}/10 ({comparison['overlap_pct']:.0f}%)")
        print(f"  Top-1 Match:  {'✅ Yes' if comparison['top1_match'] else '❌ No'}")
        print(f"  Only in RRF:  {len(comparison['only_rrf'])} documents")
        print(f"  Only in Interleaved: {len(comparison['only_interleaved'])} documents")
        
        # Side-by-side comparison
        print_side_by_side_comparison(rrf_results, interleaved_results, max_show=10)
        
        # Show detailed results for top 3
        print(f"\n📄 Detailed Top-3 Results:")
        
        for rank in range(min(3, len(rrf_results))):
            print_result(rrf_results[rank], rank + 1, "RRF")
        
        for rank in range(min(3, len(interleaved_results))):
            print_result(interleaved_results[rank], rank + 1, "Interleaved")
        
        # Highlight differences
        if not comparison['top1_match']:
            print(f"\n⚠️  TOP-1 MISMATCH:")
            print(f"  RRF Top-1:        {rrf_results[0].path if rrf_results else 'N/A'}")
            print(f"  Interleaved Top-1: {interleaved_results[0].path if interleaved_results else 'N/A'}")
        
        if comparison['only_rrf']:
            print(f"\n🔵 Documents ONLY in RRF (not in Interleaved top-10):")
            for doc_id in comparison['only_rrf'][:3]:
                doc = next((r for r in rrf_results if r.id == doc_id), None)
                if doc:
                    print(f"  - {doc.path[:60]}")
        
        if comparison['only_interleaved']:
            print(f"\n🟢 Documents ONLY in Interleaved (not in RRF top-10):")
            for doc_id in comparison['only_interleaved'][:3]:
                doc = next((r for r in interleaved_results if r.id == doc_id), None)
                if doc:
                    print(f"  - {doc.path[:60]}")
    
    # Overall summary
    print_header("📈 Overall Summary")
    
    avg_overlap = sum(c['overlap_pct'] for c in all_comparisons) / len(all_comparisons)
    top1_matches = sum(1 for c in all_comparisons if c['top1_match'])
    
    print(f"\nAcross {len(TEST_QUERIES)} queries:")
    print(f"  Average Overlap:     {avg_overlap:.1f}%")
    print(f"  Top-1 Match Rate:    {top1_matches}/{len(TEST_QUERIES)} ({top1_matches/len(TEST_QUERIES)*100:.0f}%)")
    print(f"  Perfect Matches:     {sum(1 for c in all_comparisons if c['overlap_pct'] == 100.0)}/{len(TEST_QUERIES)}")
    
    print("\n💡 Evaluation Guide:")
    print("  1. Check if top results are relevant to the query")
    print("  2. Compare which method ranks more relevant docs higher")
    print("  3. Look at documents unique to each method")
    print("  4. Consider if differences matter for your use case")
    
    # Save detailed results
    output_file = Path(__file__).parent.parent / "retrieval_quality_comparison.json"
    with open(output_file, 'w') as f:
        json.dump({
            'queries': TEST_QUERIES,
            'results': [
                {
                    'query': query,
                    'rrf': [{'id': r.id, 'path': r.path, 'score': r.hybrid_score, 'text': r.text[:200]} 
                           for r in retrieve_rrf(conn, query, 10)],
                    'interleaved': [{'id': r.id, 'path': r.path, 'score': r.hybrid_score, 'text': r.text[:200]} 
                                   for r in retrieve_interleaved(conn, query, 10)]
                }
                for query in TEST_QUERIES
            ]
        }, f, indent=2)
    
    print(f"\n💾 Detailed results saved to: {output_file}")
    
    conn.close()
    
    print("\n" + "=" * 100)
    print("✅ Quality comparison complete!")
    print("=" * 100)

if __name__ == "__main__":
    main()
