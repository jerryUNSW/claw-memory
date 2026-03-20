#!/usr/bin/env python3
"""
RRF Failure Analysis

For every query in BEIR NFCorpus:
  1. Run RRF (FTS5 + vector, top-100 each, fuse)
  2. Compute per-query NDCG@10
  3. Identify "bad" queries (NDCG@10 == 0 or below threshold)
  4. For each bad query, record:
     - The query text
     - What RRF retrieved (top-10) and their relevance
     - What relevant docs RRF missed
     - Why it likely missed them (FTS5 only? Vector only? Neither?)

Outputs: rrf_failure_analysis.json
"""

import sqlite3
import json
import struct
import numpy as np
import sys
from pathlib import Path
from collections import defaultdict
from typing import List, Dict
from sentence_transformers import SentenceTransformer
import sqlite_vec

sys.path.append(str(Path(__file__).parent))
from compare_rrf_vs_interleaved import escape_fts5_query, serialize_f32, RetrievalResult

DB_PATH        = "beir_nfcorpus.db"
NDCG_THRESHOLD = 0.0   # queries with NDCG@10 == 0 are "zero-hit" failures
K              = 10
OUTPUT_FILE    = "rrf_failure_analysis.json"


# ---------------------------------------------------------------------------
# Search helpers (same as benchmark_beir_real.py)
# ---------------------------------------------------------------------------

def search_fts5(conn, query: str, limit: int = 100) -> List[RetrievalResult]:
    escaped = escape_fts5_query(query)
    try:
        rows = conn.execute("""
            SELECT id, path, text, bm25(chunks_fts) as s
            FROM chunks_fts WHERE chunks_fts MATCH ?
            ORDER BY s ASC LIMIT ?
        """, [escaped, limit]).fetchall()
    except Exception:
        return []
    return [RetrievalResult(
        id=r[0], path=r[1], text=r[2],
        bm25_score=1.0 / (1.0 + abs(r[3]))
    ) for r in rows]


def search_vector(conn, query: str, model, limit: int = 100) -> List[RetrievalResult]:
    q_emb = model.encode(query)
    rows = conn.execute("""
        SELECT chunks.id, chunks.path, chunks.text,
               vec_distance_cosine(chunks_vec.embedding, ?) as dist
        FROM chunks_vec
        JOIN chunks ON chunks.id = chunks_vec.id
        ORDER BY dist ASC LIMIT ?
    """, [serialize_f32(q_emb), limit]).fetchall()
    return [RetrievalResult(
        id=r[0], path=r[1], text=r[2],
        vector_score=1.0 - r[3]
    ) for r in rows]


