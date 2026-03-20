#!/usr/bin/env python3
"""
Benchmark on BEIR Dataset with Ground Truth Evaluation

This script:
1. Downloads a BEIR dataset
2. Converts it to OpenClaw SQLite format
3. Runs RRF vs Interleaved benchmark
4. Evaluates with ground truth (NDCG, Recall, MAP, MRR)
5. Generates comparison report

Usage:
    pip install beir
    python3 scripts/benchmark_beir.py --dataset nfcorpus
    
Available datasets:
    - nfcorpus (3.6K docs, 323 queries) - Small, good for testing
    - scifact (5K docs, 300 queries) - Small, scientific
    - fiqa (57K docs, 648 queries) - Medium, financial
    - trec-covid (171K docs, 50 queries) - Large, medical
"""

import argparse
import sqlite3
import time
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Tuple
from collections import defaultdict

# Import BEIR
try:
    from beir import util
    from beir.datasets.data_loader import GenericDataLoader
except ImportError:
    print("Error: BEIR not installed. Run: pip install beir")
    exit(1)

# Import your benchmark functions
import sys
sys.path.append(str(Path(__file__).parent))
from compare_rrf_vs_interleaved import (
    RetrievalResult, benchmark_rrf, benchmark_interleaved
)

# ============================================================================
# Dataset Setup
# ============================================================================

def download_beir_dataset(dataset_name: str, data_dir: str = "datasets") -> Tuple[Dict, Dict, Dict]:
    """Download and load BEIR dataset"""
    print(f"📥 Downloading BEIR dataset: {dataset_name}")
    
    url = f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{dataset_name}.zip"
    data_path = util.download_and_unzip(url, data_dir)
    
    print(f"📂 Loading dataset from: {data_path}")
    corpus, queries, qrels = GenericDataLoader(data_folder=data_path).load(split="test")
    
    print(f"✅ Loaded:")
    print(f"   - Documents: {len(corpus):,}")
    print(f"   - Queries: {len(queries):,}")
    print(f"   - Relevance judgments: {sum(len(v) for v in qrels.values()):,}")
    
    return corpus, queries, qrels

