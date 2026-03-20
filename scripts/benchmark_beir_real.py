#!/usr/bin/env python3
"""
Benchmark on BEIR Dataset with Real Embeddings

This script uses the pre-computed embeddings from beir_nfcorpus.db
to benchmark RRF vs Interleaved retrieval with ground truth evaluation.

Usage:
    python3 scripts/benchmark_beir_real.py --dataset nfcorpus
"""

import argparse
import sqlite3
import time
import json
import struct
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict
from sentence_transformers import SentenceTransformer
import sqlite_vec

# Import benchmark functions
import sys
sys.path.append(str(Path(__file__).parent))
from compare_rrf_vs_interleaved import (
    RetrievalResult, escape_fts5_query, serialize_f32
)

# ============================================================================
# Real Vector Search Functions
# ============================================================================

def search_fts5(conn, query: str, limit: int = 100) -> List[RetrievalResult]:
    """FTS5 keyword search with BM25 scoring"""
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
        print(f"Warning: FTS5 query failed for '{query}': {e}")
        return []
    
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

def search_vector_real(conn, query: str, model, limit: int = 100) -> List[RetrievalResult]:
    """Real vector search with actual embeddings"""
    query_embedding = model.encode(query)
    
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

def benchmark_rrf(conn, query: str, model, top_k: int = 10) -> Tuple[List[RetrievalResult], float]:
    """Benchmark RRF with real embeddings"""
    start = time.perf_counter()
    
    fts_results = search_fts5(conn, query, limit=100)
    vec_results = search_vector_real(conn, query, model, limit=100)
    merged = rrf_fusion(fts_results, vec_results)
    top_k_results = merged[:top_k]
    
    latency = (time.perf_counter() - start) * 1000
    return top_k_results, latency

def benchmark_interleaved(conn, query: str, model, top_k: int = 10) -> Tuple[List[RetrievalResult], float]:
    """Benchmark interleaved with real embeddings and heap optimization"""
    from compare_rrf_vs_interleaved import InterleavedRetriever
    
    start = time.perf_counter()
    
    retriever = InterleavedRetriever(conn, model)
    top_k_results, total_fetched = retriever.retrieve(query, top_k)
    
    latency = (time.perf_counter() - start) * 1000
    return top_k_results, latency

# ============================================================================
# Evaluation Metrics
# ============================================================================

def calculate_ndcg(results: List[RetrievalResult], qrels: Dict[str, int], k: int = 10) -> float:
    """Calculate NDCG@k"""
    if not results or not qrels:
        return 0.0
    
    dcg = 0.0
    for i, result in enumerate(results[:k]):
        relevance = qrels.get(result.id, 0)
        dcg += (2**relevance - 1) / np.log2(i + 2)
    
    ideal_relevances = sorted(qrels.values(), reverse=True)[:k]
    idcg = sum((2**rel - 1) / np.log2(i + 2) for i, rel in enumerate(ideal_relevances))
    
    return dcg / idcg if idcg > 0 else 0.0

def calculate_recall(results: List[RetrievalResult], qrels: Dict[str, int], k: int = 10) -> float:
    """Calculate Recall@k"""
    if not qrels:
        return 0.0
    
    retrieved_relevant = sum(1 for r in results[:k] if r.id in qrels and qrels[r.id] > 0)
    total_relevant = sum(1 for rel in qrels.values() if rel > 0)
    
    return retrieved_relevant / total_relevant if total_relevant > 0 else 0.0

def calculate_precision(results: List[RetrievalResult], qrels: Dict[str, int], k: int = 10) -> float:
    """Calculate Precision@k"""
    if not results:
        return 0.0
    
    relevant = sum(1 for r in results[:k] if r.id in qrels and qrels[r.id] > 0)
    return relevant / min(k, len(results))

def calculate_map(results: List[RetrievalResult], qrels: Dict[str, int], k: int = 10) -> float:
    """Calculate MAP@k"""
    if not qrels:
        return 0.0
    
    relevant_count = 0
    precision_sum = 0.0
    
    for i, result in enumerate(results[:k]):
        if result.id in qrels and qrels[result.id] > 0:
            relevant_count += 1
            precision_sum += relevant_count / (i + 1)
    
    total_relevant = sum(1 for rel in qrels.values() if rel > 0)
    return precision_sum / total_relevant if total_relevant > 0 else 0.0

def calculate_mrr(results: List[RetrievalResult], qrels: Dict[str, int], k: int = 10) -> float:
    """Calculate MRR@k"""
    for i, result in enumerate(results[:k]):
        if result.id in qrels and qrels[result.id] > 0:
            return 1.0 / (i + 1)
    return 0.0

# ============================================================================
# Main Benchmark
# ============================================================================

