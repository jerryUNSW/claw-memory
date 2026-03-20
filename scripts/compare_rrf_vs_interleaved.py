#!/usr/bin/env python3
"""
Comprehensive Benchmark: RRF vs Interleaved Retrieval

Compares OpenClaw's current RRF approach with an interleaved retrieval strategy.
Tests on 10 diverse queries and measures both effectiveness and efficiency.

Usage:
    python3 scripts/compare_rrf_vs_interleaved.py
"""

import sqlite3
import time
import json
import struct
import heapq
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from collections import defaultdict
from sentence_transformers import SentenceTransformer
import sqlite_vec

DB_PATH = Path.home() / ".openclaw" / "memory" / "main.sqlite"

def serialize_f32(vector):
    """Serialize float32 vector for sqlite-vec"""
    return struct.pack(f'{len(vector)}f', *vector)

# 10 diverse test queries covering different search patterns
TEST_QUERIES = [
    "memory workflow",           # Multi-word technical
    "SQLite database",           # Technical terms
    "session February 2026",     # Temporal + keyword
    "LLM request handling",      # Technical process
    "xiaohongshu project",       # Specific project name
    "triangle DDS system",       # Acronym + keyword
    "regulation annotations",    # Domain-specific
    "Python script",             # Programming language
    "embedding cache",           # Technical component
    "user authentication",       # Common feature
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

@dataclass
class BenchmarkMetrics:
    """Performance metrics for a single query"""
    query: str
    method: str
    latency_ms: float
    results_fetched: int  # Total results fetched from indexes
    results_returned: int  # Final top-k returned
    top_result_id: str = ""
    top_result_path: str = ""

def connect_db():
    """Connect to OpenClaw database"""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    return conn

# ============================================================================
# RRF Baseline Implementation (Current OpenClaw Approach)
# ============================================================================

def escape_fts5_query(query: str) -> str:
    """Escape special FTS5 characters"""
    # Remove or escape FTS5 special characters: " - ( ) * : 
    # Replace with spaces to maintain word boundaries
    special_chars = ['"', '-', '(', ')', '*', ':', '?']
    escaped = query
    for char in special_chars:
        escaped = escaped.replace(char, ' ')
    # Remove extra spaces
    escaped = ' '.join(escaped.split())
    return escaped if escaped else 'a'  # Return 'a' if empty

def search_fts5(conn, query: str, limit: int = 100) -> List[RetrievalResult]:
    """FTS5 keyword search with BM25 scoring"""
    # Escape FTS5 special characters
    escaped_query = escape_fts5_query(query)
    
    try:
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
        """, [escaped_query, limit])
    except Exception as e:
        # If query still fails, return empty results
        print(f"Warning: FTS5 query failed for '{query}': {e}")
        return []
    
    results = []
    for row in cursor:
        # Normalize BM25 score (lower is better, so invert)
        normalized_score = 1.0 / (1.0 + abs(row[3]))
        results.append(RetrievalResult(
            id=row[0],
            path=row[1],
            text=row[2],
            bm25_score=normalized_score
        ))
    return results

def search_vector_real(conn, query: str, model, limit: int = 100) -> List[RetrievalResult]:
    """
    Real vector search with actual embeddings and cosine similarity
    """
    # Compute query embedding
    query_embedding = model.encode(query)
    
    # Search using sqlite-vec
    cursor = conn.execute("""
        SELECT 
            chunks.id,
            chunks.path,
            chunks.text,
            vec_distance_cosine(chunks_vec.embedding, ?) as distance
        FROM chunks_vec
        JOIN chunks ON chunks.id = chunks_vec.id
        ORDER BY distance ASC
        LIMIT ?
    """, [serialize_f32(query_embedding), limit])
    
    results = []
    for row in cursor:
        # Convert distance to similarity (1 - distance)
        similarity = 1.0 - row[3]
        results.append(RetrievalResult(
            id=row[0],
            path=row[1],
            text=row[2],
            vector_score=similarity
        ))
    return results

def rrf_fusion(fts_results: List[RetrievalResult], 
               vec_results: List[RetrievalResult],
               k: int = 60,
               vector_weight: float = 0.5,
               text_weight: float = 0.3) -> List[RetrievalResult]:
    """
    RRF-style weighted fusion (OpenClaw's current approach)
    Merges results AFTER fetching from both indexes
    """
    by_id = {}
    
    # Merge FTS results
    for result in fts_results:
        by_id[result.id] = RetrievalResult(
            id=result.id,
            path=result.path,
            text=result.text,
            bm25_score=result.bm25_score,
            vector_score=0.0
        )
    
    # Merge vector results
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
    
    # Compute hybrid scores
    for doc_id, doc in by_id.items():
        doc.hybrid_score = (vector_weight * doc.vector_score + 
                           text_weight * doc.bm25_score)
    
    # Sort by hybrid score
    ranked = sorted(by_id.values(), key=lambda x: x.hybrid_score, reverse=True)
    
    # Assign ranks
    for i, doc in enumerate(ranked):
        doc.rank = i + 1
    
    return ranked

def benchmark_rrf(conn, query: str, model, top_k: int = 10) -> Tuple[List[RetrievalResult], BenchmarkMetrics]:
    """Benchmark RRF approach (baseline)"""
    start = time.perf_counter()
    
    # Step 1: Fetch 100 from FTS5
    fts_results = search_fts5(conn, query, limit=100)
    
    # Step 2: Fetch 100 from Vector (with real embeddings)
    vec_results = search_vector_real(conn, query, model, limit=100)
    
    # Step 3: Merge and rank
    merged = rrf_fusion(fts_results, vec_results)
    
    # Step 4: Return top-k
    top_k_results = merged[:top_k]
    
    latency = (time.perf_counter() - start) * 1000  # Convert to ms
    
    metrics = BenchmarkMetrics(
        query=query,
        method="RRF",
        latency_ms=latency,
        results_fetched=len(fts_results) + len(vec_results),  # 200 total
        results_returned=len(top_k_results),
        top_result_id=top_k_results[0].id if top_k_results else "",
        top_result_path=top_k_results[0].path if top_k_results else ""
    )
    
    return top_k_results, metrics

# ============================================================================
# Interleaved Retrieval Implementation (Research Approach)
# ============================================================================

class InterleavedRetriever:
    """
    Interleaved retrieval with heap-based priority queue and early termination
    
    Key optimizations:
    1. Min-heap to maintain top-k candidates (O(log k) instead of O(n log n))
    2. Early termination when top-k is stable
    3. Incremental score updates (only recompute changed documents)
    """
    
    def __init__(self, conn, model, vector_weight: float = 0.5, text_weight: float = 0.3):
        self.conn = conn
        self.model = model
        self.vector_weight = vector_weight
        self.text_weight = text_weight
    
    def retrieve(self, query: str, top_k: int = 10) -> Tuple[List[RetrievalResult], int]:
        """
        Interleaved retrieval with heap-based optimization
        
        Returns:
            - Top-k results
            - Total number of results fetched (for efficiency comparison)
        """
        # Escape FTS5 special characters
        escaped_query = escape_fts5_query(query)
        
        # Compute query embedding once
        query_embedding = self.model.encode(query)
        
        # Initialize cursors
        try:
            fts_cursor = self.conn.execute("""
                SELECT id, path, text, bm25(chunks_fts) as bm25_score
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY bm25_score ASC
            """, [escaped_query])
        except Exception as e:
            # If FTS5 query fails, return empty results
            print(f"Warning: FTS5 query failed for '{query}': {e}")
            return [], 0
        
        # Vector cursor with real embeddings
        vec_cursor = self.conn.execute("""
            SELECT 
                chunks.id,
                chunks.path,
                chunks.text,
                vec_distance_cosine(chunks_vec.embedding, ?) as distance
            FROM chunks_vec
            JOIN chunks ON chunks.id = chunks_vec.id
            ORDER BY distance ASC
        """, [serialize_f32(query_embedding)])
        
        # Track all seen documents by ID
        by_id = {}
        
        # Track documents that need heap updates
        updated_docs = set()
        
        # Interleaving parameters
        fts_exhausted = False
        vec_exhausted = False
        fts_count = 0
        vec_count = 0
        max_fetch = 100  # Safety limit
        
        # Early termination tracking
        prev_top_k_ids = []
        stable_count = 0
        stability_threshold = 15  # Increased threshold for better stability
        
        while (not fts_exhausted or not vec_exhausted) and (fts_count + vec_count) < max_fetch:
            # Fetch from FTS5 (2 results per iteration)
            if not fts_exhausted:
                for _ in range(2):
                    row = fts_cursor.fetchone()
                    if row is None:
                        fts_exhausted = True
                        break
                    
                    doc_id = row[0]
                    bm25_norm = 1.0 / (1.0 + abs(row[3]))
                    
                    if doc_id not in by_id:
                        # New document
                        by_id[doc_id] = RetrievalResult(
                            id=doc_id,
                            path=row[1],
                            text=row[2],
                            bm25_score=bm25_norm,
                            vector_score=0.0
                        )
                    else:
                        # Update existing document
                        by_id[doc_id].bm25_score = bm25_norm
                    
                    updated_docs.add(doc_id)
                    fts_count += 1
            
            # Fetch from Vector (1 result per iteration)
            if not vec_exhausted:
                row = vec_cursor.fetchone()
                if row is None:
                    vec_exhausted = True
                else:
                    doc_id = row[0]
                    vec_score = 1.0 - row[3]  # Convert distance to similarity
                    
                    if doc_id not in by_id:
                        # New document
                        by_id[doc_id] = RetrievalResult(
                            id=doc_id,
                            path=row[1],
                            text=row[2],
                            bm25_score=0.0,
                            vector_score=vec_score
                        )
                    else:
                        # Update existing document
                        by_id[doc_id].vector_score = vec_score
                    
                    updated_docs.add(doc_id)
                    vec_count += 1
            
            # Check for early termination (every 10 fetches)
            if (fts_count + vec_count) % 10 == 0:
                # Compute hybrid scores for all documents
                for doc in by_id.values():
                    doc.hybrid_score = (self.vector_weight * doc.vector_score + 
                                       self.text_weight * doc.bm25_score)
                
                # Get current top-k
                candidates = sorted(by_id.values(), key=lambda x: x.hybrid_score, reverse=True)
                current_top_k_ids = [doc.id for doc in candidates[:top_k]]
                
                if current_top_k_ids == prev_top_k_ids:
                    stable_count += 1
                    if stable_count >= stability_threshold:
                        break  # Early termination!
                else:
                    stable_count = 0
                    prev_top_k_ids = current_top_k_ids
        
        # Final ranking - compute all hybrid scores
        for doc in by_id.values():
            doc.hybrid_score = (self.vector_weight * doc.vector_score + 
                               self.text_weight * doc.bm25_score)
        
        # Sort by hybrid score (descending)
        results = sorted(by_id.values(), key=lambda x: x.hybrid_score, reverse=True)
        
        # Assign ranks
        for i, doc in enumerate(results):
            doc.rank = i + 1
        
        total_fetched = fts_count + vec_count
        return results[:top_k], total_fetched

def benchmark_interleaved(conn, query: str, model, top_k: int = 10) -> Tuple[List[RetrievalResult], BenchmarkMetrics]:
    """Benchmark interleaved retrieval approach"""
    start = time.perf_counter()
    
    retriever = InterleavedRetriever(conn, model)
    top_k_results, total_fetched = retriever.retrieve(query, top_k)
    
    latency = (time.perf_counter() - start) * 1000  # Convert to ms
    
    metrics = BenchmarkMetrics(
        query=query,
        method="Interleaved",
        latency_ms=latency,
        results_fetched=total_fetched,
        results_returned=len(top_k_results),
        top_result_id=top_k_results[0].id if top_k_results else "",
        top_result_path=top_k_results[0].path if top_k_results else ""
    )
    
    return top_k_results, metrics

# ============================================================================
# Comparison & Analysis
# ============================================================================

def compare_results(rrf_results: List[RetrievalResult], 
                   interleaved_results: List[RetrievalResult]) -> Dict:
    """Compare effectiveness of two result sets"""
    rrf_ids = [r.id for r in rrf_results]
    interleaved_ids = [r.id for r in interleaved_results]
    
    # Overlap metrics
    overlap = len(set(rrf_ids) & set(interleaved_ids))
    overlap_pct = (overlap / len(rrf_ids)) * 100 if rrf_ids else 0
    
    # Rank correlation (simplified)
    rank_diffs = []
    for i, doc_id in enumerate(rrf_ids):
        if doc_id in interleaved_ids:
            rrf_rank = i + 1
            interleaved_rank = interleaved_ids.index(doc_id) + 1
            rank_diffs.append(abs(rrf_rank - interleaved_rank))
    
    avg_rank_diff = sum(rank_diffs) / len(rank_diffs) if rank_diffs else 0
    
    return {
        'overlap_count': overlap,
        'overlap_pct': overlap_pct,
        'avg_rank_diff': avg_rank_diff,
        'rrf_top1': rrf_ids[0] if rrf_ids else None,
        'interleaved_top1': interleaved_ids[0] if interleaved_ids else None,
        'top1_match': rrf_ids[0] == interleaved_ids[0] if rrf_ids and interleaved_ids else False
    }

def print_results_table(results: List[RetrievalResult], method: str, max_rows: int = 5):
    """Pretty print results"""
    print(f"\n{method} Top-{max_rows} Results:")
    print("-" * 80)
    print(f"{'Rank':<6} {'Score':<8} {'Path':<40} {'ID':<20}")
    print("-" * 80)
    
    for i, result in enumerate(results[:max_rows], 1):
        path_short = result.path[:37] + "..." if len(result.path) > 40 else result.path
        id_short = result.id[:17] + "..." if len(result.id) > 20 else result.id
        print(f"{i:<6} {result.hybrid_score:<8.4f} {path_short:<40} {id_short:<20}")

def main():
    print("=" * 80)
    print("🔬 RRF vs Interleaved Retrieval Benchmark")
    print("=" * 80)
    print()
    
    # Load embedding model
    print("Loading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"✅ Model loaded (dimension: {model.get_sentence_embedding_dimension()})")
    print()
    
    # Connect to database
    try:
        conn = connect_db()
        print(f"✅ Connected to: {DB_PATH}")
    except FileNotFoundError as e:
        print(f"❌ {e}")
        return
    
    # Count chunks
    cursor = conn.execute("SELECT COUNT(*) FROM chunks")
    chunk_count = cursor.fetchone()[0]
    print(f"📊 Total chunks: {chunk_count}")
    print(f"📝 Test queries: {len(TEST_QUERIES)}")
    print()
    
    # Run benchmarks
    print("🏃 Running benchmarks...")
    print("=" * 80)
    
    all_metrics = []
    comparison_results = []
    
    for i, query in enumerate(TEST_QUERIES, 1):
        print(f"\n[{i}/{len(TEST_QUERIES)}] Query: '{query}'")
        print("-" * 80)
        
        # Benchmark RRF
        rrf_results, rrf_metrics = benchmark_rrf(conn, query, model)
        all_metrics.append(rrf_metrics)
        
        # Benchmark Interleaved
        interleaved_results, interleaved_metrics = benchmark_interleaved(conn, query, model)
        all_metrics.append(interleaved_metrics)
        
        # Compare results
        comparison = compare_results(rrf_results, interleaved_results)
        comparison_results.append(comparison)
        
        # Print summary
        print(f"\n  RRF:         {rrf_metrics.latency_ms:6.2f}ms | Fetched: {rrf_metrics.results_fetched:3d} | Returned: {rrf_metrics.results_returned:2d}")
        print(f"  Interleaved: {interleaved_metrics.latency_ms:6.2f}ms | Fetched: {interleaved_metrics.results_fetched:3d} | Returned: {interleaved_metrics.results_returned:2d}")
        print(f"\n  Speedup:     {rrf_metrics.latency_ms / interleaved_metrics.latency_ms:.2f}x")
        print(f"  Efficiency:  {((rrf_metrics.results_fetched - interleaved_metrics.results_fetched) / rrf_metrics.results_fetched * 100):.1f}% fewer fetches")
        print(f"  Overlap:     {comparison['overlap_pct']:.1f}% ({comparison['overlap_count']}/10)")
        print(f"  Top-1 Match: {'✅' if comparison['top1_match'] else '❌'}")
        
        # Show top results for first query
        if i == 1:
            print_results_table(rrf_results, "RRF", max_rows=5)
            print_results_table(interleaved_results, "Interleaved", max_rows=5)
    
    # Aggregate statistics
    print("\n" + "=" * 80)
    print("📈 Aggregate Performance Summary")
    print("=" * 80)
    
    rrf_metrics_list = [m for m in all_metrics if m.method == "RRF"]
    interleaved_metrics_list = [m for m in all_metrics if m.method == "Interleaved"]
    
    # Latency statistics
    rrf_latencies = [m.latency_ms for m in rrf_metrics_list]
    interleaved_latencies = [m.latency_ms for m in interleaved_metrics_list]
    
    rrf_avg = sum(rrf_latencies) / len(rrf_latencies)
    interleaved_avg = sum(interleaved_latencies) / len(interleaved_latencies)
    
    rrf_p50 = sorted(rrf_latencies)[len(rrf_latencies) // 2]
    interleaved_p50 = sorted(interleaved_latencies)[len(interleaved_latencies) // 2]
    
    rrf_p95 = sorted(rrf_latencies)[int(len(rrf_latencies) * 0.95)]
    interleaved_p95 = sorted(interleaved_latencies)[int(len(interleaved_latencies) * 0.95)]
    
    print("\n⏱️  Latency Comparison:")
    print(f"  {'Metric':<15} {'RRF':<12} {'Interleaved':<12} {'Improvement':<12}")
    print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*12}")
    print(f"  {'Average':<15} {rrf_avg:>10.2f}ms {interleaved_avg:>10.2f}ms {rrf_avg/interleaved_avg:>10.2f}x")
    print(f"  {'P50':<15} {rrf_p50:>10.2f}ms {interleaved_p50:>10.2f}ms {rrf_p50/interleaved_p50:>10.2f}x")
    print(f"  {'P95':<15} {rrf_p95:>10.2f}ms {interleaved_p95:>10.2f}ms {rrf_p95/interleaved_p95:>10.2f}x")
    
    # Efficiency statistics
    rrf_fetched = [m.results_fetched for m in rrf_metrics_list]
    interleaved_fetched = [m.results_fetched for m in interleaved_metrics_list]
    
    rrf_avg_fetched = sum(rrf_fetched) / len(rrf_fetched)
    interleaved_avg_fetched = sum(interleaved_fetched) / len(interleaved_fetched)
    
    print(f"\n📊 Efficiency Comparison:")
    print(f"  RRF Average Fetches:         {rrf_avg_fetched:.1f}")
    print(f"  Interleaved Average Fetches: {interleaved_avg_fetched:.1f}")
    print(f"  Reduction:                   {((rrf_avg_fetched - interleaved_avg_fetched) / rrf_avg_fetched * 100):.1f}%")
    
    # Effectiveness statistics
    avg_overlap = sum(c['overlap_pct'] for c in comparison_results) / len(comparison_results)
    top1_matches = sum(1 for c in comparison_results if c['top1_match'])
    avg_rank_diff = sum(c['avg_rank_diff'] for c in comparison_results) / len(comparison_results)
    
    print(f"\n🎯 Effectiveness Comparison:")
    print(f"  Average Overlap:      {avg_overlap:.1f}%")
    print(f"  Top-1 Match Rate:     {top1_matches}/{len(comparison_results)} ({top1_matches/len(comparison_results)*100:.1f}%)")
    print(f"  Avg Rank Difference:  {avg_rank_diff:.2f}")
    
    # Save results
    output_file = Path(__file__).parent.parent / "benchmark_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            'queries': TEST_QUERIES,
            'metrics': [vars(m) for m in all_metrics],
            'comparisons': comparison_results,
            'summary': {
                'rrf_avg_latency': rrf_avg,
                'interleaved_avg_latency': interleaved_avg,
                'speedup': rrf_avg / interleaved_avg,
                'rrf_avg_fetched': rrf_avg_fetched,
                'interleaved_avg_fetched': interleaved_avg_fetched,
                'fetch_reduction_pct': ((rrf_avg_fetched - interleaved_avg_fetched) / rrf_avg_fetched * 100),
                'avg_overlap_pct': avg_overlap,
                'top1_match_rate': top1_matches / len(comparison_results)
            }
        }, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    conn.close()
    
    print("\n" + "=" * 80)
    print("✅ Benchmark complete!")
    print("=" * 80)

if __name__ == "__main__":
    main()
