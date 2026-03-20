# OpenClaw Hybrid Retrieval Research

Research into improving hybrid retrieval (keyword + vector search) for [OpenClaw's](https://github.com/openclaw) agent memory system. The goal is to replace the current two-pass RRF fusion approach with a faster, more efficient retrieval strategy.

---

## The Problem

OpenClaw's current memory retrieval issues two separate SQL queries — one for FTS5 keyword search and one for vector search — then fuses them in JavaScript using Reciprocal Rank Fusion (RRF):

```javascript
// From dist/manager-CIjpkmRY.js
const keywordResults = await this.searchKeyword(query, 100);  // FTS5
const vectorResults  = await this.searchVector(queryVec, 100); // sqlite-vec

const merged = await mergeHybridResults({
    vector: vectorResults,
    keyword: keywordResults,
    vectorWeight: 0.5,
    textWeight: 0.3
});
```

**Issues with this approach:**
- Two separate SQL queries (double I/O)
- Fusion happens in JavaScript, not in the database
- Must always fetch 200 candidates — no early termination
- Cannot leverage SQLite query planner
- Latency around 50ms even on small datasets

---

## What We Tried

### Phase 1 — Fix the Baseline (Week 1)

**Problem discovered:** Initial benchmarks used fake vector search (sorted by recency), giving meaningless NDCG scores (~0.009).

**Fix:**
- Implemented real semantic vector search using `sentence-transformers` (`all-MiniLM-L6-v2`)
- Built `beir_nfcorpus.db` with 3,633 real document embeddings from the BEIR NFCorpus dataset
- Re-ran all benchmarks with real embeddings

**Result:** NDCG@10 jumped from 0.009 → 0.331 (36x improvement). Established a solid RRF baseline.

---

### Phase 2 — Interleaved Retrieval with Early Termination (Week 1)

**Approach:** Instead of fetching all candidates from both indexes and then merging, interleave fetches from FTS5 and vector indexes one-by-one and stop as soon as the top-k ranking stabilises.

**Benchmark dataset:** BEIR NFCorpus — 3,633 documents, 323 queries.

| Metric | RRF (baseline) | Interleaved | Delta |
|---|---|---|---|
| NDCG@10 | 0.331 | 0.312 | -5.6% |
| Recall@10 | 0.163 | 0.156 | -4.3% |
| Precision@10 | 0.253 | 0.234 | -7.5% |
| Avg latency | 50.2ms | 55.7ms | **+10% slower** |
| Docs fetched | 200 | ~60–80 | -65% |

**Outcome:** Failed to beat RRF. Despite fetching far fewer documents, Python-level overhead (sorting every 10 fetches, incremental score computation) dominated and made it slower.

**Key learning:** Algorithm-level improvements are undermined by implementation-level overhead. Python is the wrong layer for this optimisation.

---

### Phase 3 — Cascaded Retrieval (Week 2)

**Approach:** A 3-stage pipeline that progressively narrows the candidate set:

```
Stage 1: BM25-only (100 candidates)   — fast, cheap
Stage 2: Vector reranking (top 30)    — medium cost
Stage 3: Full hybrid scoring (top 10) — precise
```

**Results:**

| Metric | RRF (baseline) | Cascaded | Delta |
|---|---|---|---|
| NDCG@10 | 0.331 | 0.297 | -10.3% |
| Recall@10 | 0.163 | 0.143 | -12.3% |
| Precision@10 | 0.253 | 0.286 | +13.4% |
| Avg latency | 54.5ms | **15.5ms** | **3.52x faster** |

**Outcome:** Winner for immediate deployment. 3.52x speedup at the cost of ~10% NDCG drop. The quality gap is expected to narrow to 5–7% with tuning.

---

## Summary of All Results

| Method | Latency | NDCG@10 | Speedup | Verdict |
|---|---|---|---|---|
| RRF (baseline) | 54.5ms | 0.331 | 1.00x | Production baseline |
| Interleaved (Python) | 56.0ms | 0.312 | 0.97x | Failed — overhead too high |
| **Cascaded** | **15.5ms** | **0.297** | **3.52x** | **Current best** |
| Unified C/Rust operator | ~5–10ms (est.) | ~0.33 (est.) | ~5–10x | Future goal |

---

## Repository Structure

```
.
├── scripts/
│   ├── benchmark_beir_real.py       # Main benchmark with real embeddings
│   ├── cascaded_retrieval.py        # Cascaded 3-stage retrieval
│   ├── compare_rrf_vs_interleaved.py
│   ├── benchmark_cascaded.py
│   ├── compute_beir_embeddings.py   # Precompute BEIR embeddings
│   └── plot_research_results.py     # Generate figures
├── figures/                         # Benchmark plots
├── datasets/                        # BEIR NFCorpus data
├── beir_nfcorpus.db                 # SQLite DB with real embeddings (18MB)
├── hybrid_retriever.py              # Core hybrid retrieval implementation
├── requirements.txt
├── RESEARCH_PROPOSAL.md
├── CASCADED_RESULTS.md
├── FINAL_RESULTS.md
└── RESEARCH_SUMMARY.md
```

---

## Possible Next Steps

### Short-term (1–2 weeks) — Improve Cascaded Retrieval

1. **Tune stage sizes** — Grid search over (Stage 1 size, Stage 2 size) on validation set to close the 10% NDCG gap.
2. **Add FTS5 fallback** — If BM25 Stage 1 returns < N results, fall back to a broader scan to improve recall.
3. **Optimise vector scoring** — Use approximate nearest neighbour (ANN) at Stage 2 instead of exact cosine.
4. **Test on larger datasets** — Scale to 10K–100K chunks to validate speedup holds at OpenClaw's real-world scale.

### Medium-term (4–6 weeks) — Smarter Interleaving

Python overhead killed the interleaved approach, but the algorithm is sound. Options:

- **Score-based early termination** — Stop when the minimum possible score of unseen docs is below the k-th result's current score (WAND/BMW-style).
- **Adaptive interleaving ratio** — Dynamically adjust how many FTS vs. vector candidates to fetch based on query characteristics.
- **Query expansion** — Expand the original query before FTS5 stage to improve recall without increasing candidate size.

### Long-term (8–12 weeks) — DB-Level Unified Operator

The original research goal: implement a **SQLite virtual table in C/Rust** that performs interleaved hybrid retrieval inside the database engine.

```sql
-- Target: single query, all fusion in C
SELECT * FROM vtab_hybrid
WHERE fts_match(?, text)
  AND vector_distance(?, embedding) < 0.8
ORDER BY hybrid_score DESC
LIMIT 10;
```

**Expected gains:**
- Latency: 5–10ms (5–10x faster than RRF)
- NDCG: No loss (exact fusion, no approximation)
- Memory: Lower (no JavaScript overhead)

This would be a novel contribution to both OpenClaw and the broader SQLite hybrid retrieval ecosystem.

---

## Dataset

- **BEIR NFCorpus** — 3,633 documents, 323 queries, medical/nutrition domain.
- Embeddings computed with `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions).
- OpenClaw production DB uses `gemini-embedding-001` (3072 dimensions) — larger scale testing should use this.

---

## References

- Cormack et al. (2009) — [Reciprocal Rank Fusion](https://dl.acm.org/doi/10.1145/1571941.1572114)
- [BEIR Benchmark](https://github.com/beir-cellar/beir)
- [sqlite-vec](https://github.com/asg017/sqlite-vec)
- [SQLite FTS5](https://www.sqlite.org/fts5.html)
- OpenClaw memory manager: `/opt/homebrew/lib/node_modules/openclaw/dist/manager-CIjpkmRY.js`
