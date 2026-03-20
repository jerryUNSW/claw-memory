#!/usr/bin/env python3
"""
Quick Start: Benchmark OpenClaw's Current RRF Performance

This script measures the baseline performance of OpenClaw's current
hybrid retrieval system (RRF fusion) so you have a target to beat.

Usage:
    python3 scripts/benchmark_baseline.py
"""

import sqlite3
import time
from pathlib import Path
from typing import List, Dict, Tuple

DB_PATH = Path.home() / ".openclaw" / "memory" / "main.sqlite"

# Sample test queries based on your actual memory
TEST_QUERIES = [
    "memory workflow",
    "technical notes",
    "session February",
    "2026 March",
    "LLM request",
    "xiaohongshu",
    "triangle DDS",
    "regulation annotations",
]

def connect_db():
    """Connect to OpenClaw database"""
    if not DB_PATH.exists():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")
    return sqlite3.connect(str(DB_PATH))

def search_fts5(conn, query: str, limit: int = 100) -> List[Dict]:
    """Simulate OpenClaw's FTS5 search"""
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
        results.append({
            'id': row[0],
            'path': row[1],
            'text': row[2],
            'bm25_score': row[3],
            'text_score': 1.0 / (1.0 + abs(row[3]))  # Normalize BM25
        })
    return results

def search_vector_fallback(conn, limit: int = 100) -> List[Dict]:
    """
    Fallback vector search (without actual vector similarity)
    Just returns chunks to simulate the vector search step
    """
    cursor = conn.execute("""
        SELECT id, path, text
        FROM chunks
        ORDER BY updated_at DESC
        LIMIT ?
    """, [limit])
    
    results = []
    for i, row in enumerate(cursor):
        results.append({
            'id': row[0],
            'path': row[1],
            'text': row[2],
            'vector_score': 1.0 - (i / limit)  # Simulate decreasing similarity
        })
    return results

def rrf_merge(fts_results: List[Dict], vec_results: List[Dict], 
              k: int = 60, vector_weight: float = 0.5, 
              text_weight: float = 0.3) -> List[Dict]:
    """
    Simulate OpenClaw's RRF-style weighted fusion
    (from manager-CIjpkmRY.js lines 875-928)
    """
    by_id = {}
    
    # Merge FTS results
    for rank, result in enumerate(fts_results):
        by_id[result['id']] = {
            'id': result['id'],
            'path': result['path'],
            'text': result['text'],
            'text_score': result.get('text_score', 0),
            'vector_score': 0,
            'fts_rank': rank
        }
    
    # Merge vector results
    for rank, result in enumerate(vec_results):
        if result['id'] in by_id:
            by_id[result['id']]['vector_score'] = result.get('vector_score', 0)
            by_id[result['id']]['vec_rank'] = rank
        else:
            by_id[result['id']] = {
                'id': result['id'],
                'path': result['path'],
                'text': result['text'],
                'text_score': 0,
                'vector_score': result.get('vector_score', 0),
                'vec_rank': rank
            }
    
    # Compute hybrid scores
    for doc_id, doc in by_id.items():
        hybrid_score = (vector_weight * doc['vector_score'] + 
                       text_weight * doc['text_score'])
        doc['hybrid_score'] = hybrid_score
    
    # Sort by hybrid score
    ranked = sorted(by_id.values(), key=lambda x: x['hybrid_score'], reverse=True)
    return ranked

def benchmark_query(conn, query: str) -> Tuple[List[Dict], float]:
    """Run a single query and measure latency"""
    start = time.time()
    
    # Step 1: FTS5 search
    fts_results = search_fts5(conn, query, limit=100)
    
    # Step 2: Vector search (fallback without actual vectors)
    vec_results = search_vector_fallback(conn, limit=100)
    
    # Step 3: RRF merge
    merged = rrf_merge(fts_results, vec_results)
    
    latency = (time.time() - start) * 1000  # Convert to ms
    
    return merged[:10], latency

def main():
    print("="*60)
    print("🔬 OpenClaw RRF Baseline Benchmark")
    print("="*60)
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
    print()
    
    # Run benchmark
    print("🏃 Running benchmark queries...")
    print("-"*60)
    
    latencies = []
    results_summary = []
    
    for i, query in enumerate(TEST_QUERIES, 1):
        results, latency = benchmark_query(conn, query)
        latencies.append(latency)
        
        print(f"{i}. Query: '{query}'")
        print(f"   Latency: {latency:.2f}ms")
        print(f"   Results: {len(results)} documents")
        if results:
            print(f"   Top result: {results[0]['path'][:40]}")
        print()
        
        results_summary.append({
            'query': query,
            'latency': latency,
            'result_count': len(results)
        })
    
    # Summary statistics
    print("="*60)
    print("📈 Baseline Performance Summary")
    print("="*60)
    print()
    
    avg_latency = sum(latencies) / len(latencies)
    p50_latency = sorted(latencies)[len(latencies)//2]
    p95_latency = sorted(latencies)[int(len(latencies)*0.95)]
    max_latency = max(latencies)
    
    print(f"Average Latency:  {avg_latency:.2f}ms")
    print(f"P50 Latency:      {p50_latency:.2f}ms")
    print(f"P95 Latency:      {p95_latency:.2f}ms")
    print(f"Max Latency:      {max_latency:.2f}ms")
    print()
    
    print("🎯 Target for Unified Operator:")
    print(f"   - Latency: <{avg_latency * 0.6:.2f}ms (40% reduction)")
    print(f"   - P95: <{p95_latency * 0.6:.2f}ms")
    print()
    
    print("💡 Next Steps:")
    print("   1. Generate more test queries (target: 50-100)")
    print("   2. Add relevance labels (0-2 scale)")
    print("   3. Implement unified operator")
    print("   4. Compare performance")
    print()
    
    conn.close()
    
    print("="*60)
    print("✅ Baseline benchmark complete!")
    print("="*60)

if __name__ == "__main__":
    main()
