# Experiment Plan

---

## Experiment 1: OpenClaw Hybrid Retrieval vs. HyMem on Agent Memory Benchmarks

### Goal

Compare OpenClaw's hybrid retrieval system (BM25 + vector via RRF) against HyMem on standard agent memory benchmarks. This is the core experiment establishing whether hybrid retrieval outperforms pure semantic retrieval for agent memory.

### Research Question

> Does combining keyword search (BM25/FTS5) with vector search produce better memory retrieval than pure semantic search (HyMem's approach), when evaluated on agent memory benchmarks?

---

### Systems Being Compared

| System | Retrieval Method | Our implementation? |
|--------|-----------------|---------------------|
| **OpenClaw (ours)** | Hybrid: BM25 (FTS5) + vector (sqlite-vec), fused via RRF | Yes |
| **HyMem (lightweight retrieval only)** | Semantic: Level-1 vector retrieval (top-k cosine similarity over lightweight memory units). **Skip** deep module + reflection. | Re-implement lightweight module only (no end-to-end LLM reasoning) |

**Why HyMem:** Most recent SOTA (Feb 2026), benchmarks on both LoCoMo and LongMemEval, claims best efficiency-effectiveness balance. Direct competitor.

---

### Benchmark Datasets

| Dataset | # Questions | Memory type | Setup |
|---------|------------|-------------|-------|
| **LoCoMo** | ~300 QA pairs across 10 conversations | Long-term human-like conversation (up to 600 turns) | Memories pre-provided; index and retrieve |
| **LongMemEval** | 500 questions (×2 corpus sizes: S and M) | Multi-session user-assistant chat | Memories pre-provided; index and retrieve |

Both datasets provide:
- Pre-written memory corpora (no agent needed to generate memories)
- Ground-truth evidence annotations (which specific chunk answers each question)
- Allows pure retrieval evaluation without an LLM in the loop

---

### Embedding Models

Two embedding models will be tested to show results are robust across model quality:

| Model | Type | Why included |
|-------|------|-------------|
| **`embeddinggemma-300m-qat`** | OpenClaw's default local model (300M param, quantised Gemma, GGUF) | Real-world OpenClaw production model — results reflect actual user experience |
| **DPR** (`facebook/dpr-ctx_encoder-single-nq-base`) | Retrieval-trained (Dense Passage Retrieval, MS MARCO / NQ) | Proper retrieval-trained baseline; open source; widely cited in retrieval literature |

**Note on `all-MiniLM-L6-v2`:** Our earlier BEIR experiments used this model. It is a sentence similarity model, not a retrieval model, and underperformed badly (missed 79.1% of relevant docs in vector search). It will not be used in Experiment 1.

**Note on ColBERT v2:** Deferred — requires a specialised multi-vector index incompatible with SQLite's current vector extensions. May be revisited in a later experiment.

---

### Evaluation Metrics

| Metric | Role | Description |
|--------|------|-------------|
| **Recall@5** | Primary | Did the correct memory chunk appear in top-5 retrieved results? |
| **Recall@10** | Primary | Did the correct memory chunk appear in top-10 retrieved results? |
| **MRR@10** | Optional | Only compute if we want rank-sensitivity analysis. |
| **Precision@5** | Optional | Only compute as an extra sanity check. |

**Not using:**
- NDCG@10 — graded relevance metric designed for multi-doc web search, not binary memory chunk retrieval
- Answer Accuracy — confounded by LLM layer; not a clean retrieval signal

---

### Experimental Setup

```
For each (system, embedding_model, dataset) combination:
  1. Load memory corpus from dataset
  2. Chunk memories (consistent chunk size across all systems)
  3. Index:
     - OpenClaw: build FTS5 index + vector index using embedding_model
     - HyMem (light): build Level-1 (summary-level) vector index only using embedding_model
       (Level-1 units come from dataset-provided summaries when available; otherwise we use the same chunk text as a retrieval-only proxy to avoid any LLM/API dependence.)
  4. For each test question:
     a. Run retrieval → top-K chunks
     b. Check if gold chunk is in top-5 → Recall@5
     c. Check if gold chunk is in top-10 → Recall@10
     d. (Optional) Record rank of gold chunk → MRR@10
  5. Aggregate metrics across all questions
```

**Controlled variables (same across all systems):**
- Same embedding model per run
- Same chunk size and overlap
- Same top-K cutoff
- Same dataset split

**Variable:**
- Retrieval architecture (OpenClaw hybrid RRF vs. HyMem-light pure semantic)

---

### Expected Result Matrix

| System | Embedding | Dataset | Recall@5 | Recall@10 |
|--------|-----------|---------|----------|-----------|
| OpenClaw (hybrid RRF) | embeddinggemma-300m-qat | LoCoMo | TBD | TBD |
| HyMem-light | embeddinggemma-300m-qat | LoCoMo | TBD | TBD |
| OpenClaw (hybrid RRF) | DPR | LoCoMo | TBD | TBD |
| HyMem-light | DPR | LoCoMo | TBD | TBD |
| OpenClaw (hybrid RRF) | embeddinggemma-300m-qat | LongMemEval-S | TBD | TBD |
| HyMem-light | embeddinggemma-300m-qat | LongMemEval-S | TBD | TBD |
| OpenClaw (hybrid RRF) | DPR | LongMemEval-S | TBD | TBD |
| HyMem-light | DPR | LongMemEval-S | TBD | TBD |
| OpenClaw (hybrid RRF) | embeddinggemma-300m-qat | LongMemEval-M | TBD | TBD |
| HyMem-light | embeddinggemma-300m-qat | LongMemEval-M | TBD | TBD |
| OpenClaw (hybrid RRF) | DPR | LongMemEval-M | TBD | TBD |
| HyMem-light | DPR | LongMemEval-M | TBD | TBD |

---

### Hypothesis

- **H1 (main):** OpenClaw hybrid RRF achieves higher Recall@K than HyMem-light's lightweight pure semantic retrieval, because BM25 captures exact keyword matches (names, IDs, tool calls) that vector search misses in agent memory content.
- **H2 (embedding):** Both systems improve substantially when switching from `embeddinggemma-300m-qat` to DPR, but the *gap* between hybrid and pure semantic remains — showing the retrieval architecture advantage is independent of embedding quality.
- **H3 (dataset):** The hybrid advantage is larger on LongMemEval-M (more sessions, more memory chunks) because keyword exact-match becomes relatively more important at scale.

---

### Implementation Status

- [ ] Download LoCoMo dataset and parse into memory chunks
- [ ] Download LongMemEval (S and M) from HuggingFace
- [ ] Set up OpenClaw retrieval benchmark harness (extend existing `benchmark_beir_real.py`)
- [ ] Replicate HyMem lightweight retrieval only (Level-1 top-k cosine); no deep module + no reflection
- [ ] Integrate `embeddinggemma-300m-qat` as embedding model
- [ ] Integrate DPR as embedding model
- [ ] Run all 12 combinations and record results
- [ ] Fill in result matrix above
