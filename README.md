# Agent Memory Retrieval: Efficient Hybrid Search for AI Agent Systems

## The Problem

AI agents like OpenClaw maintain a **memory layer** — a growing store of past observations, decisions, tool results, and conversation history. Every time an agent needs context to answer a question or complete a task, it queries this memory store.

This is not web search. It is **agent memory retrieval** — a fundamentally different problem:

| Property | Web / Document Search | Agent Memory Retrieval |
|---|---|---|
| Who wrote the content? | Third parties | The agent and user themselves |
| Query source | User typing a search | Agent generating a context query mid-task |
| Relevance | Topical similarity | Episodic relevance — "what did I decide / do / observe?" |
| Corpus size | Millions of docs | Hundreds to low thousands of memory chunks |
| Temporal signal | Usually ignored | Critical — recency and session context matter |
| Update frequency | Mostly static | Continuously growing every session |
| Latency budget | 100ms–1s acceptable | <50ms required — blocks agent response time |

**There is no established benchmark dataset for agent memory retrieval.** Existing IR benchmarks (BEIR, MS MARCO, TREC) measure document retrieval for web search and question answering — not episodic memory retrieval for AI agents. This is an open research gap.

---

## Motivation: OpenClaw

[OpenClaw](https://github.com/openclaw) is an AI agent framework that stores agent memory in SQLite using FTS5 (keyword index) and `sqlite-vec` (vector index). At query time it issues two separate SQL queries — one keyword, one vector — then fuses them in JavaScript using Reciprocal Rank Fusion (RRF):

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

**Problems with this approach:**
- Two separate SQL queries (double I/O)
- Must always fetch 200 candidates — no early termination
- Fusion happens in JavaScript, outside the database engine
- Latency ~50ms even on small memory databases
- Designed for document retrieval, not episodic agent memory

---

## Research Questions

1. **Efficiency:** Can hybrid retrieval for agent memory be made significantly faster without losing retrieval quality?
2. **Effectiveness:** Does the current RRF approach retrieve the right memories? Where does it fail?
3. **Benchmark gap:** How should agent memory retrieval be evaluated, given no standard benchmark exists?
4. **Architecture:** Is a DB-level unified retrieval operator (interleaved FTS + vector in C/SQLite) better than application-level fusion?

---

## What We Found

### Embedding model used by OpenClaw

OpenClaw uses **API-based models** when keys are available:
- Gemini: `gemini-embedding-001` (3,072 dims)
- OpenAI: `text-embedding-3-small`

When no API key is supplied, it falls back to a **local GGUF model** via `node-llama-cpp`:
- Default: `embeddinggemma-300m-qat-Q8_0.gguf` (300M param, quantised Gemma)

For our benchmarks we used `all-MiniLM-L6-v2` — free, local, no API key required. This is a general-purpose sentence similarity model, not a retrieval-trained model. Our BEIR results are therefore a lower bound — OpenClaw's actual production quality is higher.

### Benchmark used: BEIR NFCorpus

We used BEIR NFCorpus (3,633 medical documents, 323 queries) as a proxy benchmark because it has ground-truth relevance labels. This is a harder-than-average IR dataset — medical queries vs research abstracts with large vocabulary gaps. It is **not** an agent memory dataset, but it allowed controlled comparison of retrieval methods.

### Results

| Method | NDCG@10 | Latency | vs RRF |
|---|---|---|---|
| RRF baseline (BM25 + vector, top-100 each) | 0.331 | 55ms | — |
| Interleaved retrieval (Python) | 0.312 | 56ms | -5.6% NDCG, no speedup |
| **Cascaded retrieval (3-stage)** | **0.297** | **19ms** | **-10% NDCG, 3.52x faster** |
| Fast ColBERT (BM25 pre-filter + ColBERT rerank) | 0.172 | 4,455ms | -48% NDCG, 80x slower |
| Full ColBERT (bert-base-uncased, no pre-filter) | 0.207 | 123ms | -37% NDCG, 2.2x slower |

### RRF Failure Analysis

We analysed all 323 queries to understand where RRF fails. Key findings:

- **81 / 323 queries (25%) scored NDCG@10 = 0** — zero relevant docs in top-10
- The dominant failure (**89.9% of missed docs**) is that relevant documents were **not in either the FTS5 or vector top-100 candidate pool** — no amount of fusion improvement can fix this
- FTS5 returned zero results for **53% of queries** (vocabulary mismatch)
- Vector search never returned zero results, but still missed 79.1% of relevant docs (weak embedding model)
- Pure fusion failures (both indexes found the doc but RRF ranked it too low) affected only **5 queries** — a minor issue

**The 100-candidate ceiling is the bottleneck, not the fusion algorithm.**

---

## Key Competitors / Related Systems

These are the most relevant prior systems working on agent memory retrieval. They are our direct competitors when writing a paper.

| System | Venue | Retrieval Method | Embedding Model |
|--------|-------|------------------|-----------------|
| **HyMem** | Feb 2026 | Hierarchical memory tree + semantic search | Not specified (general LLM embeddings) |
| **MemR3** | 2025 | Retrieve → Reflect → Respond pipeline | Sentence-BERT variants |
| **MAGMA** | 2025 | Multi-granularity memory with graph links | Not specified |
| **EpMAN** | 2025 | Episodic memory with attention-based retrieval | BERT-based |
| **AriGraph** | 2024 | Knowledge graph + semantic retrieval | GPT-based embeddings |
| **OpenClaw (current)** | — | RRF: BM25 (FTS5) + vector (sqlite-vec) | gemini / openai / local GGUF |

**Key observation: none of the competitors use hybrid retrieval.** They all rely purely on vector/semantic search. This is the gap we are addressing — no existing agent memory system combines keyword and vector search, and none are designed for SQLite-native deployment.

### Do competitors use the same embedding model?

No — every system uses a different embedding model, and none disclose fair controlled comparisons:

- HyMem, MAGMA, EpMAN: unspecified or general-purpose LLM embeddings
- MemR3: Sentence-BERT variants (similar class to our `all-MiniLM-L6-v2`)
- AriGraph: GPT-based embeddings (API-dependent)
- OpenClaw: Gemini / OpenAI / local GGUF depending on environment

This is a significant problem for reproducibility in the field. Different embedding models can shift Recall@K by 20–40 percentage points, making system comparisons unreliable.

### Should we control the embedding model in our experiments?

**Yes — fixing the embedding model is essential for a fair comparison.** Our experimental plan:

1. **Fix one open-source embedding model across all systems** we compare (e.g., `all-MiniLM-L6-v2` or `bge-base-en-v1.5`) so that differences in results are attributable to the *retrieval architecture*, not the embedding model
2. Report results with **multiple embedding models** (cheap general-purpose vs. retrieval-trained) to show our hybrid approach is robust to embedding quality
3. Use the **same chunking strategy** across all systems (same chunk size, overlap)

The claim we want to make is: *given the same embedding model, our hybrid BM25+vector approach retrieves the right memory chunk more reliably than pure vector search* — which is what all competitors do.

---

## Why BEIR is the Wrong Benchmark for This Problem

Our BEIR results reveal a key insight: the failures we observed are largely a consequence of using a **general-purpose embedding model** on a **domain-specialised IR dataset**. This is not what OpenClaw users experience.

For agent memory retrieval:
- Queries are written by the same person who wrote the memories — vocabulary overlap is high
- Documents are short episodic chunks, not long research abstracts
- Relevant memories are often recently written — temporal recency is a strong signal
- The corpus is small (hundreds to low thousands) — exhaustive search is feasible

There is **no standard benchmark dataset** for agent memory retrieval. This is itself a research contribution opportunity: defining the evaluation protocol, metrics, and dataset for this problem.

---

## What We Tried

### Phase 1 — Fix the baseline
Initial benchmarks used fake vector search (recency-based). Fixed by computing real embeddings with `all-MiniLM-L6-v2`. NDCG improved from 0.009 → 0.331.

### Phase 2 — Interleaved retrieval with early termination
Python-level interleaved fetching from FTS5 and vector indexes. Result: 10% slower than RRF despite fetching 65% fewer docs. Python overhead dominated. **Failed.**

### Phase 3 — Cascaded retrieval (3-stage pipeline)
BM25 pre-filter (100 candidates) → vector reranking (top 30) → full hybrid scoring (top 10). Result: **3.52x faster** at the cost of 10% NDCG. **Current best for deployment.**

### Phase 4 — ColBERT benchmarks
Tested both fast ColBERT (BM25 pre-filter + ColBERT rerank with `bert-base-uncased`) and full ColBERT (no pre-filter). Both performed **worse** than RRF because `bert-base-uncased` was never trained for retrieval. A proper ColBERT v2 checkpoint would be needed for fair comparison.

---

## Next Steps

### Immediate (1–2 weeks)
1. **Build an agent memory evaluation dataset** — use real OpenClaw memory chunks + LLM-generated queries with relevance labels. This is the missing piece.
2. **Re-benchmark on OpenClaw's actual embedding model** (`embeddinggemma-300m-qat`) to get results representative of real usage.
3. **Tune cascaded retrieval** — grid search stage sizes and fusion weights on agent memory queries specifically.

### Medium-term (4–6 weeks)
4. **Test DPR as a drop-in replacement** for `all-MiniLM-L6-v2` on BEIR to establish a proper IR baseline.
5. **Test ColBERT v2** (`colbert-ir/colbertv2.0`) as a re-ranker on top of cascaded BM25 pre-filtering.
6. **Query expansion** — expand agent queries before FTS5 to reduce vocabulary mismatch failures (Category A).

### Long-term (8–12 weeks)
7. **DB-level unified operator in C/Rust** — implement interleaved FTS5 + vector traversal as a SQLite virtual table. Expected: same NDCG as RRF at 5–10ms latency. Model-agnostic contribution.
8. **Define the agent memory retrieval benchmark** — evaluation protocol, metrics beyond NDCG (task completion, memory staleness), and a reusable dataset.

---

## Repository Structure

```
.
├── scripts/
│   ├── benchmark_beir_real.py          # RRF + interleaved benchmark (real embeddings)
│   ├── cascaded_retrieval.py           # Cascaded 3-stage retrieval
│   ├── benchmark_cascaded.py           # Cascaded benchmark
│   ├── benchmark_colbert_full.py       # Full ColBERT benchmark (no pre-filter)
│   ├── fast_colbert.py                 # Fast ColBERT (BM25 pre-filter + rerank)
│   ├── analyze_rrf_failures.py         # Per-query RRF failure analysis
│   ├── analyze_keyword_vs_semantic.py  # Keyword vs semantic miss breakdown
│   ├── analyze_topk_ceiling.py         # Top-k ceiling analysis
│   ├── compute_beir_embeddings.py      # Precompute BEIR embeddings
│   └── plot_research_results.py        # Generate figures
├── figures/                            # Benchmark plots
├── datasets/                           # BEIR NFCorpus data
├── beir_nfcorpus.db                    # SQLite DB with real embeddings (18MB)
├── hybrid_retriever.py                 # Core hybrid retrieval implementation
├── RRF_FAILURE_ANALYSIS.md             # Detailed per-query failure analysis
├── CASCADED_RESULTS.md                 # Cascaded retrieval results
├── RESEARCH_PROPOSAL.md                # Original research proposal
└── requirements.txt
```

---

## Embedding Model Notes

| Model | Used by | Retrieval-trained? |
|---|---|---|
| `embeddinggemma-300m-qat` | OpenClaw (local, no API key) | General purpose |
| `gemini-embedding-001` | OpenClaw (Gemini API) | Yes (Google) |
| `text-embedding-3-small` | OpenClaw (OpenAI API) | Yes (OpenAI) |
| `all-MiniLM-L6-v2` | Our benchmarks | No (sentence similarity only) |
| DPR | Not yet tested | Yes (MS MARCO) |
| ColBERT v2 | Tested (wrong checkpoint) | Yes (MS MARCO + hard negatives) |

---

## References

- Cormack et al. (2009) — [Reciprocal Rank Fusion](https://dl.acm.org/doi/10.1145/1571941.1572114)
- Karpukhin et al. (2020) — [Dense Passage Retrieval (DPR)](https://arxiv.org/abs/2004.04906)
- Santhanam et al. (2022) — [ColBERTv2](https://arxiv.org/abs/2112.01488)
- [BEIR Benchmark](https://github.com/beir-cellar/beir)
- [sqlite-vec](https://github.com/asg017/sqlite-vec)
- [SQLite FTS5](https://www.sqlite.org/fts5.html)
- OpenClaw memory manager: `/opt/homebrew/lib/node_modules/openclaw/dist/manager-CIjpkmRY.js`
