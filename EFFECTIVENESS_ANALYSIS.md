# Understanding the Effectiveness Difference

## Your Question: Are They Really the Same?

**Short answer**: No, they can have **different effectiveness** in general. In our benchmark, they happened to return identical results due to specific conditions.

---

## Why They Got 100% Overlap in Our Test

### 1. **Small Dataset (30 chunks)**
Both methods explored nearly the entire dataset:
- RRF: Fetched 30-34 results (almost everything)
- Interleaved: Fetched 20-24 results (still most of it)

When you're looking at 2/3 of a tiny dataset, you'll find the same top-10.

### 2. **Simulated Vector Search**
We used `ORDER BY updated_at DESC` as a proxy for semantic similarity. This means:
- Vector scores are deterministic (based on recency)
- No actual semantic understanding
- Both methods see the same "vector" ordering

### 3. **Same Scoring Formula**
Both use: `hybrid_score = 0.5 * vector_score + 0.3 * bm25_score`

---

## When They WILL Differ (Real-World Scenarios)

### Scenario 1: Large Dataset
```
Database: 10,000 chunks

RRF:
- Fetches top-100 from FTS5
- Fetches top-100 from Vector
- Merges 200 results
- Returns top-10

Interleaved:
- Fetches ~30 results total (early termination)
- Returns top-10

Result: Different top-10 because interleaved didn't see 
        documents ranked 31-100 in either index!
```

**Example**:
- Document X is ranked #80 in FTS5, #5 in Vector
- RRF sees it (fetches top-100 from both)
- Interleaved might miss it (stops at ~30 fetches)
- **Different results!**

### Scenario 2: Real Vector Embeddings
```
With actual embeddings:
- Vector scores are query-dependent
- Different queries → different vector rankings
- More variability in which docs appear in top-100

Interleaved might miss a document that:
- Has mediocre FTS5 rank (#60)
- Has great vector similarity (#8)
- Would score high in hybrid ranking

RRF would catch it, Interleaved might not.
```

### Scenario 3: Skewed Score Distributions
```
Query: "machine learning optimization"

FTS5 top-10: All have BM25 scores 0.9-1.0 (very relevant)
Vector top-10: Scores 0.5-0.7 (moderate similarity)

If interleaved stops early (after 20 fetches):
- Might miss a doc ranked #50 in FTS5, #15 in Vector
- That doc could have high hybrid score
- RRF would include it
```

---

## The Trade-off

### RRF (Exhaustive)
```python
# Fetches top-K from EACH index (e.g., K=100)
fts_top_100 = fetch_fts5(query, limit=100)
vec_top_100 = fetch_vector(query, limit=100)

# Merges ALL candidates
all_candidates = merge(fts_top_100, vec_top_100)  # Up to 200 docs

# Ranks and returns top-10
return rank(all_candidates)[:10]
```

**Pros**: 
- Considers more candidates (higher recall)
- More likely to find the "true" top-10

**Cons**: 
- Fetches 200 results to return 10 (wasteful)
- Slower

### Interleaved (Approximate)
```python
# Alternates between indexes, stops early
while not_stable:
    fetch_2_from_fts5()
    fetch_1_from_vector()
    update_top_k()
    
    if top_k_stable_for_N_iterations:
        break  # Early termination!

return top_k
```

**Pros**: 
- Much faster (13.91x in our test)
- Fetches only what's needed

**Cons**: 
- Might miss some candidates (lower recall)
- Top-10 is approximate, not guaranteed optimal

---

## Effectiveness Metrics to Measure

### 1. **Overlap@K**
What % of documents are in both result sets?
```
Our test: 100% (identical)
Real-world: 85-95% typical
```

### 2. **Rank Correlation**
How similar are the rankings?
```
Our test: Perfect (0.0 difference)
Real-world: 0.8-0.9 Kendall's tau typical
```

### 3. **NDCG (Normalized Discounted Cumulative Gain)**
Quality of ranking with relevance labels
```
Requires: Human-labeled relevance judgments
Expected: RRF slightly higher (more candidates)
```

### 4. **Recall@K**
What % of truly relevant docs are retrieved?
```
Requires: Ground truth relevant docs
Expected: RRF higher (exhaustive search)
```

---

## Visualizing the Difference

```
Dataset: 1000 chunks
Query: "database optimization"

FTS5 Ranking:          Vector Ranking:
1. Doc A (BM25=0.95)   1. Doc B (sim=0.92)
2. Doc C (BM25=0.90)   2. Doc D (sim=0.88)
3. Doc E (BM25=0.85)   3. Doc A (sim=0.85)  ← Also in FTS5 top
...                    ...
50. Doc X (BM25=0.40)  10. Doc X (sim=0.75)  ← High vector score!
...                    ...

RRF (fetches top-100 from each):
✓ Sees Doc X (rank 50 in FTS5, rank 10 in Vector)
✓ Hybrid score: 0.5*0.75 + 0.3*0.40 = 0.495
✓ Doc X makes it to top-10!

Interleaved (stops after ~30 fetches):
✗ Stops before reaching rank 50 in FTS5
✗ Misses Doc X entirely
✗ Different top-10!
```

---

## So What's Really Happening?

### In Our Benchmark:
We're **not** just "speeding up with a priority queue" - we're using **early termination** which is an **approximation algorithm**.

### The Key Insight:
```
RRF = Exhaustive (optimal but slow)
Interleaved = Approximate (fast but might miss some docs)
```

### Why 100% Overlap in Our Test?
1. Dataset too small (30 chunks)
2. Both methods saw most of the data
3. Simulated vectors (deterministic)

### What to Expect in Production?
```
Dataset: 10,000+ chunks
Real embeddings: Query-dependent vectors

Expected results:
- Overlap: 85-95% (not 100%)
- Top-1 match: 80-90%
- Rank differences: Small but measurable
- Speed: 10-50x faster
- Effectiveness: Slightly lower (acceptable trade-off)
```

---

## The Research Question

**Is the effectiveness loss acceptable for the speed gain?**

That's what you need to evaluate:

1. **Measure on larger dataset** (1000+ chunks)
2. **Use real embeddings** (not simulated)
3. **Get relevance labels** (human judgments)
4. **Compare NDCG/Recall** (not just overlap)

Then decide: Is 5% effectiveness loss worth 20x speedup?

---

## Bottom Line

**No, they're not exactly the same effectiveness.**

- **Our test**: 100% overlap (special case - tiny dataset)
- **Real-world**: 85-95% overlap expected
- **Trade-off**: Speed vs. completeness

Interleaved is an **approximation algorithm** that trades a small amount of effectiveness for large efficiency gains. The question is whether that trade-off is worth it for your use case.
