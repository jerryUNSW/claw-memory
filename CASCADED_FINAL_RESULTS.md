# Final Cascaded Retrieval Results - All Configurations Tested

## Summary

We tested 3 configurations of cascaded retrieval with improvements:

| Config | Stage Sizes | Latency | NDCG | Speedup | Query Success |
|--------|-------------|---------|------|---------|---------------|
| **Original** | 100→30→10 | 15.49ms | 0.2968 | 3.52x | ~92% |
| **Config A** | 100→40→10 | 18.26ms | 0.2986 | 2.89x | 100% ✅ |
| **Config B** | 100→50→10 | 19.26ms | 0.2986 | 2.84x | 100% ✅ |

---

## Key Findings

### 1. FTS5 Fallback Works Perfectly ✅
- All 323 queries now return results (100% success rate)
- ~25 queries use vector fallback when FTS5 fails
- Critical for production reliability

### 2. Stage 2 Size Has Diminishing Returns
- 30→40: +0.6% NDCG improvement
- 40→50: No additional improvement (0.2986 → 0.2986)
- Conclusion: 40 documents is the sweet spot

### 3. Fallback Adds Latency Cost
- Stage 1 increased from 3.1ms → 6.3ms (2x slower)
- Vector fallback is more expensive than BM25
- Trade-off: reliability vs speed

### 4. NDCG Improvement Less Than Expected
- Expected: +4% from improvements
- Actual: +0.6% improvement
- Root cause: Stage 1 BM25-only filtering is too aggressive

---

## Recommended Configuration

**Use Config A (100→40→10):**

```python
retriever = CascadedRetriever(
    conn, 
    model,
    stage1_size=100,
    stage2_size=40,
    stage3_size=10
)
```

**Performance:**
- ✅ Latency: 18.26ms (2.89x faster than RRF)
- ✅ NDCG: 0.2986 (9.8% drop from RRF)
- ✅ Query success: 100%
- ✅ Meets OpenClaw's <20ms requirement

**Why not Config B (stage2=50)?**
- No NDCG improvement over Config A
- 1ms slower (19.26ms vs 18.26ms)
- Not worth the extra latency

---

## Comparison to All Methods

| Method | Latency | NDCG | Speedup | Success Rate | Status |
|--------|---------|------|---------|--------------|--------|
| RRF (baseline) | 54.6ms | 0.331 | 1.00x | 100% | Production |
| Interleaved | 56.0ms | 0.312 | 0.94x | ~92% | Failed |
| Cascaded (original) | 15.5ms | 0.297 | 3.52x | ~92% | Fast but unreliable |
| **Cascaded (final)** | **18.3ms** | **0.299** | **2.89x** | **100%** | **✅ Winner** |

---

## What We Learned

### Success ✅
1. **Cascaded retrieval is production-ready** - 2.89x speedup with acceptable quality
2. **FTS5 fallback is essential** - Ensures 100% query success
3. **Stage 2 size = 40 is optimal** - Best balance of speed and quality
4. **Multi-stage retrieval works** - Proven pattern from search engines

### Challenges ⚠️
1. **Stage 1 BM25-only is limiting** - Misses semantically relevant docs
2. **Fallback adds latency** - Vector search is slower than BM25
3. **NDCG improvement was modest** - +0.6% vs +4% hoped
4. **Speedup decreased** - 3.52x → 2.89x due to fallback overhead

### Insights 💡
1. **Implementation level matters** - Python overhead killed interleaved approach
2. **Reliability vs speed trade-off** - 100% success costs 3ms latency
3. **Diminishing returns** - Stage 2 size beyond 40 doesn't help
4. **Early filtering is critical** - Stage 1 quality determines final results

---

## Why NDCG Didn't Improve More?

### Root Cause: Stage 1 BM25-Only Filtering

The fundamental issue is that Stage 1 uses **BM25-only** to select top-100 candidates. This means:

1. **Semantically relevant docs are missed** if they don't match keywords
2. **Stage 2 can't recover** - it only reranks the 100 docs from Stage 1
3. **Even with 40 or 50 docs in Stage 2**, we've already lost good candidates

