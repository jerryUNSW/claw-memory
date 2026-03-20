# Research Gap & Interleaved Index Design

## 🎯 The Core Research Gap

### Current Problem: Post-Process Fusion (OpenClaw's Approach)

OpenClaw strikes a balance between three factors:
- **Keyword precision** (FTS5 with BM25)
- **Semantic understanding** (Vector similarity)
- **Recency** (Temporal decay)

**But the fusion happens AFTER retrieval:**

```
┌─────────────────────────────────────────────┐
│  Application Layer (JavaScript)             │
│                                             │
│  1. Run FTS5 query → 100 results           │
│  2. Run Vector query → 100 results         │
│  3. Merge 200 results in memory            │
│  4. Compute hybrid scores                  │
│  5. Sort by score                          │
│  6. Return top 10                          │
│                                             │
│  ❌ Problem: Fusion happens AFTER retrieval│
└─────────────────────────────────────────────┘
         ↓              ↓
    ┌─────────┐    ┌──────────┐
    │  FTS5   │    │  Vector  │
    │ (100)   │    │  (100)   │
    └─────────┘    └──────────┘
```

**Key Issues:**

1. ❌ **No early termination** - Must fetch 100 from each (200 total)
2. ❌ **Wasted computation** - Many low-scoring results never used
3. ❌ **No cross-optimization** - Query planner can't optimize across both indexes
4. ❌ **Double I/O** - Two separate index scans
5. ❌ **Late fusion** - Can't prune bad candidates early
6. ❌ **Memory overhead** - 200 results in memory, only need 10

---

## 💡 The Research Opportunity: Integrated Interleaved Retrieval

### Vision: Unified Operator with Interleaved Traversal

```
┌─────────────────────────────────────────────┐
│  SQLite Virtual Table (C code)              │
│                                             │
│  ┌─────────────────────────────────────┐  │
│  │  Unified Operator (vtab_hybrid)     │  │
│  │                                     │  │
│  │  ┌──────────┐      ┌──────────┐   │  │
│  │  │FTS5      │      │Vector    │   │  │
│  │  │Cursor    │◄────►│Cursor    │   │  │
│  │  └────┬─────┘      └────┬─────┘   │  │
│  │       │                 │          │  │
│  │       └────────┬────────┘          │  │
│  │                ↓                   │  │
│  │      Priority Queue                │  │
│  │      (Interleaved)                 │  │
│  │                ↓                   │  │
│  │      Compute hybrid_score          │  │
│  │      on-the-fly                    │  │
│  │                ↓                   │  │
│  │      Early termination             │  │
│  │      (stop when top-10 stable)     │  │
│  │                ↓                   │  │
│  │      Return 10 results             │  │
│  └─────────────────────────────────────┘  │
└─────────────────────────────────────────────┘
```

**Benefits:**

1. ✅ **Early termination** - Stop when top-k is stable
2. ✅ **Efficient** - Only compute what's needed
3. ✅ **Integrated** - Single query plan
4. ✅ **Single I/O pass** - Interleaved traversal
5. ✅ **Early pruning** - Discard bad candidates immediately
6. ✅ **Lower memory** - Only keep top-k in memory

---

## 🔬 Specific Research Gaps

### Gap 1: Interleaved Index Traversal

**Current (Sequential Fetch):**
```python
# Step 1: Fetch ALL from FTS5
fts_results = []
for i in range(100):
    fts_results.append(fts_cursor.next())

# Step 2: Fetch ALL from Vector
vec_results = []
for i in range(100):
    vec_results.append(vec_cursor.next())

# Step 3: Merge in application memory
merged = rrf_merge(fts_results, vec_results)

# Step 4: Return top 10
return merged[:10]

# Problem: Fetched 200, only needed 10!
```

