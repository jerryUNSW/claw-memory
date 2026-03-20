# Cascaded Retrieval - Improved Results

## Summary of Improvements

We implemented two key improvements:
1. ✅ **FTS5 fallback to vector search** - Fixes query failures
2. ✅ **Increased stage 2 size** - 30 → 40 documents for better quality

---

## Results Comparison

### Before Improvements (Original)
- Latency: 15.49ms (3.52x speedup)
- NDCG: 0.2968 (-10.3% vs RRF)
- Query success: ~92% (25+ queries failed)
- Stage 2 size: 30 documents

### After Improvements (Current)
- Latency: 18.26ms (2.89x speedup)
- NDCG: 0.2986 (-9.8% vs RRF)
- Query success: **100%** ✅ (all queries return results)
- Stage 2 size: 40 documents

### Change from Improvements
- Latency: +2.77ms (+18% slower)
- NDCG: +0.0018 (+0.6% improvement)
- Query success: +8% (all queries now work)

---

## Analysis

### What Worked ✅

1. **FTS5 Fallback is Working**
   - All 323 queries now return results (100% success rate)
   - ~25 queries that previously failed now use vector fallback
   - Examples: "Breast Cancer & Alcohol", "Dr. Dean Ornish", "Parkinson's disease"

2. **Stage 2 Size Increase Helps Slightly**
   - 40 documents vs 30 provides more candidates for final ranking
   - NDCG improved by 0.6% (0.2968 → 0.2986)

### What Didn't Work as Expected ⚠️

1. **Fallback Adds Latency**
   - Stage 1 increased from 3.1ms → 6.3ms (2x slower)
   - Vector fallback is more expensive than BM25
   - ~25 queries use fallback, adding overhead

2. **NDCG Improvement is Modest**
   - Expected +4% from both improvements
   - Actual: +0.6% improvement
   - Still 9.8% below RRF baseline

3. **Speedup Decreased**
   - From 3.52x → 2.89x
   - Still good, but less impressive

---

## Stage Breakdown

### Before Improvements
```
Stage 1 (BM25):      3.1ms  (20%)
Stage 2 (Vector):   12.3ms  (79%)
Stage 3 (Hybrid):    0.1ms  (1%)
Total:              15.5ms
```

### After Improvements
```
Stage 1 (BM25+Fallback):  6.3ms  (34%)  ← 2x slower due to fallback
Stage 2 (Vector):        11.9ms  (65%)  ← Slightly faster (40 vs 30 docs)
Stage 3 (Hybrid):         0.1ms  (1%)
Total:                   18.3ms
```

**Key observation:** Stage 1 is now the bottleneck (34% of time), not Stage 2.

---

## Effectiveness Metrics

| Metric | RRF | Cascaded (Before) | Cascaded (After) | Change |
|--------|-----|-------------------|------------------|--------|
| **NDCG@10** | 0.3309 | 0.2968 | **0.2986** | +0.6% |
| Recall@10 | 0.1631 | 0.1431 | 0.1467 | +2.5% |
| Precision@10 | 0.2526 | 0.2864 | 0.2870 | +0.2% |
| MAP@10 | 0.1186 | 0.1094 | 0.1103 | +0.8% |
| MRR@10 | 0.5208 | 0.4814 | 0.4835 | +0.4% |

**Observation:** Small improvements across all metrics, but not the +4% we hoped for.

---

## Why NDCG Didn't Improve More?

### Hypothesis 1: Fallback Queries Are Hard
- Queries that fail FTS5 are often single words or proper nouns
- Examples: "Alli", "Fosamax", "okra", "Zoloft"
- These may not have good vector representations
- Vector-only search may not find relevant documents

### Hypothesis 2: Stage 1 Filtering Is Too Aggressive
- BM25-only filtering (100 docs) may miss semantically relevant documents
- Even with 40 docs in stage 2, we may have already lost good candidates
- Need hybrid scoring earlier in the pipeline

