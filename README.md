# Efficient Hybrid Retrieval: Unified Index Fusion for Lexical and Semantic Search

## Research Problem

Modern retrieval systems need to combine two complementary signals:

- **Lexical search** (BM25/FTS) — fast, precise, good at exact term matching
- **Semantic/dense search** (vector similarity) — understands meaning, handles synonymy and paraphrase

The standard approach — run both independently, then merge results — is wasteful. It performs double I/O, fetches far more candidates than needed, cannot terminate early, and pushes fusion logic into the application layer where the query planner cannot optimize it.

**The core research question:** Can moving hybrid fusion *into* the database engine's query planner — through interleaved index traversal and early termination — achieve the efficiency of cascaded filtering while preserving the recall of exhaustive fusion?

This is an open problem in the Information Retrieval community. Results are evaluated on standard IR benchmarks (BEIR, MS MARCO) and are applicable to any system that today runs keyword and vector search in separate passes: enterprise search, RAG pipelines, biomedical retrieval, legal search, and e-commerce.

### Primary Application: OpenClaw Agent Memory

The most important concrete application driving this research is [OpenClaw's](https://github.com/openclaw) agent memory system. OpenClaw is an AI agent framework whose memory layer (`memory-core`) stores observations, tool results, and conversation history in SQLite. At query time it must retrieve the most relevant memories fast — latency directly impacts agent response time.

OpenClaw's current retrieval issues two separate SQL queries — one for FTS5 keyword search and one for vector search — then fuses them in JavaScript using Reciprocal Rank Fusion (RRF):

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

This pattern is not unique to OpenClaw — it is the dominant architecture in Elasticsearch hybrid search, PostgreSQL with pgvector, and most SQLite-based RAG stacks. A solution here generalizes broadly.

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

## Datasets & Benchmarks

We use a three-tier dataset strategy to validate that results generalize across scales and domains.

### Tier 1 — BEIR NFCorpus (current experiments)

- **Size:** 3,633 documents, 323 queries, medical/nutrition domain
- **Why:** Queries mix exact biomedical terminology with semantic reasoning — the same keyword+concept duality present in agent memory queries. Small enough to iterate quickly; hard enough to expose quality differences between methods.
- **Embeddings:** `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions)

**Published NDCG@10 on NFCorpus** (from BEIR paper, Thakur et al. 2021):

| Method | Type | NDCG@10 | Notes |
|--------|------|---------|-------|
| BM25 (Elasticsearch) | Sparse/Lexical | 0.325 | Robust baseline |
| DPR (multi-dataset) | Dense bi-encoder | 0.189 | Poor OOD generalization |
| ANCE | Dense bi-encoder | 0.237 | MS MARCO trained |
| TAS-B | Dense bi-encoder | 0.319 | Balanced dense |
| ColBERT-v2 | Late interaction | 0.338 | Best single-model |
| monoT5 (re-ranker) | Cross-encoder | 0.350 | Highest quality, slowest |

**Our results on NFCorpus:**

| Method | NDCG@10 | Latency | Speedup vs RRF | Notes |
|--------|---------|---------|----------------|-------|
| RRF (BM25 + dense, exhaustive) | 0.331 | 50.2ms | 1.0× | Our baseline |
| Interleaved (early termination) | 0.312 | 55.7ms | 0.9× | Python overhead negates gains |
| Cascaded (BM25 filter → vector rerank) | 0.299 | 19.4ms | 2.9× | Best efficiency/quality trade-off so far |
| Fast ColBERT (BM25 → MaxSim rerank) | 0.171 | 4455ms | 0.01× | Token embeddings too slow without GPU |

**Key gap:** Our RRF baseline (0.331) already matches published BM25 (0.325) and approaches ColBERT-v2 (0.338) because we combine both signals. The research question is whether we can reach that quality at cascaded-retrieval speeds (sub-20ms).

---

### Tier 2 — MS MARCO Passage (scalability validation, planned)

- **Size:** 8.8M passages, ~6,980 dev queries
- **Why:** Industry-standard scale benchmark used by Elasticsearch, Vespa, Weaviate, and the broader IR community. Required to demonstrate that the unified operator scales beyond small corpora.
- **Primary metric:** MRR@10 (dev set), NDCG@10

**Published MRR@10 on MS MARCO dev set** (representative numbers from literature):

| Method | Type | MRR@10 | Notes |
|--------|------|--------|-------|
| BM25 | Sparse | 0.184 | Anserini default |
| DPR | Dense bi-encoder | 0.318 | Facebook, NQ-trained |
| ANCE | Dense bi-encoder | 0.330 | Hard-negative mining |
| ColBERT-v2 | Late interaction | 0.397 | State of the art retriever |
| SPLADE-v3 | Learned sparse | ~0.400 | Competitive with ColBERT |
| monoT5 (re-ranker over BM25) | Cross-encoder | 0.422 | Two-stage, high latency |
| RRF (BM25 + dense) | Hybrid fusion | ~0.340 | Typical hybrid baseline |

---

### Tier 3 — OpenClaw Production DB (deployment target)

- **Size:** Variable (30–100k+ agent memory entries in practice)
- **Embeddings:** `gemini-embedding-001` (3072 dimensions)
- **Why:** The primary application. Latency here directly impacts agent response time. No public ground-truth relevance judgments — evaluation is latency-focused with spot-check quality checks.

---

### What the Benchmarks Tell Us

The research problem lives in the gap between Tier 1 quality numbers and Tier 3 latency requirements:

- Exhaustive RRF matches ColBERT-v2 quality on NFCorpus but costs 50ms at small scale — unacceptable at 100k+ entries
- Cascaded retrieval hits 19ms but loses ~10% NDCG — the pruning is too aggressive
- The unified interleaved operator targets: **ColBERT-v2 quality + cascaded latency** in a single DB-level pass

---

## References

- Cormack et al. (2009) — [Reciprocal Rank Fusion](https://dl.acm.org/doi/10.1145/1571941.1572114)
- [BEIR Benchmark](https://github.com/beir-cellar/beir)
- [sqlite-vec](https://github.com/asg017/sqlite-vec)
- [SQLite FTS5](https://www.sqlite.org/fts5.html)
- OpenClaw memory manager: `/opt/homebrew/lib/node_modules/openclaw/dist/manager-CIjpkmRY.js`