**Your Research (Interleaved Traversal):**
```python
# Initialize both cursors
fts_cursor = init_fts_cursor(query)
vec_cursor = init_vec_cursor(query_embedding)
priority_queue = MinHeap(capacity=10)

# Interleaved traversal
while not done:
    # Peek at next candidates from both cursors
    fts_candidate = fts_cursor.peek()
    vec_candidate = vec_cursor.peek()
    
    # Compute hybrid scores on-the-fly
    fts_hybrid_score = (
        alpha * fts_candidate.text_score +
        beta * lookup_vector_score(fts_candidate.id) +
        gamma * temporal_decay(fts_candidate.age)
    )
    
    vec_hybrid_score = (
        alpha * vec_candidate.vector_score +
        beta * lookup_text_score(vec_candidate.id) +
        gamma * temporal_decay(vec_candidate.age)
    )
    
    # Take the better candidate
    if fts_hybrid_score > vec_hybrid_score:
        candidate = fts_cursor.next()
        score = fts_hybrid_score
    else:
        candidate = vec_cursor.next()
        score = vec_hybrid_score
    
    # Insert into priority queue (keeps top-k)
    priority_queue.insert(candidate, score)
    
    # Early termination check
    if top_k_is_stable(priority_queue, k=10):
        break  # Stop early!
    
    # Safety: Don't scan forever
    if total_scanned > max_candidates:
        break

return priority_queue.top(10)
```

**Research Question:**
> How much faster is interleaved traversal vs sequential fetch?

**Hypothesis:** 40-50% latency reduction

---

### Gap 2: Early Termination

**Current (No Early Stop):**
```python
# Must fetch ALL candidates
fts_results = fetch_all(100)  # Can't stop early
vec_results = fetch_all(100)  # Can't stop early
merged = merge(fts_results, vec_results)
return merged[:10]

# Scanned: 200 candidates
# Needed: 10 results
# Waste: 190 candidates (95%)
```

**Your Research (Early Termination):**
```python
def top_k_is_stable(priority_queue, k=10):
    """
    Check if top-k results are stable
    (no new candidate can enter top-k)
    """
    if len(priority_queue) < k:
        return False
    
    # Get the k-th best score (threshold)
    kth_score = priority_queue.get_kth_score(k)
    
    # Check if remaining candidates can beat threshold
    fts_max_possible = estimate_max_score(fts_cursor)
    vec_max_possible = estimate_max_score(vec_cursor)
    
    # If no remaining candidate can beat k-th score, we're done
    if fts_max_possible < kth_score and vec_max_possible < kth_score:
        return True
    
    return False
```

**Research Question:**
> How many candidates do we actually need to scan to get top-10?

**Hypothesis:** 20-30 candidates (vs 200 currently)

---

### Gap 3: Query Planning & Cost Estimation

**Current (No Cross-Index Optimization):**
```sql
-- SQLite sees these as two independent queries
SELECT * FROM chunks_fts WHERE MATCH 'query' LIMIT 100;
SELECT * FROM chunks_vec ORDER BY distance LIMIT 100;

-- Query planner can't optimize across both
-- No shared statistics
-- No cost-based decision making
```

**Your Research (Unified Query Planning):**
```c
// xBestIndex - Tell SQLite about index capabilities
static int hybridBestIndex(
    sqlite3_vtab *tab,
    sqlite3_index_info *pIdxInfo
) {
    double fts_cost = estimate_fts_cost(pIdxInfo);
    double vec_cost = estimate_vec_cost(pIdxInfo);
    
    // Estimate hybrid cost (less than sum of both)
    double hybrid_cost = fts_cost + vec_cost;
    
    // Apply synergy discount (interleaved is more efficient)
    hybrid_cost *= 0.6;  // 40% reduction
    
    // Consider selectivity
    if (has_fts_constraint(pIdxInfo)) {
        // FTS5 is selective, prioritize it
        hybrid_cost *= 0.8;
    }
    
    pIdxInfo->estimatedCost = hybrid_cost;
    pIdxInfo->estimatedRows = 10;  // We return top-10
    
    return SQLITE_OK;
}
```

**Research Question:**
> Can SQLite's query planner make better decisions with unified cost estimates?

**Hypothesis:** Yes, especially for complex queries with multiple constraints

---

### Gap 4: Score Computation Location

**Current (Application-Level Scoring):**
```javascript
// Scoring happens in JavaScript (slow)
for (const doc of documents) {
    doc.hybridScore = (
        0.5 * doc.vectorScore +
        0.3 * doc.textScore +
        0.2 * temporalDecay(doc.age)
    );
}
documents.sort((a, b) => b.hybridScore - a.hybridScore);
```