### Hypothesis 3: Stage 2 Size Still Too Small
- 40 documents may not be enough
- Try 50 or 60 for better quality

---

## Recommendations

### Option A: Accept Current Results (Recommended)

**Pros:**
- 2.89x speedup is still significant
- 100% query success rate
- 9.8% NDCG drop is acceptable for many applications
- Production-ready

**Cons:**
- Not as fast as original (18ms vs 15ms)
- NDCG improvement was modest

**Verdict:** Deploy this version if 18ms latency and 9.8% NDCG drop are acceptable.

### Option B: Optimize Fallback (Medium Effort)

**Idea:** Cache vector embeddings for common single-word queries

```python
# Pre-compute embeddings for common queries
query_cache = {
    'Alli': precomputed_embedding,
    'Fosamax': precomputed_embedding,
    # ...
}

def _stage1_vector_fallback(self, query):
    if query in query_cache:
        query_embedding = query_cache[query]  # Fast lookup
    else:
        query_embedding = self.model.encode(query)  # Compute on-the-fly
    # ... rest of fallback logic
```

**Expected:** Stage 1 latency 6.3ms → 4.5ms, total 18ms → 16ms

### Option C: Hybrid Stage 1 (High Effort)

**Idea:** Use lightweight hybrid scoring in stage 1 instead of BM25-only

```python
def _stage1_hybrid_light(self, query):
    # Get top-200 from BM25
    bm25_results = fts5_search(query, limit=200)
    
    # Quick vector scoring (approximate or cached)
    for doc in bm25_results:
        doc.approx_vector = get_approximate_vector(doc.id)
        doc.stage1_score = 0.7 * doc.bm25 + 0.3 * doc.approx_vector
    
    # Return top-100 by hybrid score
    return sorted(bm25_results)[:100]
```

**Expected:** NDCG 0.299 → 0.315 (+5%), latency 18ms → 22ms

### Option D: Increase Stage 2 Size Further (Low Effort)

**Idea:** Try 100 → 50 → 10 or 100 → 60 → 10

**Expected:** NDCG 0.299 → 0.305-0.310, latency 18ms → 20-22ms

---

## Final Recommendation

**Deploy Option A (current version) if:**
- 18ms latency meets requirements (<20ms for OpenClaw)
- 9.8% NDCG drop is acceptable
- 100% query success is important

**Try Option D (increase stage 2 to 50) if:**
- Can tolerate 20-22ms latency
- Want to get closer to 0.31 NDCG (7% drop)
- Low effort (5 minutes to test)

**Pursue Option C (hybrid stage 1) if:**
- Need <8% NDCG drop
- Can tolerate 22ms latency
- Have time for more complex implementation

---

## Comparison to All Methods

| Method | Latency | NDCG | Speedup | Status |
|--------|---------|------|---------|--------|
| RRF (baseline) | 52.9ms | 0.331 | 1.00x | Production |
| Interleaved (Python) | 56.0ms | 0.312 | 0.94x | Failed |
| Cascaded (original) | 15.5ms | 0.297 | 3.52x | Good but failures |
| **Cascaded (improved)** | **18.3ms** | **0.299** | **2.89x** | **Best overall** |

---

## Conclusion

The improvements successfully achieved:
- ✅ 100% query success rate (no more failures)
- ✅ 2.89x speedup (still significant)
- ✅ Slight NDCG improvement (+0.6%)

Trade-offs:
- ⚠️ Slower than original (18ms vs 15ms)
- ⚠️ NDCG improvement less than expected (+0.6% vs +4% hoped)

**Overall verdict:** This is a production-ready solution that balances speed, quality, and reliability. The 100% query success rate is valuable, and 2.89x speedup with 9.8% NDCG drop is acceptable for most applications.

**Next step:** Test Option D (stage 2 size = 50) to see if we can get to 0.305-0.310 NDCG with 20-22ms latency.