def rrf_fuse(fts_results, vec_results, k_rrf=60,
            vec_weight=0.5, text_weight=0.3) -> List[Dict]:
    """Standard RRF fusion, returns list of {id, score, bm25_rank, vec_rank, text}"""
    fts_rank  = {r.id: i + 1 for i, r in enumerate(fts_results)}
    vec_rank  = {r.id: i + 1 for i, r in enumerate(vec_results)}
    all_ids   = set(fts_rank) | set(vec_rank)
    text_map  = {r.id: r.text for r in fts_results + vec_results}
    path_map  = {r.id: r.path for r in fts_results + vec_results}

    scored = []
    for doc_id in all_ids:
        fr = fts_rank.get(doc_id, len(fts_results) + 1)
        vr = vec_rank.get(doc_id, len(vec_results) + 1)
        score = (text_weight / (k_rrf + fr)) + (vec_weight / (k_rrf + vr))
        scored.append({
            "id":        doc_id,
            "score":     round(score, 6),
            "bm25_rank": fr if doc_id in fts_rank else None,
            "vec_rank":  vr if doc_id in vec_rank else None,
            "text":      (text_map.get(doc_id, "") or "")[:300],
            "path":      path_map.get(doc_id, ""),
        })
    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def ndcg_at_k(ranked_ids, relevant: Dict[str, int], k: int) -> float:
    dcg = sum(
        relevant.get(did, 0) / np.log2(i + 2)
        for i, did in enumerate(ranked_ids[:k])
    )
    ideal = sorted(relevant.values(), reverse=True)[:k]
    idcg  = sum(r / np.log2(i + 2) for i, r in enumerate(ideal))
    return dcg / idcg if idcg > 0 else 0.0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    conn = sqlite3.connect(DB_PATH)
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)

    # Load queries and qrels
    queries    = conn.execute("SELECT id, text FROM queries").fetchall()
    qrel_rows  = conn.execute("SELECT query_id, doc_id, relevance FROM qrels").fetchall()
    qrels: Dict[str, Dict[str, int]] = defaultdict(dict)
    for qid, did, rel in qrel_rows:
        qrels[qid][did] = rel

    print(f"Loaded {len(queries)} queries, {len(qrel_rows)} qrels")
    print("Loading embedding model (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")

    per_query_results = []
    zero_hit_count    = 0
    low_ndcg_count    = 0

    for qi, (qid, qtext) in enumerate(queries):
        relevant = qrels.get(qid, {})
        if not relevant:
            continue

        # Run RRF
        fts_res = search_fts5(conn, qtext, limit=100)
        vec_res = search_vector(conn, qtext, model, limit=100)
        fused   = rrf_fuse(fts_res, vec_res)

        ranked_ids = [d["id"] for d in fused]
        ndcg       = ndcg_at_k(ranked_ids, relevant, K)

        # Categorise FTS5 / vector coverage for relevant docs
        fts_ids = {r.id for r in fts_res}
        vec_ids = {r.id for r in vec_res}

        missed_relevant = []
        for did, rel in relevant.items():
            if rel > 0 and did not in ranked_ids[:K]:
                in_fts = did in fts_ids
                in_vec = did in vec_ids
                # fetch text
                row = conn.execute("SELECT text FROM chunks WHERE id=?", [did]).fetchone()
                doc_text = (row[0][:300] if row else "") or ""
                missed_relevant.append({
                    "doc_id":     did,
                    "relevance":  rel,
                    "in_fts100":  in_fts,
                    "in_vec100":  in_vec,
                    "in_neither": not in_fts and not in_vec,
                    "text":       doc_text,
                })

        # Annotate top-10 retrieved with relevance
        top10_annotated = []
        for d in fused[:K]:
            d2 = dict(d)
            d2["relevance"] = relevant.get(d["id"], 0)
            top10_annotated.append(d2)

        entry = {
            "query_id":        qid,
            "query_text":      qtext,
            "ndcg_at_10":      round(ndcg, 4),
            "num_relevant":    sum(1 for v in relevant.values() if v > 0),
            "top10_retrieved": top10_annotated,
            "missed_relevant": missed_relevant,
            "diagnosis": {
                "fts5_returned_any":   len(fts_res) > 0,
                "vec_returned_any":    len(vec_res) > 0,
                "missed_in_neither":   sum(1 for m in missed_relevant if m["in_neither"]),
                "missed_fts_only":     sum(1 for m in missed_relevant if m["in_fts100"] and not m["in_vec100"]),
                "missed_vec_only":     sum(1 for m in missed_relevant if not m["in_fts100"] and m["in_vec100"]),
                "missed_both_found":   sum(1 for m in missed_relevant if m["in_fts100"] and m["in_vec100"]),
            },
        }
        per_query_results.append(entry)

        if ndcg == 0.0:
            zero_hit_count += 1
        if ndcg < 0.1:
            low_ndcg_count += 1

        if (qi + 1) % 50 == 0:
            avg_so_far = np.mean([e["ndcg_at_10"] for e in per_query_results])
            print(f"  {qi+1}/{len(queries)}  avg NDCG@10={avg_so_far:.4f}  zero-hits so far={zero_hit_count}")

    conn.close()

    # Sort worst first
    per_query_results.sort(key=lambda x: x["ndcg_at_10"])

    avg_ndcg = np.mean([e["ndcg_at_10"] for e in per_query_results])

    # Summary statistics
    ndcg_vals = [e["ndcg_at_10"] for e in per_query_results]
    summary = {
        "dataset":           "nfcorpus",
        "num_queries":       len(per_query_results),
        "avg_ndcg_at_10":    round(avg_ndcg, 4),
        "zero_hit_queries":  zero_hit_count,
        "low_ndcg_lt_0.1":   low_ndcg_count,
        "ndcg_distribution": {
            "min":    round(float(np.min(ndcg_vals)), 4),
            "p10":    round(float(np.percentile(ndcg_vals, 10)), 4),
            "p25":    round(float(np.percentile(ndcg_vals, 25)), 4),
            "median": round(float(np.median(ndcg_vals)), 4),
            "p75":    round(float(np.percentile(ndcg_vals, 75)), 4),
            "p90":    round(float(np.percentile(ndcg_vals, 90)), 4),
            "max":    round(float(np.max(ndcg_vals)), 4),
        },
        "diagnosis_totals": {
            "queries_fts5_returned_nothing": sum(1 for e in per_query_results if not e["diagnosis"]["fts5_returned_any"]),
            "total_missed_in_neither":       sum(e["diagnosis"]["missed_in_neither"] for e in per_query_results),
            "total_missed_fts_only":         sum(e["diagnosis"]["missed_fts_only"] for e in per_query_results),
            "total_missed_vec_only":         sum(e["diagnosis"]["missed_vec_only"] for e in per_query_results),
            "total_missed_both_found":       sum(e["diagnosis"]["missed_both_found"] for e in per_query_results),
        },
    }

    output = {
        "summary":      summary,
        "worst_queries": per_query_results,   # sorted worst NDCG first
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    # Print summary
    print()
    print("=" * 65)
    print("RRF FAILURE ANALYSIS SUMMARY")
    print("=" * 65)
    print(f"Queries evaluated:        {summary['num_queries']}")
    print(f"Avg NDCG@10:              {summary['avg_ndcg_at_10']}")
    print(f"Zero-hit queries:         {summary['zero_hit_queries']}")
    print(f"Low NDCG (<0.1) queries:  {summary['low_ndcg_lt_0.1']}")
    print()
    print("NDCG distribution:")
    for k, v in summary["ndcg_distribution"].items():
        print(f"  {k:<8}: {v}")
    print()
    print("Miss diagnosis (why relevant docs were not in top-10):")
    d = summary["diagnosis_totals"]
    print(f"  FTS5 returned nothing for query:      {d['queries_fts5_returned_nothing']}")
    print(f"  Doc missed — not in FTS nor vec top100: {d['total_missed_in_neither']}")
    print(f"  Doc missed — in FTS top100 only:        {d['total_missed_fts_only']}")
    print(f"  Doc missed — in vec top100 only:        {d['total_missed_vec_only']}")
    print(f"  Doc missed — in BOTH top100 (fusion fail): {d['total_missed_both_found']}")
    print()
    print(f"Results saved to: {OUTPUT_FILE}")
    print("=" * 65)
    print()
    print("TOP 10 WORST QUERIES:")
    for e in per_query_results[:10]:
        print(f"  NDCG={e['ndcg_at_10']:.4f}  rel={e['num_relevant']:3d}  missed={len(e['missed_relevant']):3d}  '{e['query_text'][:70]}'")


if __name__ == "__main__":
    main()