**Your Research (Database-Level Scoring):**
```c
// Scoring happens in C (fast)
static double compute_hybrid_score(
    hybrid_cursor *cursor,
    double text_score,
    double vector_score,
    int64_t age_days
) {
    double temporal = exp(-cursor->lambda * age_days);
    
    return (
        cursor->alpha * vector_score +
        cursor->beta * text_score +
        cursor->gamma * temporal
    );
}
```

**Research Question:**
> How much faster is C-level scoring vs JavaScript?

**Hypothesis:** 5-10x faster for score computation

---

## 🎯 Design: Interleaved Index Method

### Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│  vtab_hybrid (SQLite Virtual Table)                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │  Dual Cursor State                          │  │
│  │  ┌──────────────┐    ┌──────────────┐     │  │
│  │  │ FTS5 Cursor  │    │ Vector Cursor│     │  │
│  │  │              │    │              │     │  │
│  │  │ - position   │    │ - position   │     │  │
│  │  │ - stmt       │    │ - stmt       │     │  │
│  │  │ - exhausted  │    │ - exhausted  │     │  │
│  │  └──────────────┘    └──────────────┘     │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │  Priority Queue (Min-Heap)                  │  │
│  │  ┌────────────────────────────────────┐    │  │
│  │  │ [doc1, score=0.95]                 │    │  │
│  │  │ [doc2, score=0.89]                 │    │  │
│  │  │ [doc3, score=0.87]                 │    │  │
│  │  │ ...                                │    │  │
│  │  │ [doc10, score=0.72] ← threshold    │    │  │
│  │  └────────────────────────────────────┘    │  │
│  └─────────────────────────────────────────────┘  │
│                                                     │
│  ┌─────────────────────────────────────────────┐  │
│  │  Scoring Parameters                         │  │
│  │  - alpha (vector weight): 0.5               │  │
│  │  - beta (text weight): 0.3                  │  │
│  │  - gamma (temporal weight): 0.2             │  │
│  │  - lambda (decay rate): 0.01                │  │
│  └─────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

---

### Algorithm: Interleaved Traversal with Early Termination

```c
// Pseudo-code for the interleaved algorithm

struct hybrid_cursor {
    sqlite3_vtab_cursor base;
    
    // Dual cursors
    sqlite3_stmt *fts_stmt;
    sqlite3_stmt *vec_stmt;
    
    // Priority queue (min-heap, keeps top-k)
    struct {
        int64_t rowid;
        double score;
        char *snippet;
    } *heap;
    int heap_size;
    int heap_capacity;  // k (e.g., 10)
    
    // Scoring parameters
    double alpha;   // vector weight
    double beta;    // text weight
    double gamma;   // temporal weight
    double lambda;  // decay rate
    
    // State
    int total_scanned;
    int max_candidates;  // Safety limit (e.g., 200)
    bool fts_exhausted;
    bool vec_exhausted;
};

// Main algorithm
int hybridFilter(hybrid_cursor *cur, ...) {
    // Initialize both cursors
    init_fts_cursor(cur);
    init_vec_cursor(cur);
    
    // Interleaved traversal
    while (!should_stop(cur)) {
        // Get next candidates from both cursors
        candidate_t fts_cand = peek_fts(cur);
        candidate_t vec_cand = peek_vec(cur);
        
        // Compute hybrid scores
        double fts_score = compute_hybrid_score(cur, fts_cand);
        double vec_score = compute_hybrid_score(cur, vec_cand);
        
        // Choose better candidate
        candidate_t chosen;
        double chosen_score;
        
        if (fts_score > vec_score) {
            chosen = advance_fts(cur);
            chosen_score = fts_score;
        } else {
            chosen = advance_vec(cur);
            chosen_score = vec_score;
        }
        
        // Insert into priority queue
        heap_insert(cur->heap, chosen, chosen_score);
        cur->total_scanned++;
        
        // Check early termination
        if (can_terminate_early(cur)) {
            break;
        }
    }
    
    return SQLITE_OK;
}

// Early termination check
bool can_terminate_early(hybrid_cursor *cur) {
    // Need at least k results
    if (cur->heap_size < cur->heap_capacity) {
        return false;
    }
    
    // Get k-th best score (threshold)
    double threshold = cur->heap[cur->heap_capacity - 1].score;
    
    // Estimate max possible scores from remaining candidates
    double fts_max = estimate_max_fts_score(cur);
    double vec_max = estimate_max_vec_score(cur);
    
    // If no remaining candidate can beat threshold, stop
    if (fts_max < threshold && vec_max < threshold) {
        return true;
    }
    
    // Safety: Don't scan forever
    if (cur->total_scanned >= cur->max_candidates) {
        return true;
    }
    
    return false;
}

// Hybrid score computation
double compute_hybrid_score(hybrid_cursor *cur, candidate_t cand) {
    // Get scores from both indexes
    double text_score = get_text_score(cand);
    double vector_score = get_vector_score(cand);
    
    // Compute temporal decay
    int64_t age_days = compute_age_days(cand.timestamp);
    double temporal = exp(-cur->lambda * age_days);
    
    // Weighted combination
    return (
        cur->alpha * vector_score +
        cur->beta * text_score +
        cur->gamma * temporal
    );
}
```