def create_openclaw_db(corpus: Dict, db_path: str):
    """Convert BEIR corpus to OpenClaw SQLite format"""
    print(f"\n🔨 Creating OpenClaw database: {db_path}")
    
    # Remove existing database
    if Path(db_path).exists():
        Path(db_path).unlink()
    
    conn = sqlite3.connect(db_path)
    
    # Create tables (OpenClaw schema)
    conn.execute("""
        CREATE TABLE chunks (
            id TEXT PRIMARY KEY,
            path TEXT,
            text TEXT,
            start_line INTEGER,
            end_line INTEGER,
            source TEXT,
            updated_at INTEGER
        )
    """)
    
    conn.execute("""
        CREATE VIRTUAL TABLE chunks_fts USING fts5(
            id, path, text,
            content='chunks',
            content_rowid='rowid'
        )
    """)
    
    # Insert documents
    print("📝 Inserting documents...")
    current_time = int(time.time())
    
    for i, (doc_id, doc) in enumerate(corpus.items()):
        # Combine title and text
        title = doc.get('title', '').strip()
        text = doc.get('text', '').strip()
        full_text = f"{title}\n\n{text}" if title else text
        
        conn.execute("""
            INSERT INTO chunks (id, path, text, start_line, end_line, source, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (doc_id, f"beir/{doc_id}", full_text, 0, 0, "beir", current_time - i))
        
        if (i + 1) % 1000 == 0:
            print(f"   Inserted {i + 1:,} documents...")
    
    # Build FTS5 index
    print("🔍 Building FTS5 index...")
    conn.execute("INSERT INTO chunks_fts SELECT id, path, text FROM chunks")
    
    conn.commit()
    conn.close()
    
    print(f"✅ Database created with {len(corpus):,} documents")

# ============================================================================
# Evaluation Metrics
# ============================================================================

def calculate_ndcg(retrieved_ids: List[str], relevant_docs: Dict[str, int], k: int = 10) -> float:
    """Calculate NDCG@k"""
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k]):
        relevance = relevant_docs.get(doc_id, 0)
        dcg += (2**relevance - 1) / np.log2(i + 2)
    
    # Ideal DCG
    ideal_relevances = sorted(relevant_docs.values(), reverse=True)[:k]
    idcg = sum((2**rel - 1) / np.log2(i + 2) for i, rel in enumerate(ideal_relevances))
    
    return dcg / idcg if idcg > 0 else 0.0

def calculate_recall(retrieved_ids: List[str], relevant_docs: Dict[str, int], k: int = 10) -> float:
    """Calculate Recall@k"""
    retrieved_set = set(retrieved_ids[:k])
    relevant_set = set(doc_id for doc_id, rel in relevant_docs.items() if rel > 0)
    
    if len(relevant_set) == 0:
        return 0.0
    
    return len(retrieved_set & relevant_set) / len(relevant_set)

def calculate_precision(retrieved_ids: List[str], relevant_docs: Dict[str, int], k: int = 10) -> float:
    """Calculate Precision@k"""
    retrieved_set = set(retrieved_ids[:k])
    relevant_set = set(doc_id for doc_id, rel in relevant_docs.items() if rel > 0)
    
    if len(retrieved_set) == 0:
        return 0.0
    
    return len(retrieved_set & relevant_set) / len(retrieved_set)

def calculate_map(retrieved_ids: List[str], relevant_docs: Dict[str, int], k: int = 10) -> float:
    """Calculate Average Precision@k"""
    relevant_set = set(doc_id for doc_id, rel in relevant_docs.items() if rel > 0)
    
    if len(relevant_set) == 0:
        return 0.0
    
    precisions = []
    num_relevant = 0
    
    for i, doc_id in enumerate(retrieved_ids[:k]):
        if doc_id in relevant_set:
            num_relevant += 1
            precisions.append(num_relevant / (i + 1))
    
    return sum(precisions) / len(relevant_set) if precisions else 0.0

def calculate_mrr(retrieved_ids: List[str], relevant_docs: Dict[str, int], k: int = 10) -> float:
    """Calculate Reciprocal Rank"""
    relevant_set = set(doc_id for doc_id, rel in relevant_docs.items() if rel > 0)
    
    for i, doc_id in enumerate(retrieved_ids[:k]):
        if doc_id in relevant_set:
            return 1.0 / (i + 1)
    
    return 0.0

# ============================================================================
# Benchmark Execution
# ============================================================================

def run_benchmark(db_path: str, queries: Dict, qrels: Dict, top_k: int = 10):
    """Run benchmark on BEIR dataset"""
    print(f"\n🏃 Running benchmark on {len(queries)} queries...")
    
    conn = sqlite3.connect(db_path)
    
    results = []
    rrf_metrics_all = defaultdict(list)
    int_metrics_all = defaultdict(list)
    
    for i, (query_id, query_text) in enumerate(queries.items(), 1):
        if i % 10 == 0:
            print(f"   Progress: {i}/{len(queries)} queries...")
        
        # Run both methods
        rrf_results, rrf_perf = benchmark_rrf(conn, query_text, top_k=top_k)
        int_results, int_perf = benchmark_interleaved(conn, query_text, top_k=top_k)
        
        # Extract IDs
        rrf_ids = [r.id for r in rrf_results]
        int_ids = [r.id for r in int_results]
        
        # Get ground truth for this query
        relevant_docs = qrels.get(query_id, {})
        
        # Calculate effectiveness metrics
        if relevant_docs:
            # RRF metrics
            rrf_metrics_all['ndcg'].append(calculate_ndcg(rrf_ids, relevant_docs, k=top_k))
            rrf_metrics_all['recall'].append(calculate_recall(rrf_ids, relevant_docs, k=top_k))
            rrf_metrics_all['precision'].append(calculate_precision(rrf_ids, relevant_docs, k=top_k))
            rrf_metrics_all['map'].append(calculate_map(rrf_ids, relevant_docs, k=top_k))
            rrf_metrics_all['mrr'].append(calculate_mrr(rrf_ids, relevant_docs, k=top_k))
            
            # Interleaved metrics
            int_metrics_all['ndcg'].append(calculate_ndcg(int_ids, relevant_docs, k=top_k))
            int_metrics_all['recall'].append(calculate_recall(int_ids, relevant_docs, k=top_k))
            int_metrics_all['precision'].append(calculate_precision(int_ids, relevant_docs, k=top_k))
            int_metrics_all['map'].append(calculate_map(int_ids, relevant_docs, k=top_k))
            int_metrics_all['mrr'].append(calculate_mrr(int_ids, relevant_docs, k=top_k))
        
        # Efficiency metrics
        rrf_metrics_all['latency'].append(rrf_perf.latency_ms)
        rrf_metrics_all['fetches'].append(rrf_perf.results_fetched)
        int_metrics_all['latency'].append(int_perf.latency_ms)
        int_metrics_all['fetches'].append(int_perf.results_fetched)
        
        # Overlap
        overlap = len(set(rrf_ids) & set(int_ids))
        rrf_metrics_all['overlap'].append(overlap / top_k * 100)
        
        results.append({
            'query_id': query_id,
            'query': query_text,
            'rrf_ids': rrf_ids,
            'int_ids': int_ids,
            'relevant_docs': relevant_docs
        })
    
    conn.close()
    
    return results, rrf_metrics_all, int_metrics_all

# ============================================================================
# Report Generation
# ============================================================================

def print_report(dataset_name: str, rrf_metrics: Dict, int_metrics: Dict, corpus_size: int):
    """Print comparison report"""
    print("\n" + "=" * 80)
    print(f"📊 BEIR Benchmark Results: {dataset_name}")
    print("=" * 80)
    
    print(f"\n📚 Dataset: {corpus_size:,} documents")
    print(f"📝 Queries: {len(rrf_metrics['latency'])} evaluated")
    
    # Effectiveness metrics
    print("\n🎯 Effectiveness Metrics:")
    print(f"  {'Metric':<15} {'RRF':<12} {'Interleaved':<12} {'Difference':<12}")
    print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*12}")
    
    for metric in ['ndcg', 'recall', 'precision', 'map', 'mrr']:
        if metric in rrf_metrics and rrf_metrics[metric]:
            rrf_avg = np.mean(rrf_metrics[metric])
            int_avg = np.mean(int_metrics[metric])
            diff = ((int_avg - rrf_avg) / rrf_avg * 100) if rrf_avg > 0 else 0
            
            print(f"  {metric.upper()+'@10':<15} {rrf_avg:>10.4f}  {int_avg:>10.4f}  {diff:>+10.1f}%")
    
    # Efficiency metrics
    print("\n⚡ Efficiency Metrics:")
    print(f"  {'Metric':<15} {'RRF':<12} {'Interleaved':<12} {'Improvement':<12}")
    print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*12}")
    
    rrf_latency = np.mean(rrf_metrics['latency'])
    int_latency = np.mean(int_metrics['latency'])
    speedup = rrf_latency / int_latency if int_latency > 0 else 0
    
    rrf_fetches = np.mean(rrf_metrics['fetches'])
    int_fetches = np.mean(int_metrics['fetches'])
    fetch_reduction = ((rrf_fetches - int_fetches) / rrf_fetches * 100) if rrf_fetches > 0 else 0
    
    print(f"  {'Avg Latency':<15} {rrf_latency:>9.2f}ms {int_latency:>9.2f}ms {speedup:>10.2f}x")
    print(f"  {'Avg Fetches':<15} {rrf_fetches:>10.1f}  {int_fetches:>10.1f}  {fetch_reduction:>+9.1f}%")
    
    # Overlap
    avg_overlap = np.mean(rrf_metrics['overlap'])
    print(f"  {'Overlap':<15} {'-':<12} {avg_overlap:>10.1f}%  {'-':<12}")
    
    # Summary
    print("\n💡 Summary:")
    print(f"  • Interleaved is {speedup:.1f}x faster")
    print(f"  • Fetches {fetch_reduction:.1f}% fewer documents")
    print(f"  • {avg_overlap:.1f}% document overlap")
    
    if 'ndcg' in rrf_metrics and rrf_metrics['ndcg']:
        ndcg_diff = ((np.mean(int_metrics['ndcg']) - np.mean(rrf_metrics['ndcg'])) / 
                     np.mean(rrf_metrics['ndcg']) * 100)
        print(f"  • NDCG@10: {ndcg_diff:+.1f}% vs RRF")
    
    print("\n" + "=" * 80)

def save_results(output_file: str, dataset_name: str, results: List, 
                rrf_metrics: Dict, int_metrics: Dict):
    """Save results to JSON"""
    output = {
        'dataset': dataset_name,
        'num_queries': len(results),
        'rrf_metrics': {k: [float(v) for v in vals] for k, vals in rrf_metrics.items()},
        'int_metrics': {k: [float(v) for v in vals] for k, vals in int_metrics.items()},
        'summary': {
            'rrf_ndcg': float(np.mean(rrf_metrics['ndcg'])) if rrf_metrics['ndcg'] else 0,
            'int_ndcg': float(np.mean(int_metrics['ndcg'])) if int_metrics['ndcg'] else 0,
            'rrf_latency': float(np.mean(rrf_metrics['latency'])),
            'int_latency': float(np.mean(int_metrics['latency'])),
            'speedup': float(np.mean(rrf_metrics['latency']) / np.mean(int_metrics['latency'])),
            'overlap': float(np.mean(rrf_metrics['overlap']))
        }
    }
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")

# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Benchmark on BEIR dataset")
    parser.add_argument('--dataset', type=str, default='nfcorpus',
                       help='BEIR dataset name (nfcorpus, scifact, fiqa, trec-covid)')
    parser.add_argument('--data-dir', type=str, default='datasets',
                       help='Directory to store datasets')
    parser.add_argument('--top-k', type=int, default=10,
                       help='Number of results to retrieve')
    parser.add_argument('--output', type=str, default=None,
                       help='Output JSON file (default: beir_{dataset}_results.json)')
    
    args = parser.parse_args()
    
    # Set output file
    if args.output is None:
        args.output = f"beir_{args.dataset}_results.json"
    
    print("=" * 80)
    print("🔬 BEIR Benchmark: RRF vs Interleaved Retrieval")
    print("=" * 80)
    
    # Step 1: Download dataset
    corpus, queries, qrels = download_beir_dataset(args.dataset, args.data_dir)
    
    # Step 2: Create OpenClaw database
    db_path = f"beir_{args.dataset}.sqlite"
    create_openclaw_db(corpus, db_path)
    
    # Step 3: Run benchmark
    results, rrf_metrics, int_metrics = run_benchmark(db_path, queries, qrels, args.top_k)
    
    # Step 4: Print report
    print_report(args.dataset, rrf_metrics, int_metrics, len(corpus))
    
    # Step 5: Save results
    save_results(args.output, args.dataset, results, rrf_metrics, int_metrics)
    
    print("\n✅ Benchmark complete!")

if __name__ == "__main__":
    main()
