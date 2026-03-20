#!/usr/bin/env python3
"""
Fast ColBERT Implementation - Two-Stage Retrieval

Stage 1: BM25 filtering (top-100)
Stage 2: ColBERT-style reranking with token-level embeddings

This tests if ColBERT-style late interaction is actually better than
our cascaded approach.
"""

import sqlite3
import time
import json
import numpy as np
import torch
from pathlib import Path
from typing import List, Dict, Tuple
from dataclasses import dataclass
from collections import defaultdict
from transformers import AutoTokenizer, AutoModel

import sys
sys.path.append(str(Path(__file__).parent))
from cascaded_retrieval import escape_fts5_query, RetrievalResult

@dataclass
class ColBERTResult:
    id: str
    path: str
    text: str
    bm25_score: float = 0.0
    colbert_score: float = 0.0
    rank: int = 0

class FastColBERT:
    """
    Fast ColBERT using two-stage retrieval:
    1. BM25 gets top-100 candidates (fast)
    2. ColBERT reranks to top-10 (accurate)
    """
    
    def __init__(self, model_name='bert-base-uncased'):
        print(f"Loading model: {model_name}...")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModel.from_pretrained(model_name)
        self.model.eval()
        
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)
        print(f"Using device: {self.device}")
    
    def encode_text(self, text: str, max_length: int = 128) -> torch.Tensor:
        """Encode text to token-level embeddings"""
        inputs = self.tokenizer(
            text,
            max_length=max_length,
            truncation=True,
            padding='max_length',
            return_tensors='pt'
        )
        
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            embeddings = outputs.last_hidden_state[0]  # [seq_len, hidden_dim]
        
        return embeddings.cpu()
    
    def maxsim_score(self, query_emb: torch.Tensor, doc_emb: torch.Tensor) -> float:
        """
        ColBERT's MaxSim: for each query token, find max similarity with any doc token
        """
        # Normalize embeddings
        query_norm = torch.nn.functional.normalize(query_emb, dim=1)
        doc_norm = torch.nn.functional.normalize(doc_emb, dim=1)
        
        # Compute similarity matrix: [query_tokens, doc_tokens]
        similarity_matrix = torch.matmul(query_norm, doc_norm.T)
        
        # For each query token, take max similarity
        max_sims = similarity_matrix.max(dim=1)[0]
        
        # Sum across query tokens
        score = max_sims.sum().item()
        
        return score
    
    def search(self, conn, query: str, top_k: int = 10, stage1_size: int = 100) -> Tuple[List[ColBERTResult], dict]:
        """
        Two-stage search:
        1. BM25 filtering
        2. ColBERT reranking
        """
        timings = {}
        
        # Stage 1: BM25 filtering
        stage1_start = time.perf_counter()
        candidates = self._stage1_bm25(conn, query, stage1_size)
        timings['stage1_ms'] = (time.perf_counter() - stage1_start) * 1000
        
        if not candidates:
            return [], timings
        
        # Stage 2: ColBERT reranking
        stage2_start = time.perf_counter()
        
        # Encode query once
        query_emb = self.encode_text(query)
        
        # Score each candidate with ColBERT
        for candidate in candidates:
            doc_emb = self.encode_text(candidate.text)
            candidate.colbert_score = self.maxsim_score(query_emb, doc_emb)
        
        timings['stage2_ms'] = (time.perf_counter() - stage2_start) * 1000
        
        # Sort by ColBERT score
        candidates.sort(key=lambda x: x.colbert_score, reverse=True)
        
        # Assign ranks
        for i, candidate in enumerate(candidates[:top_k]):
            candidate.rank = i + 1
        
        timings['total_ms'] = timings['stage1_ms'] + timings['stage2_ms']
        
        return candidates[:top_k], timings
    
    def _stage1_bm25(self, conn, query: str, limit: int) -> List[ColBERTResult]:
        """Stage 1: Fast BM25 filtering"""
        escaped_query = escape_fts5_query(query)
        
        try:
            cursor = conn.execute("""
                SELECT id, path, text, bm25(chunks_fts) as bm25_score
                FROM chunks_fts
                WHERE chunks_fts MATCH ?
                ORDER BY bm25_score ASC
                LIMIT ?
            """, [escaped_query, limit])
            
            results = []
            for row in cursor:
                normalized_score = 1.0 / (1.0 + abs(row[3]))
                results.append(ColBERTResult(
                    id=row[0],
                    path=row[1],
                    text=row[2],
                    bm25_score=normalized_score
                ))
            
            return results
            
        except Exception as e:
            print(f"FTS5 failed for '{query}': {e}")
            return []