def run_benchmark(db_path: str, dataset_name: str):
    """Run benchmark on BEIR dataset with real embeddings"""
    print("=" * 80)
    print(f"🔬 BEIR Benchmark with Real Embeddings: {dataset_name}")
    print("=" * 80)
    
    # Load model
    print("\nLoading embedding model...")
    model = SentenceTransformer('all-MiniLM-L6-v2')
    print(f"✅ Model loaded (dimension: {model.get_sentence_embedding_dimension()})")
    
    # Connect to database
    print(f"\nConnecting to database: {db_path}")
    conn = sqlite3.connect(db_path)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    
    # Load queries and qrels
    cursor = conn.execute("SELECT id, text FROM queries")
    queries = {row[0]: row[1] for row in cursor}
    
    cursor = conn.execute("SELECT query_id, doc_id, relevance FROM qrels")
    qrels = defaultdict(dict)
    for row in cursor:
        qrels[row[0]][row[1]] = row[2]
    
    print(f"✅ Loaded {len(queries)} queries with {len(qrels)} qrels")
    
    # Run benchmarks
    print("\n" + "=" * 80)
    print("Running benchmarks...")
    print("=" * 80)
    
    rrf_metrics = {'ndcg': [], 'recall': [], 'precision': [], 'map': [], 'mrr': [], 'latency': []}
    int_metrics = {'ndcg': [], 'recall': [], 'precision': [], 'map': [], 'mrr': [], 'latency': []}
    
    for i, (query_id, query_text) in enumerate(queries.items(), 1):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(queries)} queries...")
        
        query_qrels = qrels.get(query_id, {})
        if not query_qrels:
            continue
        
        # RRF
        try:
            rrf_results, rrf_latency = benchmark_rrf(conn, query_text, model, top_k=10)
            rrf_metrics['ndcg'].append(calculate_ndcg(rrf_results, query_qrels, k=10))
            rrf_metrics['recall'].append(calculate_recall(rrf_results, query_qrels, k=10))
            rrf_metrics['precision'].append(calculate_precision(rrf_results, query_qrels, k=10))
            rrf_metrics['map'].append(calculate_map(rrf_results, query_qrels, k=10))
            rrf_metrics['mrr'].append(calculate_mrr(rrf_results, query_qrels, k=10))
            rrf_metrics['latency'].append(rrf_latency)
        except Exception as e:
            print(f"Error with RRF for query {query_id}: {e}")
            continue
        
        # Interleaved
        try:
            int_results, int_latency = benchmark_interleaved(conn, query_text, model, top_k=10)
            int_metrics['ndcg'].append(calculate_ndcg(int_results, query_qrels, k=10))
            int_metrics['recall'].append(calculate_recall(int_results, query_qrels, k=10))
            int_metrics['precision'].append(calculate_precision(int_results, query_qrels, k=10))
            int_metrics['map'].append(calculate_map(int_results, query_qrels, k=10))
            int_metrics['mrr'].append(calculate_mrr(int_results, query_qrels, k=10))
            int_metrics['latency'].append(int_latency)
        except Exception as e:
            print(f"Error with Interleaved for query {query_id}: {e}")
            continue
    
    conn.close()
    
    # Print results
    print("\n" + "=" * 80)
    print("📊 RESULTS WITH REAL EMBEDDINGS")
    print("=" * 80)
    
    print(f"\n{'Metric':<15} {'RRF':<12} {'Interleaved':<12} {'Difference':<12}")
    print("-" * 60)
    
    for metric in ['ndcg', 'recall', 'precision', 'map', 'mrr']:
        rrf_avg = np.mean(rrf_metrics[metric]) if rrf_metrics[metric] else 0.0
        int_avg = np.mean(int_metrics[metric]) if int_metrics[metric] else 0.0
        diff = int_avg - rrf_avg
        print(f"{metric.upper():<15} {rrf_avg:<12.4f} {int_avg:<12.4f} {diff:+.4f}")
    
    rrf_latency = np.mean(rrf_metrics['latency']) if rrf_metrics['latency'] else 0.0
    int_latency = np.mean(int_metrics['latency']) if int_metrics['latency'] else 0.0
    speedup = rrf_latency / int_latency if int_latency > 0 else 0.0
    
    print(f"{'Latency (ms)':<15} {rrf_latency:<12.2f} {int_latency:<12.2f} {speedup:.2f}x")
    
    # Save results
    results = {
        'dataset': dataset_name,
        'num_queries': len(queries),
        'rrf_metrics': {k: float(np.mean(v)) if v else 0.0 for k, v in rrf_metrics.items()},
        'int_metrics': {k: float(np.mean(v)) if v else 0.0 for k, v in int_metrics.items()},
        'speedup': float(speedup)
    }
    
    output_file = f"beir_{dataset_name}_real_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description='Benchmark BEIR with real embeddings')
    parser.add_argument('--dataset', type=str, default='nfcorpus',
                       help='BEIR dataset name (default: nfcorpus)')
    args = parser.parse_args()
    
    db_path = f"beir_{args.dataset}.db"
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print(f"Please run: python3 scripts/compute_beir_embeddings.py --dataset {args.dataset}")
        return
    
    run_benchmark(db_path, args.dataset)

if __name__ == "__main__":
    main()
