#!/usr/bin/env python3
"""
Experiment 1: OpenClaw Hybrid Retrieval vs Pure Semantic on Agent Memory Benchmarks

Compares:
  - OpenClaw hybrid: BM25 (FTS5) + vector search, fused via RRF
  - Pure semantic: vector-only retrieval (HyMem-style baseline)

Datasets:
  - LoCoMo: 10 long conversations, ~1986 QA pairs
  - LongMemEval (oracle): 500 questions with per-question haystacks

Embedding models:
  - all-MiniLM-L6-v2: lightweight sentence similarity model (384 dims)
  - DPR: retrieval-trained dual encoder (768 dims)

Metrics: Recall@5, Recall@10, MRR@10, Precision@5

Usage:
    python3 scripts/experiment1.py
    python3 scripts/experiment1.py --dataset locomo
    python3 scripts/experiment1.py --dataset longmemeval
    python3 scripts/experiment1.py --model minilm
    python3 scripts/experiment1.py --model dpr
"""

import argparse
import json
import math
import os
import sqlite3
import struct
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import sqlite_vec
from tqdm import tqdm

REPO_ROOT = Path(__file__).parent.parent
RESULTS_DIR = REPO_ROOT / "experiment1_results"
RESULTS_DIR.mkdir(exist_ok=True)


# ============================================================================
# Embedding Model Abstractions
# ============================================================================

class EmbeddingModel(ABC):
    """Abstract embedding model interface."""

    @abstractmethod
    def encode_queries(self, texts: List[str]) -> np.ndarray:
        """Encode query texts into vectors."""

    @abstractmethod
    def encode_chunks(self, texts: List[str]) -> np.ndarray:
        """Encode memory chunk texts into vectors."""

    @abstractmethod
    def dimension(self) -> int:
        """Return embedding dimension."""

    @abstractmethod
    def name(self) -> str:
        """Human-readable model name."""


class MiniLMModel(EmbeddingModel):
    """all-MiniLM-L6-v2 via sentence-transformers."""

    def __init__(self):
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer('all-MiniLM-L6-v2')

    def encode_queries(self, texts: List[str]) -> np.ndarray:
        return self._model.encode(texts, show_progress_bar=False)

    def encode_chunks(self, texts: List[str]) -> np.ndarray:
        return self._model.encode(texts, show_progress_bar=False, batch_size=128)

    def dimension(self) -> int:
        return 384

    def name(self) -> str:
        return "all-MiniLM-L6-v2"


class DPRModel(EmbeddingModel):
    """Facebook DPR dual-encoder (separate question/context encoders)."""

    def __init__(self):
        import torch
        from transformers import DPRContextEncoder, DPRContextEncoderTokenizer
        from transformers import DPRQuestionEncoder, DPRQuestionEncoderTokenizer

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._q_tokenizer = DPRQuestionEncoderTokenizer.from_pretrained(
            'facebook/dpr-question_encoder-single-nq-base')
        self._q_encoder = DPRQuestionEncoder.from_pretrained(
            'facebook/dpr-question_encoder-single-nq-base').to(self.device).eval()
        self._c_tokenizer = DPRContextEncoderTokenizer.from_pretrained(
            'facebook/dpr-ctx_encoder-single-nq-base')
        self._c_encoder = DPRContextEncoder.from_pretrained(
            'facebook/dpr-ctx_encoder-single-nq-base').to(self.device).eval()

    def _encode(self, texts, tokenizer, encoder, batch_size=32):
        import torch
        all_embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            inputs = tokenizer(batch, return_tensors='pt', padding=True,
                               truncation=True, max_length=512).to(self.device)
            with torch.no_grad():
                outputs = encoder(**inputs)
            all_embeddings.append(outputs.pooler_output.cpu().numpy())
        return np.concatenate(all_embeddings, axis=0)

    def encode_queries(self, texts: List[str]) -> np.ndarray:
        return self._encode(texts, self._q_tokenizer, self._q_encoder)

    def encode_chunks(self, texts: List[str]) -> np.ndarray:
        return self._encode(texts, self._c_tokenizer, self._c_encoder)

    def dimension(self) -> int:
        return 768

    def name(self) -> str:
        return "DPR"


