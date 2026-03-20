# Final Benchmark Results - Real Embeddings with Optimizations

## Executive Summary

We successfully fixed the critical issues and benchmarked RRF vs Interleaved retrieval with real embeddings on BEIR NFCorpus (3,633 documents, 323 queries).

**Key Findings:**
- ✅ Real embeddings improved NDCG from 0.009 to 0.33 (36x improvement)
- ✅ Both methods now use semantic vector search
- ⚠️ Interleaved with early termination shows slight effectiveness trade-off
- ⚠️ Current implementation is not faster than RRF (0.90x speedup)

---

## Benchmark Results

### BEIR NFCorpus Dataset
- Documents: 3,633
- Queries: 323
- Domain: Medical/nutrition information retrieval

### Effectiveness Metrics (NDCG@10 is primary)

| Metric | RRF | Interleaved | Difference | Analysis |
|--------|-----|-------------|------------|----------|
| **NDCG@10** | **0.3309** | **0.3124** | **-0.0185** | Interleaved slightly worse due to early termination |
| Recall@10 | 0.1631 | 0.1556 | -0.0075 | Missing some relevant docs |
| Precision@10 | 0.2526 | 0.2344 | -0.0183 | Lower precision |
| MAP@10 | 0.1186 | 0.1133 | -0.0053 | Slightly lower |
| MRR@10 | 0.5208 | 0.4838 | -0.0370 | First relevant doc ranked lower |

### Efficiency Metrics

| Method | Avg Latency | Speedup | Documents Fetched |
|--------|-------------|---------|-------------------|
| RRF (baseline) | 50.23ms | 1.00x | 200 (100 FTS + 100 Vector) |
| Interleaved | 55.70ms | 0.90x | ~60-80 (early termination) |

**Observation:** Interleaved is currently SLOWER despite fetching fewer documents. This is because:
1. Early termination check overhead (sorting every 10 fetches)
2. Incremental score computation overhead
3. Python implementation overhead vs optimized SQLite operations

---

## What We Fixed

### Priority 1: Real Vector Search ✅

**Before:**
```python
# Fake vector search using recency
ORDER BY updated_at DESC
sim_score = 1.0 - (i / limit)
```

**After:**
```python
# Real vector search with embeddings
query_embedding = model.encode(query)
vec_distance_cosine(chunks_vec.embedding, query_embedding)
```

**Impact:** NDCG improved from 0.009 → 0.33 (36x better!)

### Priority 2: Interleaved with Early Termination ✅

**Implementation:**
- Alternates fetching from FTS5 (2 docs) and Vector (1 doc) per iteration
- Computes hybrid scores incrementally
- Stops when top-10 is stable for 15 consecutive checks
- Typically fetches 60-80 documents instead of 200

**Trade-off:**
- Fetches 60-70% fewer documents
- But 5.6% lower NDCG due to early termination
- Currently 10% slower due to implementation overhead

---

## Analysis

### Why is Interleaved Slower?

Despite fetching fewer documents, interleaved is slower because:

1. **Early termination overhead:** Sorting all candidates every 10 fetches to check stability
2. **Incremental computation:** Computing hybrid scores for each document as it arrives
3. **Python overhead:** Pure Python implementation vs SQLite's optimized C code
4. **Small dataset:** With only 3,633 docs, fetching 200 is already very fast (50ms)

### Why is Effectiveness Lower?

Early termination stops fetching when top-10 appears stable, but:
- Some relevant documents appear later in the rankings
- Stopping at 60-80 docs misses documents that would rank in top-10 if we fetched all 200
- This is the classic speed vs accuracy trade-off

### When Would Interleaved Win?

Interleaved retrieval would show benefits when:

1. **Larger datasets:** Millions of documents where fetching 200 from each index is expensive
2. **Lower-level implementation:** C/C++ implementation in SQLite itself, not Python
3. **Relaxed effectiveness requirements:** If 5% NDCG drop is acceptable for speed
4. **Streaming scenarios:** When you need to show results progressively

---

## Comparison to Original Goals

### Original Hypothesis
"Interleaved retrieval can match RRF effectiveness while being 10x faster through early termination"

### Reality Check
- ✅ Interleaved fetches 60-70% fewer documents
- ❌ Effectiveness is 5.6% lower (0.31 vs 0.33 NDCG)
- ❌ Latency is 10% slower (56ms vs 50ms)

### Why the Discrepancy?

1. **Dataset size:** NFCorpus is small (3,633 docs). Fetching 200 docs is already fast.
2. **Implementation language:** Python overhead dominates. SQLite's C code is highly optimized.
3. **Early termination cost:** Checking stability requires sorting, which adds overhead.

---

## Recommendations

### For OpenClaw Production

**Use RRF (current approach)** because:
- ✅ Better effectiveness (0.33 vs 0.31 NDCG)
- ✅ Simpler implementation
- ✅ Faster on small-medium datasets (<100K docs)
- ✅ No early termination tuning needed
- ✅ Already implemented and tested

### For Future Research

**Interleaved could be valuable if:**
1. **Implement in C/Rust:** Add to SQLite as a native function
2. **Larger datasets:** Test on 1M+ document collections
3. **Better early termination:** Use statistical tests instead of simple stability checks
4. **Adaptive fetching:** Adjust fetch ratios based on query characteristics

### For This Research

**Next steps:**
1. ✅ Document findings (this file)
2. ✅ Fix FTS5 escaping for 100% query success (Priority 3)
3. Test on larger BEIR datasets (SciFact, FiQA)
4. Explore adaptive early termination strategies
5. Consider C/Rust implementation for fair comparison

---

## Key Lessons Learned

### 1. Real Data is Essential
- Simulated vector search gave 36x worse results
- Can't evaluate retrieval quality without real embeddings
- Always use real data for benchmarking

### 2. Implementation Matters
- Theory: Interleaved should be faster
- Reality: Python overhead makes it slower
- Language and optimization level are critical

### 3. Dataset Size Matters
- Small datasets (3K docs): RRF is fast enough
- Large datasets (1M+ docs): Interleaved might win
- Always test on realistic data sizes

### 4. Trade-offs are Real
- Early termination reduces fetches but hurts effectiveness
- Speed vs accuracy is a fundamental trade-off
- Need to quantify and accept trade-offs

### 5. Be Honest About Results
- Don't claim speedups before measuring
- Report negative results honestly
- Understand why results differ from expectations

---

## Files Generated

1. `beir_nfcorpus.db` - Database with real embeddings (18MB)
2. `scripts/compute_beir_embeddings.py` - Embedding computation script
3. `scripts/benchmark_beir_real.py` - Benchmark with real embeddings
4. `scripts/compare_rrf_vs_interleaved.py` - Updated with real vector search
5. `beir_nfcorpus_real_results.json` - Final benchmark results
6. `CRITICAL_ISSUES_RESOLVED.md` - Issue tracking and resolution
7. `FINAL_RESULTS.md` - This document

---

## Conclusion

We successfully implemented and benchmarked hybrid retrieval with real embeddings. While interleaved retrieval with early termination is a theoretically sound approach, our results show that:

1. **RRF is the better choice for OpenClaw** given its dataset size and latency requirements
2. **Interleaved retrieval needs lower-level implementation** to show speed benefits
3. **Early termination has a real effectiveness cost** that must be considered

The research provides valuable insights into the trade-offs between different fusion strategies and demonstrates the importance of proper implementation and realistic benchmarking.