---

### Key Design Decisions

#### 1. **Which Cursor to Advance?**

**Option A: Greedy (Choose Higher Score)**
```c
if (fts_score > vec_score) {
    advance_fts();
} else {
    advance_vec();
}
```
**Pros:** Simple, intuitive
**Cons:** May miss good candidates from the other cursor

**Option B: Round-Robin**
```c
if (iteration % 2 == 0) {
    advance_fts();
} else {
    advance_vec();
}
```
**Pros:** Fair, explores both
**Cons:** May waste time on low-scoring cursor

**Option C: Adaptive (Based on Recent Performance)**
```c
if (fts_recent_avg > vec_recent_avg) {
    advance_fts();
} else {
    advance_vec();
}
```
**Pros:** Adapts to query characteristics
**Cons:** More complex

**Recommendation:** Start with Option A (greedy), test Option C in ablation study

---

#### 2. **When to Stop? (Early Termination)**

**Condition 1: Top-k is Stable**
```c
// No remaining candidate can enter top-k
max_possible_score < kth_best_score
```

**Condition 2: Safety Limit**
```c
// Don't scan forever
total_scanned >= max_candidates (e.g., 200)
```

**Condition 3: Both Cursors Exhausted**
```c
fts_exhausted && vec_exhausted
```

**Recommendation:** Use all three conditions (OR logic)

---

#### 3. **How to Estimate Max Possible Score?**

**For FTS5:**
```c
double estimate_max_fts_score(hybrid_cursor *cur) {
    // Assume next FTS5 result has best possible BM25
    // (decreasing order, so next is upper bound)
    double max_text_score = peek_fts_score(cur);
    
    // Assume it also has perfect vector match
    double max_vector_score = 1.0;
    
    // Assume it's brand new
    double max_temporal = 1.0;
    
    return (
        cur->alpha * max_vector_score +
        cur->beta * max_text_score +
        cur->gamma * max_temporal
    );
}
```

**For Vector:**
```c
double estimate_max_vec_score(hybrid_cursor *cur) {
    // Assume next vector result has best possible similarity
    double max_vector_score = peek_vec_score(cur);
    
    // Assume it also has perfect text match
    double max_text_score = 1.0;
    
    // Assume it's brand new
    double max_temporal = 1.0;
    
    return (
        cur->alpha * max_vector_score +
        cur->beta * max_text_score +
        cur->gamma * max_temporal
    );
}
```

**Note:** These are **optimistic estimates** (upper bounds)

---

#### 4. **Priority Queue Implementation**

**Min-Heap (Keep Top-k)**
```c
struct heap_entry {
    int64_t rowid;
    double score;
    char *snippet;
};

void heap_insert(heap_entry *heap, int *size, int capacity, 
                 heap_entry new_entry) {
    if (*size < capacity) {
        // Heap not full, just insert
        heap[*size] = new_entry;
        (*size)++;
        heapify_up(heap, *size - 1);
    } else {
        // Heap full, replace min if new is better
        if (new_entry.score > heap[0].score) {
            heap[0] = new_entry;
            heapify_down(heap, 0, *size);
        }
    }
}
```

**Why min-heap?**
- Root is the k-th best score (threshold)
- Easy to check if new candidate beats threshold
- Efficient insertion: O(log k)

---

### Implementation Phases

#### Phase 1: Basic Interleaved Traversal (Week 3-4)

**Goal:** Prove correctness