def load_model(model_name: str) -> EmbeddingModel:
    if model_name == "minilm":
        return MiniLMModel()
    elif model_name == "dpr":
        return DPRModel()
    else:
        raise ValueError(f"Unknown model: {model_name}")


# ============================================================================
# Data Structures
# ============================================================================

@dataclass
class MemoryChunk:
    chunk_id: str
    text: str
    session_id: str = ""
    speaker: str = ""
    timestamp: str = ""


@dataclass
class RetrievalQuery:
    query_id: str
    question: str
    gold_chunk_ids: List[str]
    category: str = ""


@dataclass
class DatasetInstance:
    """A single retrieval instance: a set of chunks + queries over them."""
    instance_id: str
    chunks: List[MemoryChunk]
    queries: List[RetrievalQuery]


# ============================================================================
# Dataset Loaders
# ============================================================================

def load_locomo() -> List[DatasetInstance]:
    """Load LoCoMo dataset: 10 conversations, each with QA pairs."""
    data_path = REPO_ROOT / "datasets" / "locomo" / "locomo10.json"
    if not data_path.exists():
        raise FileNotFoundError(f"LoCoMo data not found at {data_path}")

    with open(data_path) as f:
        data = json.load(f)

    instances = []
    for conv_idx, conv_data in enumerate(data):
        conv = conv_data['conversation']
        chunks = []

        session_keys = sorted(
            [k for k in conv.keys() if k.startswith('session_') and not k.endswith('_date_time')],
            key=lambda x: int(x.split('_')[1])
        )

        dia_id_to_chunk_id = {}
        for sess_key in session_keys:
            session = conv[sess_key]
            if not isinstance(session, list):
                continue
            date_key = f"{sess_key}_date_time"
            sess_date = conv.get(date_key, "")

            for turn in session:
                dia_id = turn['dia_id']
                text = turn['text']
                speaker = turn.get('speaker', '')
                chunk_id = f"conv{conv_idx}_{dia_id.replace(':', '_')}"
                dia_id_to_chunk_id[dia_id] = chunk_id
                chunks.append(MemoryChunk(
                    chunk_id=chunk_id,
                    text=f"[{speaker}] {text}" if speaker else text,
                    session_id=sess_key,
                    speaker=speaker,
                    timestamp=sess_date,
                ))

        queries = []
        for qa_idx, qa in enumerate(conv_data.get('qa', [])):
            gold_ids = []
            for ev in qa.get('evidence', []):
                if ev in dia_id_to_chunk_id:
                    gold_ids.append(dia_id_to_chunk_id[ev])

            if not gold_ids:
                continue

            cat_map = {1: "single-hop", 2: "temporal", 3: "multi-hop", 4: "open-domain", 5: "unanswerable"}
            queries.append(RetrievalQuery(
                query_id=f"conv{conv_idx}_q{qa_idx}",
                question=qa['question'],
                gold_chunk_ids=gold_ids,
                category=cat_map.get(qa.get('category', 0), "unknown"),
            ))

        instances.append(DatasetInstance(
            instance_id=f"locomo_conv{conv_idx}",
            chunks=chunks,
            queries=queries,
        ))

    return instances


