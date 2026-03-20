#!/usr/bin/env python3
"""
Benchmark Cascaded Retrieval vs RRF

Compares:
1. RRF (baseline) - fetch 100 from each, merge
2. Cascaded - 3-stage pipeline (100 → 30 → 10)

Tests on BEIR NFCorpus with real embeddings.
"""

import argparse
import sqlite3
import json
import numpy as np
from pathlib import Path
from typing import Dict
from collections import defaultdict
from sentence_transformers import SentenceTransformer
import sqlite_vec

# Import our implementations
import sys
sys.path.append(str(Path(__file__).parent))
from cascaded_retrieval import benchmark_cascaded
from benchmark_beir_real import (
    benchmark_rrf,
    calculate_ndcg,
    calculate_recall,
    calculate_precision,
    calculate_map,
    calculate_mrr
)

def run_comparison(db_path: str, dataset_name: str):
    """Compare RRF vs Cascaded retrieval"""
    print("=" * 80)
    print(f"🔬 Cascaded vs RRF Benchmark: {dataset_name}")
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
    
    rrf_metrics = {
        'ndcg': [], 'recall': [], 'precision': [], 'map': [], 'mrr': [], 
        'latency': []
    }
    cascaded_metrics = {
        'ndcg': [], 'recall': [], 'precision': [], 'map': [], 'mrr': [], 
        'latency': [], 'stage1_ms': [], 'stage2_ms': [], 'stage3_ms': []
    }
    
    query_count = 0
    for i, (query_id, query_text) in enumerate(queries.items(), 1):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(queries)} queries...")
        
        query_qrels = qrels.get(query_id, )
        if not query_qrels:
            continue
        
        query_count += 1
        
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
        
        # Cascaded
        try:
            cascaded_results, timings = benchmark_cascaded(conn, query_text, model, top_k=10)
            cascaded_metrics['ndcg'].append(calculate_ndcg(cascaded_results, query_qrels, k=10))
            cascaded_metrics['recall'].append(calculate_recall(cascaded_results, query_qrels, k=10))
            cascaded_metrics['precision'].append(calculate_precision(cascaded_results, query_qrels, k=10))
            cascaded_metrics['map'].append(calculate_map(cascaded_results, query_qrels, k=10))
            cascaded_metrics['mrr'].append(calculate_mrr(cascaded_results, query_qrels, k=10))
            cascaded_metrics['latency'].append(timings['total_ms'])
            cascaded_metrics['stage1_ms'].append(timings['stage1_ms'])
            cascaded_metrics['stage2_ms'].append(timings['stage2_ms'])
            cascaded_metrics['stage3_ms'].append(timings['stage3_ms'])
        except Exception as e:
            print(f"Error with Cascaded for query {query_id}: {e}")
            continue
    
    conn.close()
    
    # Print results
    print("\n" + "=" * 80)
    print("📊 EFFECTIVENESS COMPARISON")
    print("=" * 80)
    
    print(f"\n{'Metric':<15} {'RRF':<12} {'Cascaded':<12} {'Difference':<12} {'% Change':<12}")
    print("-" * 75)
    
    for metric in ['ndcg', 'recall', 'precision', 'map', 'mrr']:
        rrf_avg = np.mean(rrf_metrics[metric]) if rrf_metrics[metric] else 0.0
        cas_avg = np.mean(cascaded_metrics[metric]) if cascaded_metrics[metric] else 0.0
        diff = cas_avg - rrf_avg
        pct_change = (diff / rrf_avg * 100) if rrf_avg > 0 else 0.0
        print(f"{metric.upper():<15} {rrf_avg:<12.4f} {cas_avg:<12.4f} {diff:+12.4f} {pct_change:+11.2f}%")
    
    print("\n" + "=" * 80)
    print("⚡ EFFICIENCY COMPARISON")
    print("=" * 80)
    
    rrf_latency = np.mean(rrf_metrics['latency']) if rrf_metrics['latency'] else 0.0
    cas_latency = np.mean(cascaded_metrics['latency']) if cascaded_metrics['latency'] else 0.0
    speedup = rrf_latency / cas_latency if cas_latency > 0 else 0.0
    
    print(f"\n{'Method':<15} {'Latency (ms)':<15} {'Speedup':<12}")
    print("-" * 45)
    print(f"{'RRF':<15} {rrf_latency:<15.2f} {'1.00x':<12}")
    print(f"{'Cascaded':<15} {cas_latency:<15.2f} {f'{speedup:.2f}x':<12}")
    
    # Stage breakdown for cascaded
    print("\n" + "=" * 80)
    print("🔍 CASCADED STAGE BREAKDOWN")
    print("=" * 80)
    
    stage1_avg = np.mean(cascaded_metrics['stage1_ms'])
    stage2_avg = np.mean(cascaded_metrics['stage2_ms'])
    stage3_avg = np.mean(cascaded_metrics['stage3_ms'])
    
    print(f"\n{'Stage':<20} {'Latency (ms)':<15} {'% of Total':<12}")
    print("-" * 50)
    print(f"{'Stage 1 (BM25)':<20} {stage1_avg:<15.2f} {stage1_avg/cas_latency*100:<11.1f}%")
    print(f"{'Stage 2 (Vector)':<20} {stage2_avg:<15.2f} {stage2_avg/cas_latency*100:<11.1f}%")
    print(f"{'Stage 3 (Hybrid)':<20} {stage3_avg:<15.2f} {stage3_avg/cas_latency*100:<11.1f}%")
    print(f"{'Total':<20} {cas_latency:<15.2f} {'100.0%':<12}")
    
    # Save results
    results = {
        'dataset': dataset_name,
        'num_queries': query_count,
        'rrf_metrics': {k: float(np.mean(v)) if v else 0.0 for k, v in rrf_metrics.items()},
        'cascaded_metrics': {k: float(np.mean(v)) if v else 0.0 for k, v in cascaded_metrics.items()},
        'speedup': float(speedup),
        'effectiveness_change': {
            'ndcg': float(np.mean(cascaded_metrics['ndcg']) - np.mean(rrf_metrics['ndcg'])),
            'recall': float(np.mean(cascaded_metrics['recall']) - np.mean(rrf_metrics['recall'])),
            'precision': float(np.mean(cascaded_metrics['precision']) - np.mean(rrf_metrics['precision'])),
        }
    }
    
    output_file = f"cascaded_vs_rrf_{dataset_name}.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📝 SUMMARY")
    print("=" * 80)
    
    ndcg_change = results['effectiveness_change']['ndcg']
    ndcg_pct = (ndcg_change / results['rrf_metrics']['ndcg'] * 100) if results['rrf_metrics']['ndcg'] > 0 else 0
    
    print(f"\n✅ Cascaded retrieval is {speedup:.2f}x faster than RRF")
    print(f"   - RRF: {rrf_latency:.2f}ms")
    print(f"   - Cascaded: {cas_latency:.2f}ms")
    print(f"\n📊 Effectiveness change: {ndcg_change:+.4f} NDCG ({ndcg_pct:+.2f}%)")
    print(f"   - RRF NDCG: {results['rrf_metrics']['ndcg']:.4f}")
    print(f"   - Cascaded NDCG: {results['cascaded_metrics']['ndcg']:.4f}")
    
    if speedup > 1.5 and abs(ndcg_change) < 0.02:
        print(f"\n🎉 SUCCESS! Cascaded is significantly faster with minimal quality loss!")
    elif speedup > 1.0:
        print(f"\n✅ Good! Cascaded is faster, but speedup is modest.")
    else:
        print(f"\n⚠️  Warning: Cascaded is not faster than RRF.")
    
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description='Benchmark Cascaded vs RRF')
    parser.add_argument('--dataset', type=str, default='nfcorpus',
                       help='BEIR dataset name (default: nfcorpus)')
    args = parser.parse_args()
    
    db_path = f"beir_{args.dataset}.db"
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        print(f"Please run: python3 scripts/compute_beir_embeddings.py --dataset {args.dataset}")
        return
    
    run_comparison(db_path, args.dataset)

if __name__ == "__main__":
    main()