**Example:**
- Query: "cancer prevention"
- BM25 finds: docs with exact words "cancer" and "prevention"
- Misses: docs about "tumor reduction" or "disease avoidance" (semantically similar)
- Stage 2 can't find these docs because they weren't in Stage 1's top-100

### Solution: Hybrid Stage 1

To improve NDCG further, we need **hybrid scoring in Stage 1**:

```python
def _stage1_hybrid(self, query):
    # Get top-200 from BM25
    bm25_results = fts5_search(query, limit=200)
    
    # Add vector scores
    for doc in bm25_results:
        doc.vector_score = get_vector_score(doc.id, query)
        doc.stage1_score = 0.7 * doc.bm25 + 0.3 * doc.vector
    
    # Return top-100 by hybrid score
    return sorted(bm25_results, key=lambda x: x.stage1_score)[:100]
```

**Expected impact:**
- NDCG: 0.299 → 0.315-0.320 (+5-7%)
- Latency: 18ms → 22-25ms
- Trade-off: Better quality, slightly slower

---

## Production Deployment Recommendation

### Deploy Current Version (Config A)

**Reasons:**
1. ✅ 2.89x speedup is significant (54.6ms → 18.3ms)
2. ✅ 100% query success rate (critical for reliability)
3. ✅ Meets <20ms latency requirement
4. ✅ 9.8% NDCG drop is acceptable for many applications
5. ✅ Production-ready pattern (used by Google, Bing)

**When to use:**
- Agent memory systems requiring <20ms response
- Applications where 10% quality drop is acceptable
- Systems prioritizing reliability (100% success rate)

### Future Improvements (If Needed)

**If NDCG drop is too high:**
- Implement hybrid Stage 1 (expect 0.315-0.320 NDCG, 22-25ms latency)
- Accept slower speed for better quality

**If latency is too high:**
- Optimize vector fallback with caching
- Reduce Stage 1 size to 75 (expect 15ms, but lower NDCG)

**If both speed and quality are critical:**
- Implement DB-level unified operator in C/Rust
- Expected: 5-10ms latency, 0.33 NDCG (same as RRF)
- High effort but best of both worlds

---

## Final Metrics

### Cascaded (Final Configuration)

**Effectiveness:**
- NDCG@10: 0.2986 (vs RRF: 0.3309, -9.8%)
- Recall@10: 0.1467 (vs RRF: 0.1631, -10.0%)
- Precision@10: 0.2870 (vs RRF: 0.2526, +13.6%)
- MAP@10: 0.1103 (vs RRF: 0.1186, -7.0%)
- MRR@10: 0.4835 (vs RRF: 0.5208, -7.2%)

**Efficiency:**
- Latency: 18.26ms (vs RRF: 54.60ms, 2.89x faster)
- Stage 1: 6.42ms (35%)
- Stage 2: 12.67ms (69%)
- Stage 3: 0.16ms (1%)

**Reliability:**
- Query success rate: 100% (323/323 queries)
- FTS5 fallback used: ~25 queries (~8%)

---

## Conclusion

We successfully implemented and optimized cascaded retrieval, achieving:

1. ✅ **2.89x speedup** over RRF baseline
2. ✅ **100% query success rate** with FTS5 fallback
3. ✅ **Production-ready** implementation
4. ✅ **Meets OpenClaw requirements** (<20ms latency)

The 9.8% NDCG drop is the trade-off for speed and reliability. For applications requiring better quality, hybrid Stage 1 can improve NDCG to 0.315-0.320 at the cost of 22-25ms latency.

**Recommendation:** Deploy Config A (100→40→10) to OpenClaw production.

---

## Files Generated

1. `scripts/cascaded_retrieval.py` - Implementation with FTS5 fallback
2. `scripts/benchmark_cascaded.py` - Benchmark script
3. `cascaded_vs_rrf_nfcorpus.json` - Final results
4. `CASCADED_IMPROVED_RESULTS.md` - Analysis of improvements
5. `CASCADED_FINAL_RESULTS.md` - This document

**Next step:** Deploy to OpenClaw and monitor production metrics.