def load_longmemeval_oracle() -> List[DatasetInstance]:
    """Load LongMemEval oracle: 500 questions, each with its own haystack."""
    data_path = REPO_ROOT / "datasets" / "longmemeval" / "longmemeval_oracle"
    if not data_path.exists():
        raise FileNotFoundError(f"LongMemEval oracle not found at {data_path}")

    with open(data_path) as f:
        data = json.load(f)

    instances = []
    for entry in data:
        qid = entry['question_id']
        chunks = []
        gold_ids = []

        for sess_idx, session in enumerate(entry['haystack_sessions']):
            sess_id = entry['haystack_session_ids'][sess_idx] if sess_idx < len(entry.get('haystack_session_ids', [])) else f"sess_{sess_idx}"
            for turn_idx, turn in enumerate(session):
                chunk_id = f"{qid}_s{sess_idx}_t{turn_idx}"
                role = turn.get('role', 'unknown')
                text = turn.get('content', '')
                chunks.append(MemoryChunk(
                    chunk_id=chunk_id,
                    text=f"[{role}] {text}",
                    session_id=str(sess_id),
                    speaker=role,
                ))
                if turn.get('has_answer', False):
                    gold_ids.append(chunk_id)

        if not gold_ids or not chunks:
            continue

        query = RetrievalQuery(
            query_id=qid,
            question=entry['question'],
            gold_chunk_ids=gold_ids,
            category=entry.get('question_type', 'unknown'),
        )

        instances.append(DatasetInstance(
            instance_id=f"lme_{qid}",
            chunks=chunks,
            queries=[query],
        ))

    return instances


# ============================================================================
# Retrieval Systems
# ============================================================================

def serialize_f32(vector) -> bytes:
    return struct.pack(f'{len(vector)}f', *vector)


def escape_fts5(query: str) -> str:
    special = ['"', '-', '(', ')', '*', ':', '&', "'", '.', '?', '!', ',', ';', '/']
    escaped = query
    for ch in special:
        escaped = escaped.replace(ch, ' ')
    words = [w for w in escaped.split() if len(w) > 1]
    return ' OR '.join(words) if words else 'the'


def build_index(conn: sqlite3.Connection, chunks: List[MemoryChunk],
                embeddings: np.ndarray, dim: int):
    """Build FTS5 + vector index in SQLite."""
    conn.execute("CREATE TABLE IF NOT EXISTS chunks (chunk_id TEXT PRIMARY KEY, text TEXT, session_id TEXT)")
    conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(chunk_id, text, content=chunks, content_rowid=rowid)")
    conn.execute(f"CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(chunk_id TEXT PRIMARY KEY, embedding float[{dim}])")

    for i, chunk in enumerate(chunks):
        conn.execute("INSERT INTO chunks (rowid, chunk_id, text, session_id) VALUES (?, ?, ?, ?)",
                     (i + 1, chunk.chunk_id, chunk.text, chunk.session_id))
        conn.execute("INSERT INTO chunks_fts (rowid, chunk_id, text) VALUES (?, ?, ?)",
                     (i + 1, chunk.chunk_id, chunk.text))
        conn.execute("INSERT INTO chunks_vec (chunk_id, embedding) VALUES (?, ?)",
                     (chunk.chunk_id, serialize_f32(embeddings[i])))
    conn.commit()


def retrieve_hybrid_rrf(conn: sqlite3.Connection, query_text: str,
                        query_embedding: np.ndarray, top_k: int = 10,
                        fts_limit: int = 100, vec_limit: int = 100,
                        vector_weight: float = 0.5, text_weight: float = 0.3) -> List[str]:
    """OpenClaw-style hybrid retrieval: BM25 + vector → RRF fusion."""
    escaped = escape_fts5(query_text)
    by_id: Dict[str, dict] = {}

    try:
        fts_rows = conn.execute("""
            SELECT chunk_id, bm25(chunks_fts) as score
            FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY score ASC LIMIT ?
        """, [escaped, fts_limit]).fetchall()
    except Exception:
        fts_rows = []

    for row in fts_rows:
        cid, score = row
        by_id[cid] = {'bm25': 1.0 / (1.0 + abs(score)), 'vec': 0.0}

    vec_rows = conn.execute("""
        SELECT chunk_id, vec_distance_cosine(embedding, ?) as dist
        FROM chunks_vec ORDER BY dist ASC LIMIT ?
    """, [serialize_f32(query_embedding), vec_limit]).fetchall()

    for row in vec_rows:
        cid, dist = row
        sim = 1.0 - dist
        if cid in by_id:
            by_id[cid]['vec'] = sim
        else:
            by_id[cid] = {'bm25': 0.0, 'vec': sim}

    scored = []
    for cid, scores in by_id.items():
        hybrid = vector_weight * scores['vec'] + text_weight * scores['bm25']
        scored.append((cid, hybrid))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [cid for cid, _ in scored[:top_k]]


