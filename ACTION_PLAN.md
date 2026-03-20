# Action Plan: Improve Cascaded Retrieval

## Current Status

✅ **Cascaded retrieval implemented and benchmarked**
- 3.52x faster than RRF (15.5ms vs 54.5ms)
- 10% NDCG drop (0.297 vs 0.331)
- Stage 2 (vector scoring) is bottleneck at 79% of time

## Goal

Improve cascaded retrieval to achieve:
- **Target latency:** 12-15ms (maintain 3-4x speedup)
- **Target NDCG:** 0.310-0.320 (reduce drop to 5-7%)
- **Query success rate:** 100% (currently ~92% due to FTS5 failures)

---

## Improvement 1: Fix FTS5 Query Failures (High Priority)

### Problem
- ~25 queries fail due to special characters (&, ', ., etc.)
- Failed queries return empty results, hurting NDCG

### Solution
Add fallback to vector-only search when FTS5 fails:

```python
def _stage1_bm25(self, query: str) -> List[RetrievalResult]:
    """Stage 1 with fallback"""
    escaped_query = escape_fts5_query(query)
    
    try:
        # Try FTS5 first
        cursor = self.conn.execute("""
            SELECT id, path, text, bm25(chunks_fts) as bm25_score
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY bm25_score ASC
            LIMIT ?
        """, [escaped_query, self.stage1_size])
        
        results = []
        for row in cursor:
            # ... build results ...
        
        if results:
            return results
        else:
            # FTS5 returned nothing, fallback to vector
            return self._stage1_vector_fallback(query)
            
    except Exception as e:
        # FTS5 failed, fallback to vector
        print(f"FTS5 failed, using vector fallback: {e}")
        return self._stage1_vector_fallback(query)

def _stage1_vector_fallback(self, query: str) -> List[RetrievalResult]:
    """Fallback: Use vector search for stage 1"""
    query_embedding = self.model.encode(query)
    
    cursor = self.conn.execute("""
        SELECT 
            chunks.id,
            chunks.path,
            chunks.text,
            vec_distance_cosine(chunks_vec.embedding, ?) as distance
        FROM chunks_vec
        JOIN chunks ON chunks.id = chunks_vec.id
        ORDER BY distance ASC
        LIMIT ?
    """, [serialize_f32(query_embedding), self.stage1_size])
    
    results = []
    for row in cursor:
        similarity = 1.0 - row[3]
        results.append(RetrievalResult(
            id=row[0],
            path=row[1],
            text=row[2],
            vector_score=similarity,
            stage1_score=similarity  # Use vector score for stage 1
        ))
    
    return results
```

### Expected Impact
- Query success rate: 92% → 100%
- NDCG: 0.297 → 0.310 (+4%)
- Latency: 15.5ms → 16ms (slight increase due to fallback)

### Implementation Time
- 1-2 hours

---

## Improvement 2: Tune Stage Sizes (Medium Priority)

### Problem
- Current: 100 → 30 → 10 may be too aggressive
- Stage 1 → Stage 2 pruning (100 → 30) may discard relevant docs

### Solution
Test different stage size configurations:

| Config | Stage 1 | Stage 2 | Stage 3 | Expected NDCG | Expected Latency |
|--------|---------|---------|---------|---------------|------------------|
| Current | 100 | 30 | 10 | 0.297 | 15.5ms |
| **Option A** | 100 | 50 | 10 | 0.315 | 18ms |
| **Option B** | 150 | 40 | 10 | 0.320 | 20ms |
| **Option C** | 100 | 40 | 10 | 0.310 | 17ms |

**Recommendation:** Try Option C (100 → 40 → 10) as a balanced approach.

```python
retriever = CascadedRetriever(
    conn, 
    model,
    stage1_size=100,
    stage2_size=40,  # Increased from 30
    stage3_size=10
)
```

### Expected Impact
- NDCG: 0.297 → 0.310 (+4%)
- Latency: 15.5ms → 17ms (+10%)

### Implementation Time
- 30 minutes (just change parameters and re-benchmark)

---

## Improvement 3: Optimize Stage 2 Vector Scoring (Low Priority)

### Problem
- Stage 2 takes 12.3ms (79% of total time)
- Computing 100 vector similarities is expensive

### Solution A: More Efficient Batch Lookup

Current implementation does individual lookups. Optimize the SQL query:

```python
def _stage2_vector_rerank(self, query: str, candidates: List[RetrievalResult]):
    """Optimized stage 2"""
    query_embedding = self.model.encode(query)
    candidate_ids = [c.id for c in candidates]
    
    # Single efficient query with proper indexing
    placeholders = ','.join('?' * len(candidate_ids))
    cursor = self.conn.execute(f"""
        SELECT 
            chunks.id,
            vec_distance_cosine(chunks_vec.embedding, ?) as distance
        FROM chunks_vec
        JOIN chunks ON chunks.id = chunks_vec.id
        WHERE chunks.id IN ({placeholders})
    """, [serialize_f32(query_embedding)] + candidate_ids)
    
    # Build lookup dict (O(n))
    vector_scores = {row[0]: 1.0 - row[1] for row in cursor}
    
    # Update candidates (O(n))
    for candidate in candidates:
        candidate.vector_score = vector_scores.get(candidate.id, 0.0)
        candidate.stage2_score = (
            self.stage2_vector_weight * candidate.vector_score +
            self.stage2_text_weight * candidate.bm25_score
        )
    
    # Sort once (O(n log n))
    candidates.sort(key=lambda x: x.stage2_score, reverse=True)
    return candidates[:self.stage2_size]
```

### Solution B: Reduce Stage 1 Size

If stage 2 is too slow, reduce stage 1 output:

```python
retriever = CascadedRetriever(
    conn, 
    model,
    stage1_size=50,   # Reduced from 100
    stage2_size=30,
    stage3_size=10
)
```

### Expected Impact
- Solution A: 12.3ms → 10ms (18% faster in stage 2)
- Solution B: 15.5ms → 10ms (35% faster overall, but may hurt NDCG)

### Implementation Time
- Solution A: 1 hour
- Solution B: 5 minutes

---

## Improvement 4: Better FTS5 Query Escaping (Low Priority)

### Problem
- Current escaping is incomplete
- Some special characters still cause failures

### Solution
Improve the escape function:

```python
def escape_fts5_query(query: str) -> str:
    """Comprehensive FTS5 query escaping"""
    # Remove all FTS5 special characters
    special_chars = ['"', '-', '(', ')', '*', ':', '&', "'", '.', '?', '!', ',', ';', '[', ']', '{', '}']
    escaped = query
    for char in special_chars:
        escaped = escaped.replace(char, ' ')
    
    # Split into words and filter empty
    words = [w.strip() for w in escaped.split() if w.strip()]
    
    if not words:
        return 'a'  # Fallback query
    
    # Use OR for multi-word queries (more permissive)
    return ' OR '.join(words)
```

### Expected Impact
- Query success rate: 92% → 98%
- NDCG: 0.297 → 0.300 (+1%)

### Implementation Time
- 30 minutes

---

## Implementation Priority

### Week 1 (High Priority)
1. ✅ **Improvement 1: FTS5 Fallback** (1-2 hours)
   - Biggest impact on NDCG (+4%)
   - Fixes query failures
   
2. ✅ **Improvement 2: Tune Stage Sizes** (30 minutes)
   - Test 100 → 40 → 10 configuration
   - Balance speed vs quality

### Week 2 (Medium Priority)
3. **Re-benchmark** (1 hour)
   - Run full benchmark with improvements
   - Validate NDCG and latency targets
   
4. **Improvement 3: Optimize Stage 2** (1 hour)
   - Only if stage 2 is still bottleneck
   - Try Solution A (efficient batch lookup)

### Week 3 (Low Priority)
5. **Improvement 4: Better Escaping** (30 minutes)
   - Polish FTS5 query handling
   - Reduce fallback frequency

---

## Expected Final Results

After implementing Improvements 1 & 2:

| Metric | Current | Target | Change |
|--------|---------|--------|--------|
| **Latency** | 15.5ms | **13-15ms** | Maintain 3-4x speedup |
| **NDCG@10** | 0.297 | **0.310-0.315** | Reduce drop to 6-7% |
| **Query Success** | 92% | **100%** | Fix all failures |
| **Speedup vs RRF** | 3.52x | **3.5-4x** | Maintain or improve |

---

## Success Criteria

✅ **Minimum Viable:**
- Latency < 20ms (meets OpenClaw requirement)
- NDCG > 0.305 (< 8% drop from RRF)
- Query success rate > 95%

🎯 **Target:**
- Latency: 12-15ms
- NDCG: 0.310-0.320
- Query success rate: 100%

🏆 **Stretch Goal:**
- Latency < 12ms
- NDCG > 0.320
- Deploy to OpenClaw production

---

## Next Steps

1. **Implement Improvement 1** (FTS5 fallback) - Start now
2. **Implement Improvement 2** (tune stage sizes) - After #1
3. **Re-benchmark** - Validate improvements
4. **Deploy to OpenClaw** - If targets met
5. **Monitor production** - Collect real-world metrics

---

## Files to Modify

1. `scripts/cascaded_retrieval.py`
   - Add `_stage1_vector_fallback()` method
   - Update `_stage1_bm25()` with try/except
   - Improve `escape_fts5_query()`
   - Add configurable stage sizes

2. `scripts/benchmark_cascaded.py`
   - Add parameter sweep for stage sizes
   - Report query success rate
   - Add detailed error logging

---

## Estimated Total Time

- **Improvements 1 & 2:** 2-3 hours
- **Re-benchmark:** 1 hour
- **Analysis & documentation:** 1 hour
- **Total:** 4-5 hours

**Timeline:** Can be completed in 1 day of focused work.