def benchmark_fast_colbert(db_path: str, dataset_name: str):
    """Benchmark Fast ColBERT vs our other methods"""
    print("=" * 80)
    print(f"🔬 Fast ColBERT Benchmark: {dataset_name}")
    print("=" * 80)
    print()
    
    # Initialize Fast ColBERT
    fast_colbert = FastColBERT()
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    
    # Load queries and qrels
    cursor = conn.execute("SELECT id, text FROM queries")
    queries = {row[0]: row[1] for row in cursor}
    
    cursor = conn.execute("SELECT query_id, doc_id, relevance FROM qrels")
    qrels = defaultdict(dict)
    for row in cursor:
        qrels[row[0]][row[1]] = row[2]
    
    print(f"✅ Loaded {len(queries)} queries with {len(qrels)} qrels")
    print()
    
    # Import evaluation functions
    from benchmark_beir_real import (
        calculate_ndcg, calculate_recall, calculate_precision,
        calculate_map, calculate_mrr
    )
    
    # Run benchmark
    print("=" * 80)
    print("Running Fast ColBERT benchmark...")
    print("=" * 80)
    
    metrics = {
        'ndcg': [], 'recall': [], 'precision': [], 'map': [], 'mrr': [],
        'latency': [], 'stage1_ms': [], 'stage2_ms': []
    }
    
    for i, (query_id, query_text) in enumerate(queries.items(), 1):
        if i % 50 == 0:
            print(f"Progress: {i}/{len(queries)} queries...")
        
        query_qrels = qrels.get(query_id, {})
        if not query_qrels:
            continue
        
        try:
            results, timings = fast_colbert.search(conn, query_text, top_k=10, stage1_size=100)
            
            if results:
                metrics['ndcg'].append(calculate_ndcg(results, query_qrels, k=10))
                metrics['recall'].append(calculate_recall(results, query_qrels, k=10))
                metrics['precision'].append(calculate_precision(results, query_qrels, k=10))
                metrics['map'].append(calculate_map(results, query_qrels, k=10))
                metrics['mrr'].append(calculate_mrr(results, query_qrels, k=10))
                metrics['latency'].append(timings['total_ms'])
                metrics['stage1_ms'].append(timings['stage1_ms'])
                metrics['stage2_ms'].append(timings['stage2_ms'])
            
        except Exception as e:
            print(f"Error with query {query_id}: {e}")
            continue
    
    conn.close()
    
    # Print results
    print()
    print("=" * 80)
    print("📊 FAST COLBERT RESULTS")
    print("=" * 80)
    print()
    
    avg_metrics = {k: float(np.mean(v)) if v else 0.0 for k, v in metrics.items()}
    
    print(f"{'Metric':<15} {'Value':<12}")
    print("-" * 30)
    print(f"{'NDCG@10':<15} {avg_metrics['ndcg']:<12.4f}")
    print(f"{'Recall@10':<15} {avg_metrics['recall']:<12.4f}")
    print(f"{'Precision@10':<15} {avg_metrics['precision']:<12.4f}")
    print(f"{'MAP@10':<15} {avg_metrics['map']:<12.4f}")
    print(f"{'MRR@10':<15} {avg_metrics['mrr']:<12.4f}")
    print(f"{'Latency':<15} {avg_metrics['latency']:<12.1f} ms")
    
    print()
    print("Stage breakdown:")
    print(f"  Stage 1 (BM25):    {avg_metrics['stage1_ms']:.1f}ms ({avg_metrics['stage1_ms']/avg_metrics['latency']*100:.1f}%)")
    print(f"  Stage 2 (ColBERT): {avg_metrics['stage2_ms']:.1f}ms ({avg_metrics['stage2_ms']/avg_metrics['latency']*100:.1f}%)")
    
    # Compare to our methods
    print()
    print("=" * 80)
    print("📊 COMPARISON TO OTHER METHODS")
    print("=" * 80)
    print()
    
    try:
        with open('cascaded_vs_rrf_nfcorpus.json', 'r') as f:
            our_results = json.load(f)
        
        print(f"{'Method':<20} {'NDCG@10':<12} {'Latency':<12} {'Speedup':<12}")
        print("-" * 60)
        
        rrf_speedup = avg_metrics['latency'] / our_results['rrf_metrics']['latency']
        cascaded_speedup = avg_metrics['latency'] / our_results['cascaded_metrics']['latency']
        cascaded_vs_rrf_speedup = our_results['rrf_metrics']['latency'] / our_results['cascaded_metrics']['latency']
        colbert_vs_rrf_speedup = our_results['rrf_metrics']['latency'] / avg_metrics['latency']
        
        print(f"{'RRF':<20} {our_results['rrf_metrics']['ndcg']:<12.4f} {our_results['rrf_metrics']['latency']:<12.1f} {'1.00x':<12}")
        print(f"{'Cascaded':<20} {our_results['cascaded_metrics']['ndcg']:<12.4f} {our_results['cascaded_metrics']['latency']:<12.1f} {f'{cascaded_vs_rrf_speedup:.2f}x':<12}")
        print(f"{'Fast ColBERT':<20} {avg_metrics['ndcg']:<12.4f} {avg_metrics['latency']:<12.1f} {f'{colbert_vs_rrf_speedup:.2f}x':<12}")
        
        print()
        print("Key insights:")
        ndcg_vs_rrf = (avg_metrics['ndcg'] / our_results['rrf_metrics']['ndcg'] - 1) * 100
        ndcg_vs_cascaded = (avg_metrics['ndcg'] / our_results['cascaded_metrics']['ndcg'] - 1) * 100
        
        print(f"  - Fast ColBERT vs RRF: {ndcg_vs_rrf:+.1f}% NDCG, {1/rrf_speedup:.2f}x speed")
        print(f"  - Fast ColBERT vs Cascaded: {ndcg_vs_cascaded:+.1f}% NDCG, {1/cascaded_speedup:.2f}x speed")
        
    except FileNotFoundError:
        print("Run cascaded benchmark first for comparison")
    
    # Save results
    results_data = {
        'dataset': dataset_name,
        'num_queries': len(queries),
        'metrics': avg_metrics
    }
    
    with open('fast_colbert_results.json', 'w') as f:
        json.dump(results_data, f, indent=2)
    
    print()
    print(f"💾 Results saved to: fast_colbert_results.json")
    print("=" * 80)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fast ColBERT benchmark')
    parser.add_argument('--dataset', type=str, default='nfcorpus')
    args = parser.parse_args()
    
    db_path = f"beir_{args.dataset}.db"
    
    if not Path(db_path).exists():
        print(f"❌ Database not found: {db_path}")
        return
    
    benchmark_fast_colbert(db_path, args.dataset)

if __name__ == "__main__":
    main()