def retrieve_pure_semantic(conn: sqlite3.Connection,
                           query_embedding: np.ndarray,
                           top_k: int = 10) -> List[str]:
    """HyMem-style pure semantic retrieval: vector-only."""
    vec_rows = conn.execute("""
        SELECT chunk_id, vec_distance_cosine(embedding, ?) as dist
        FROM chunks_vec ORDER BY dist ASC LIMIT ?
    """, [serialize_f32(query_embedding), top_k]).fetchall()

    return [row[0] for row in vec_rows]


# ============================================================================
# Evaluation Metrics
# ============================================================================

def recall_at_k(retrieved_ids: List[str], gold_ids: List[str], k: int) -> float:
    retrieved_set = set(retrieved_ids[:k])
    gold_set = set(gold_ids)
    if not gold_set:
        return 0.0
    return len(retrieved_set & gold_set) / len(gold_set)


def precision_at_k(retrieved_ids: List[str], gold_ids: List[str], k: int) -> float:
    retrieved = retrieved_ids[:k]
    if not retrieved:
        return 0.0
    gold_set = set(gold_ids)
    return sum(1 for rid in retrieved if rid in gold_set) / len(retrieved)


def mrr_at_k(retrieved_ids: List[str], gold_ids: List[str], k: int) -> float:
    gold_set = set(gold_ids)
    for i, rid in enumerate(retrieved_ids[:k]):
        if rid in gold_set:
            return 1.0 / (i + 1)
    return 0.0


def hit_at_k(retrieved_ids: List[str], gold_ids: List[str], k: int) -> float:
    """Binary: did ANY gold chunk appear in top-k?"""
    retrieved_set = set(retrieved_ids[:k])
    return 1.0 if retrieved_set & set(gold_ids) else 0.0


# ============================================================================
# Experiment Runner
# ============================================================================

@dataclass
class ExperimentResult:
    system: str
    model_name: str
    dataset: str
    recall_5: float = 0.0
    recall_10: float = 0.0
    mrr_10: float = 0.0
    precision_5: float = 0.0
    hit_5: float = 0.0
    hit_10: float = 0.0
    num_queries: int = 0
    avg_latency_ms: float = 0.0
    per_category: Dict[str, Dict[str, float]] = field(default_factory=dict)


