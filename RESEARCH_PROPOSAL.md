# Research Proposal: Unified Interleaved SQLite Operator for OpenClaw
## Solving the Hybrid Gap in Agent-Native Storage

**Research Period:** Q2 2026  
**Principal Focus:** Eliminating the FTS5/sqlite-vec retrieval bottleneck through unified indexing

---

## 1. Problem Statement

### 1.1 The Current Architecture Limitation

OpenClaw's memory system (`memory-core`) currently operates two **independent** retrieval pipelines:

```
User Query → [FTS5 Search] → Results_A
          ↓
          → [vec0 Search] → Results_B
          ↓
          → [RRF Merge] → Final Results
```

**Critical Inefficiencies:**
- **Double I/O Penalty:** Two separate B-tree traversals
- **Late Fusion:** Ranking happens *after* retrieval (no early pruning)
- **No Cross-Index Optimization:** Cannot express "semantic similarity WHERE keyword EXISTS"
- **Scalability Ceiling:** RRF complexity grows O(n+m) with result set sizes

### 1.2 The "Hybrid Gap"

The fundamental disconnect: **Lexical precision** (FTS5) and **semantic understanding** (vectors) are treated as orthogonal dimensions, when in reality they should be **co-dependent filters** in a single search space.

---

## 2. Research Objectives

### Primary Goal
Design and implement a **Unified Virtual Table** (`vtab_hybrid`) that performs interleaved traversal of FTS5 and vector indexes within a single SQLite query execution plan.

### Success Metrics
1. **Latency Reduction:** ≥40% improvement over current RRF pipeline
2. **Relevance Improvement:** ≥15% increase in NDCG@10 on OpenClaw benchmark queries
3. **Memory Efficiency:** Support 100k+ embeddings without RAM overflow
4. **Query Expressiveness:** Enable SQL syntax like:
   ```sql
   SELECT * FROM vtab_hybrid 
   WHERE vector_distance(embedding, ?) < 0.8 
     AND fts_match(content, 'SQLite')
   ORDER BY hybrid_score DESC LIMIT 10;
   ```

---

## 3. Technical Approach

### 3.1 Architecture: The Unified Operator

```
┌─────────────────────────────────────────┐
│   Custom Virtual Table: vtab_hybrid     │
├─────────────────────────────────────────┤
│  ┌─────────────┐    ┌────────────────┐ │
│  │ FTS5 Cursor │◄──►│ Vector Cursor  │ │
│  └─────────────┘    └────────────────┘ │
│         │                    │          │
│         └────────┬───────────┘          │
│                  ▼                      │
│        Interleaved Iterator             │
│     (Neuro-Symbolic Ranker)             │
└─────────────────────────────────────────┘
```

**Key Innovation:** The virtual table maintains **dual cursors** that advance cooperatively based on a unified scoring function.

### 3.2 Scoring Function Design

#### Baseline: Weighted Hybrid Score
```
hybrid_score = α·bm25_score + β·(1 - cosine_distance) + γ·temporal_decay
```

Where:
- `α, β, γ` are learned weights (start with 0.3, 0.5, 0.2)
- `temporal_decay = exp(-λ·age_days)` with λ=0.01

#### Advanced: Neuro-Symbolic Constraints
```c
// Pseudo-code for xFilter implementation
if (vector_score > threshold && fts_match_found) {
    // Apply symbolic rules
    if (metadata.source == "TRUSTED" && age_days < 7) {
        boost_factor = 1.5;
    }
    final_score = hybrid_score * boost_factor;
}
```

### 3.3 Implementation Phases

#### Phase 1: Proof of Concept (Weeks 1-3)
- [ ] Implement basic `sqlite3_module` with `xBestIndex` and `xFilter`
- [ ] Create dual-cursor iterator (FTS5 + vec0)
- [ ] Implement naive score merging (simple weighted sum)
- [ ] Benchmark against current RRF baseline

#### Phase 2: Optimization (Weeks 4-6)
- [ ] Add early termination logic (stop when top-k stabilizes)
- [ ] Implement index-aware query planning (push down WHERE clauses)
- [ ] Optimize memory layout (reduce cursor state overhead)
- [ ] Add temporal decay function

#### Phase 3: Neuro-Symbolic Layer (Weeks 7-9)
- [ ] Design metadata schema for symbolic rules
- [ ] Implement `sqlite3_create_function_v2` for custom ranking
- [ ] Add support for user-defined constraints (e.g., "only recent memories")
- [ ] Create query optimizer hints

#### Phase 4: Production Hardening (Weeks 10-12)
- [ ] Stress testing with 100k+ embeddings
- [ ] Query plan visualization tools
- [ ] Documentation and API design
- [ ] Integration with OpenClaw agent runtime

---

## 4. Research Challenges

### 4.1 The "Cursor Synchronization" Problem
**Challenge:** FTS5 returns results in BM25 order, vectors in cosine-similarity order. How do you interleave two differently-sorted streams?