```c
// Simplified version (no early termination yet)
while (total_scanned < 200) {
    if (fts_score > vec_score) {
        candidate = advance_fts();
    } else {
        candidate = advance_vec();
    }
    
    score = compute_hybrid_score(candidate);
    heap_insert(heap, candidate, score);
    total_scanned++;
}

return heap_top_k(heap, 10);
```

**Validation:**
- Compare results with current RRF
- Should return same top-10 (or very similar)

---

#### Phase 2: Add Early Termination (Week 5)

**Goal:** Improve efficiency

```c
while (total_scanned < 200) {
    // ... same as above ...
    
    // Add early termination check
    if (can_terminate_early(cursor)) {
        break;  // Stop early!
    }
}
```

**Measure:**
- How many candidates scanned? (expect 20-50 vs 200)
- Latency improvement? (expect 40-50%)

---

#### Phase 3: Optimize Score Computation (Week 6)

**Goal:** Reduce overhead

```c
// Cache vector scores to avoid repeated lookups
struct score_cache {
    int64_t rowid;
    double vector_score;
    double text_score;
};

// Batch score lookups
batch_lookup_scores(candidates, cache);
```

**Measure:**
- Score computation time
- Cache hit rate

---

#### Phase 4: Query Planning Integration (Week 7)

**Goal:** Let SQLite optimize

```c
// Implement xBestIndex
static int hybridBestIndex(...) {
    // Analyze constraints
    // Estimate costs
    // Provide hints to query planner
}
```

**Measure:**
- Query plan quality
- Cost estimation accuracy

---

## 📊 Expected Performance Improvements

### Baseline (Current RRF)

```
Query: "SQLite bug from yesterday"

FTS5 scan: 100 candidates (5ms)
Vector scan: 100 candidates (10ms)
Merge in JS: 200 → 10 (2ms)
Total: 17ms
```

### Target (Unified Operator)

```
Query: "SQLite bug from yesterday"

Interleaved scan: 25 candidates (8ms)
  ├─ FTS5: 15 candidates
  ├─ Vector: 10 candidates
  └─ Early termination at candidate 25

Total: 8ms (53% faster!)
```

### Breakdown of Improvements

| Optimization | Latency Reduction | Reason |
|--------------|-------------------|--------|
| **Interleaved traversal** | -20% | Single I/O pass |
| **Early termination** | -30% | Scan 25 vs 200 candidates |
| **C-level scoring** | -10% | Faster than JavaScript |
| **Better caching** | -5% | Reduce redundant lookups |
| **Total** | **-53%** | Combined effect |

---

## 🎯 Research Questions to Answer

### Primary Questions

1. **How much faster is interleaved vs sequential?**
   - Hypothesis: 40-50% latency reduction
   - Measure: P50, P95, P99 latency on 100K entries

2. **How many candidates do we actually need to scan?**
   - Hypothesis: 20-30 vs 200 currently
   - Measure: Average candidates scanned for top-10

3. **Does early termination hurt relevance?**
   - Hypothesis: No, NDCG@10 stays same or improves
   - Measure: NDCG@10, MRR on test set

### Secondary Questions

4. **What are optimal fusion weights?**
   - Grid search: α ∈ [0.3, 0.7], β ∈ [0.2, 0.5]
   - Measure: NDCG@10 on validation set

5. **Which cursor advancement strategy is best?**
   - Test: Greedy vs Round-Robin vs Adaptive
   - Measure: Latency and relevance

6. **How does it scale to 1M+ entries?**
   - Test on MS MARCO (8.8M passages)
   - Measure: Degradation curve

---

## 📋 Summary

### The Research Gap

**Current:** Post-process fusion (2 queries + JavaScript merge)
- ❌ No early termination
- ❌ Wasted computation
- ❌ No cross-optimization

**Your Research:** Integrated interleaved retrieval (1 unified query)
- ✅ Early termination
- ✅ Efficient traversal
- ✅ Query planner optimization

### Key Innovation

**Moving fusion from application layer into database layer** enables:
1. Interleaved index traversal
2. Early termination
3. Better query planning
4. Lower latency (40-50% reduction)
5. Better scalability (100K+ entries)

### Implementation Strategy

1. **Phase 1:** Basic interleaved traversal (prove correctness)
2. **Phase 2:** Add early termination (improve efficiency)
3. **Phase 3:** Optimize scoring (reduce overhead)
4. **Phase 4:** Query planning (enable optimization)

**This is your research contribution!** 🚀