def run_experiment(instances: List[DatasetInstance], model: EmbeddingModel,
                   dataset_name: str) -> Tuple[ExperimentResult, ExperimentResult]:
    """Run both retrieval systems on a dataset and return results."""
    hybrid_metrics = defaultdict(list)
    semantic_metrics = defaultdict(list)
    hybrid_latencies = []
    semantic_latencies = []
    category_metrics = {'hybrid': defaultdict(lambda: defaultdict(list)),
                        'semantic': defaultdict(lambda: defaultdict(list))}

    total_queries = sum(len(inst.queries) for inst in instances)
    print(f"\n  Processing {len(instances)} instances, {total_queries} queries...")

    pbar = tqdm(total=total_queries, desc=f"  {dataset_name}", leave=True)

    for inst in instances:
        if not inst.chunks or not inst.queries:
            continue

        chunk_texts = [c.text for c in inst.chunks]
        chunk_embeddings = model.encode_chunks(chunk_texts)

        query_texts = [q.question for q in inst.queries]
        query_embeddings = model.encode_queries(query_texts)

        conn = sqlite3.connect(":memory:")
        conn.enable_load_extension(True)
        sqlite_vec.load(conn)
        build_index(conn, inst.chunks, chunk_embeddings, model.dimension())

        for q_idx, query in enumerate(inst.queries):
            q_emb = query_embeddings[q_idx]

            t0 = time.perf_counter()
            hybrid_ids = retrieve_hybrid_rrf(conn, query.question, q_emb, top_k=10)
            hybrid_latencies.append((time.perf_counter() - t0) * 1000)

            t0 = time.perf_counter()
            semantic_ids = retrieve_pure_semantic(conn, q_emb, top_k=10)
            semantic_latencies.append((time.perf_counter() - t0) * 1000)

            for metric_name, retrieved, storage in [
                ("hybrid", hybrid_ids, hybrid_metrics),
                ("semantic", semantic_ids, semantic_metrics),
            ]:
                storage['recall_5'].append(recall_at_k(retrieved, query.gold_chunk_ids, 5))
                storage['recall_10'].append(recall_at_k(retrieved, query.gold_chunk_ids, 10))
                storage['mrr_10'].append(mrr_at_k(retrieved, query.gold_chunk_ids, 10))
                storage['precision_5'].append(precision_at_k(retrieved, query.gold_chunk_ids, 5))
                storage['hit_5'].append(hit_at_k(retrieved, query.gold_chunk_ids, 5))
                storage['hit_10'].append(hit_at_k(retrieved, query.gold_chunk_ids, 10))

                cat = query.category
                category_metrics[metric_name][cat]['recall_5'].append(
                    recall_at_k(retrieved, query.gold_chunk_ids, 5))
                category_metrics[metric_name][cat]['recall_10'].append(
                    recall_at_k(retrieved, query.gold_chunk_ids, 10))
                category_metrics[metric_name][cat]['mrr_10'].append(
                    mrr_at_k(retrieved, query.gold_chunk_ids, 10))
                category_metrics[metric_name][cat]['hit_10'].append(
                    hit_at_k(retrieved, query.gold_chunk_ids, 10))

            pbar.update(1)

        conn.close()

    pbar.close()

    def build_result(system_name, metrics, latencies, cat_metrics):
        per_cat = {}
        for cat, cat_data in cat_metrics.items():
            per_cat[cat] = {k: float(np.mean(v)) for k, v in cat_data.items()}
            per_cat[cat]['count'] = len(cat_data.get('recall_5', []))
        return ExperimentResult(
            system=system_name,
            model_name=model.name(),
            dataset=dataset_name,
            recall_5=float(np.mean(metrics['recall_5'])),
            recall_10=float(np.mean(metrics['recall_10'])),
            mrr_10=float(np.mean(metrics['mrr_10'])),
            precision_5=float(np.mean(metrics['precision_5'])),
            hit_5=float(np.mean(metrics['hit_5'])),
            hit_10=float(np.mean(metrics['hit_10'])),
            num_queries=len(metrics['recall_5']),
            avg_latency_ms=float(np.mean(latencies)),
            per_category=per_cat,
        )

    hybrid_result = build_result("OpenClaw (Hybrid RRF)", hybrid_metrics,
                                 hybrid_latencies, category_metrics['hybrid'])
    semantic_result = build_result("Pure Semantic", semantic_metrics,
                                  semantic_latencies, category_metrics['semantic'])

    return hybrid_result, semantic_result


# ============================================================================
# Output & Reporting
# ============================================================================

def print_results(results: List[ExperimentResult]):
    print("\n" + "=" * 90)
    print("EXPERIMENT 1 RESULTS")
    print("=" * 90)

    header = f"{'System':<25} {'Model':<20} {'Dataset':<15} {'Recall@5':<10} {'Recall@10':<10} {'MRR@10':<10} {'Hit@10':<10} {'#Q':<6}"
    print(f"\n{header}")
    print("-" * 90)

    for r in results:
        print(f"{r.system:<25} {r.model_name:<20} {r.dataset:<15} "
              f"{r.recall_5:<10.4f} {r.recall_10:<10.4f} {r.mrr_10:<10.4f} "
              f"{r.hit_10:<10.4f} {r.num_queries:<6}")

    print("\n" + "=" * 90)
    print("PER-CATEGORY BREAKDOWN")
    print("=" * 90)

    for r in results:
        print(f"\n  {r.system} | {r.model_name} | {r.dataset}")
        print(f"  {'Category':<30} {'Recall@5':<10} {'Recall@10':<10} {'MRR@10':<10} {'Hit@10':<10} {'#Q':<6}")
        print(f"  {'-'*80}")
        for cat in sorted(r.per_category.keys()):
            cd = r.per_category[cat]
            print(f"  {cat:<30} {cd.get('recall_5',0):<10.4f} {cd.get('recall_10',0):<10.4f} "
                  f"{cd.get('mrr_10',0):<10.4f} {cd.get('hit_10',0):<10.4f} {cd.get('count',0):<6.0f}")