**Proposed Solution:** Implement a **priority queue** that pulls from both cursors and maintains a global top-k heap based on the hybrid score.

### 4.2 The "Index Mismatch" Problem
**Challenge:** FTS5 operates on tokenized text, vectors on dense embeddings. A document might rank high in one but not exist in the other.

**Proposed Solution:** Maintain a **document registry** table that ensures every entry has both FTS5 tokens and a vector embedding (enforce at insert time).

### 4.3 The "Query Planning" Problem
**Challenge:** SQLite's query planner doesn't understand vector operations. It might choose inefficient execution plans.

**Proposed Solution:** Implement custom `xBestIndex` cost estimation that accurately reflects vector scan costs vs. FTS5 index seeks.

---

## 5. Evaluation Methodology

### 5.1 Benchmark Dataset
- **Source:** OpenClaw production logs (anonymized)
- **Size:** 50k memory entries, 1k test queries
- **Diversity:** Mix of keyword-heavy, semantic-heavy, and hybrid queries

### 5.2 Metrics
1. **Latency:** P50, P95, P99 query times
2. **Relevance:** NDCG@10, MRR (Mean Reciprocal Rank)
3. **Resource Usage:** Peak RAM, CPU cycles per query
4. **Scalability:** Performance degradation curve (10k → 100k → 1M entries)

### 5.3 Baseline Comparisons
- Current RRF implementation
- Pure FTS5 (keyword-only)
- Pure vector search (semantic-only)
- Elasticsearch hybrid search (external benchmark)

---

## 6. Expected Outcomes

### 6.1 Technical Deliverables
1. **`libhybrid.so`:** Loadable SQLite extension implementing `vtab_hybrid`
2. **Query Optimizer:** Tool to analyze and visualize hybrid query plans
3. **Benchmark Suite:** Reproducible test harness for future research
4. **Documentation:** API reference and integration guide

### 6.2 Research Contributions
1. **Novel Algorithm:** First open-source implementation of interleaved FTS5/vector search in SQLite
2. **Performance Baseline:** Establish reference metrics for agent memory systems
3. **Design Patterns:** Reusable patterns for neuro-symbolic ranking in embedded databases

### 6.3 Impact on OpenClaw
- **Faster Context Retrieval:** Agents can access relevant memories in <50ms
- **Better Reasoning:** Symbolic constraints enable "explain why this memory is relevant"
- **Scalability:** Support for 1M+ memory entries on consumer hardware

---

## 7. Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| SQLite API limitations | Medium | High | Prototype with `sqlite3_vtab_v2` early; fallback to external index |
| Query planner ignores custom costs | High | Medium | Implement `INDEXED BY` hints; document best practices |
| Vector quantization degrades accuracy | Medium | Medium | A/B test with full-precision fallback |
| Temporal decay too aggressive | Low | Low | Make decay rate configurable per-agent |

---

## 8. Future Research Directions

### 8.1 Multi-Modal Embeddings
Extend `vtab_hybrid` to support image/audio embeddings alongside text vectors.

### 8.2 Federated Memory
Enable cross-agent memory sharing while preserving privacy (encrypted vector search).

### 8.3 Learned Index Structures
Replace B-trees with ML-optimized index structures (e.g., learned bloom filters for vector pruning).

### 8.4 Real-Time Index Updates
Current design assumes batch indexing. Investigate incremental vector index updates for streaming memory ingestion.

---

## 9. Resource Requirements

### 9.1 Compute
- Development machine: 16GB RAM, 8-core CPU (for benchmarking)
- Test corpus: 100k embeddings × 768 dims ≈ 300MB

### 9.2 Software Dependencies
- SQLite 3.45+ (for latest FTS5 features)
- sqlite-vec 0.1.0+
- Python 3.11+ (for benchmark harness)
- Rust (optional, for performance-critical components)

### 9.3 Time Allocation
- **Research & Design:** 20%
- **Implementation:** 50%
- **Evaluation:** 20%
- **Documentation:** 10%

---

## 10. Success Criteria

This research will be considered successful if:

1. ✅ The unified operator achieves **sub-50ms P95 latency** on 100k entries
2. ✅ Relevance metrics show **≥10% improvement** over RRF baseline
3. ✅ The implementation is **production-ready** (tested, documented, integrated)
4. ✅ At least **one novel technique** is publishable (e.g., neuro-symbolic ranking algorithm)

---

## References

1. SQLite FTS5 Documentation: https://www.sqlite.org/fts5.html
2. sqlite-vec: https://github.com/asg017/sqlite-vec
3. Reciprocal Rank Fusion: Cormack et al. (2009)
4. Learned Index Structures: Kraska et al. (2018)
5. OpenClaw Memory Architecture: [Internal Docs]

---

**Next Steps:**
1. Review and refine this proposal with OpenClaw core team
2. Set up development environment and benchmark infrastructure
3. Begin Phase 1 implementation (dual-cursor prototype)
4. Schedule weekly progress reviews

---

*Prepared by: Database Research Team*  
*Date: March 12, 2026*  
*Version: 1.0*