def save_results(results: List[ExperimentResult], append: bool = True):
    out_path = RESULTS_DIR / "experiment1_results.json"

    existing = []
    if append and out_path.exists():
        with open(out_path) as f:
            existing = json.load(f)

    new_entries = []
    for r in results:
        new_entries.append({
            'system': r.system,
            'model': r.model_name,
            'dataset': r.dataset,
            'recall_5': r.recall_5,
            'recall_10': r.recall_10,
            'mrr_10': r.mrr_10,
            'precision_5': r.precision_5,
            'hit_5': r.hit_5,
            'hit_10': r.hit_10,
            'num_queries': r.num_queries,
            'avg_latency_ms': r.avg_latency_ms,
            'per_category': r.per_category,
        })

    merged = []
    seen = set()
    for entry in new_entries:
        key = (entry['system'], entry['model'], entry['dataset'])
        seen.add(key)
        merged.append(entry)
    for entry in existing:
        key = (entry['system'], entry['model'], entry['dataset'])
        if key not in seen:
            merged.append(entry)

    with open(out_path, 'w') as f:
        json.dump(merged, f, indent=2)
    print(f"\nResults saved to: {out_path} ({len(merged)} entries)")


# ============================================================================
# Main
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Experiment 1: Hybrid vs Pure Semantic Retrieval')
    parser.add_argument('--dataset', type=str, default='all',
                        choices=['all', 'locomo', 'longmemeval'],
                        help='Which dataset to run (default: all)')
    parser.add_argument('--model', type=str, default='all',
                        choices=['all', 'minilm', 'dpr'],
                        help='Which embedding model (default: all)')
    args = parser.parse_args()

    print("=" * 90)
    print("EXPERIMENT 1: OpenClaw Hybrid Retrieval vs Pure Semantic")
    print("=" * 90)

    models_to_run = ['minilm', 'dpr'] if args.model == 'all' else [args.model]
    datasets_to_run = ['locomo', 'longmemeval'] if args.dataset == 'all' else [args.dataset]

    dataset_loaders = {
        'locomo': ('LoCoMo', load_locomo),
        'longmemeval': ('LongMemEval', load_longmemeval_oracle),
    }

    all_results = []

    for model_name in models_to_run:
        print(f"\n{'='*90}")
        print(f"Loading embedding model: {model_name}")
        print(f"{'='*90}")
        model = load_model(model_name)
        print(f"Model loaded: {model.name()} (dim={model.dimension()})")

        for ds_key in datasets_to_run:
            ds_label, loader = dataset_loaders[ds_key]
            print(f"\n--- Dataset: {ds_label} ---")

            instances = loader()
            total_chunks = sum(len(inst.chunks) for inst in instances)
            total_queries = sum(len(inst.queries) for inst in instances)
            print(f"  Loaded: {len(instances)} instances, {total_chunks} chunks, {total_queries} queries")

            hybrid_result, semantic_result = run_experiment(instances, model, ds_label)
            all_results.extend([hybrid_result, semantic_result])

            print(f"\n  Hybrid RRF:     Recall@5={hybrid_result.recall_5:.4f}  Recall@10={hybrid_result.recall_10:.4f}  MRR@10={hybrid_result.mrr_10:.4f}  Hit@10={hybrid_result.hit_10:.4f}")
            print(f"  Pure Semantic:  Recall@5={semantic_result.recall_5:.4f}  Recall@10={semantic_result.recall_10:.4f}  MRR@10={semantic_result.mrr_10:.4f}  Hit@10={semantic_result.hit_10:.4f}")

    print_results(all_results)
    save_results(all_results)

    print("\nDone! Run 'python3 scripts/experiment1_plots.py' to generate visualizations.")


if __name__ == "__main__":
    main()
