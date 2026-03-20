# Research Roadmap: Unified Retrieval Operator for OpenClaw

## Executive Summary

You now have everything you need to start your research:

✅ **Problem Identified**: OpenClaw uses post-process RRF fusion (inefficient)  
✅ **Database Located**: `~/.openclaw/memory/main.sqlite` (30 chunks, ready to use)  
✅ **Architecture Understood**: FTS5 + sqlite-vec with JavaScript fusion  
✅ **Research Goal**: Move fusion into SQLite (unified operator)  
✅ **Tools Created**: Query scripts, analysis tools, dataset strategy  

---

## Week-by-Week Plan

### Week 1-2: Baseline & Dataset Preparation

#### Tasks
1. **Measure Current RRF Performance**
   ```bash
   # Create benchmark for current system
   python3 scripts/benchmark_baseline.py
   ```

2. **Generate Test Queries**
   - Use your 30 existing chunks
   - Create 50-100 test queries
   - Manual relevance labels (0-2 scale)

3. **Download MS MARCO Dev Set**
   ```bash
   pip install ir-datasets
   python3 scripts/download_msmarco.py
   ```

#### Deliverables
- Baseline metrics: NDCG@10, MRR, P95 latency
- Test query dataset (50-100 queries)
- MS MARCO indexed in SQLite

---

### Week 3-4: Proof of Concept

#### Tasks
1. **Implement Basic Virtual Table**
   ```c
   // vtab_hybrid.c - skeleton
   static int hybridBestIndex(sqlite3_vtab *tab, sqlite3_index_info *info);
   static int hybridFilter(sqlite3_vtab_cursor *cur, ...);
   static int hybridNext(sqlite3_vtab_cursor *cur);
   ```

2. **Naive Fusion (No Optimization)**
   - Simple weighted sum: `0.5*vec + 0.3*text`
   - No early termination yet
   - Just prove it works

3. **Test on Your 30 Chunks**
   ```sql
   SELECT * FROM vtab_hybrid 
   WHERE query = 'memory workflow'
   LIMIT 10;
   ```

#### Deliverables
- Working virtual table (basic)
- Correctness validation (same results as RRF)
- Initial performance comparison

---

### Week 5-6: Optimization

#### Tasks
1. **Implement Interleaved Traversal**
   - Priority queue for dual cursors
   - Early termination logic
   - Top-k stability detection

2. **Add Temporal Decay**
   ```c
   double temporal_score = exp(-lambda * age_days);
   double hybrid_score = alpha*vec + beta*text + gamma*temporal;
   ```

3. **Optimize xBestIndex**
   - Accurate cost estimation
   - Push down WHERE clauses
   - Index selection hints

#### Deliverables
- Optimized virtual table
- Latency improvements measured
- Ablation study (which optimizations help most)

---

### Week 7-8: Evaluation

#### Tasks
1. **Run Full Benchmark Suite**
   - Your OpenClaw memory (30 chunks)
   - MS MARCO dev set (6,980 queries)
   - BEIR SciFact (300 queries)

2. **Statistical Analysis**
   - Paired t-test (RRF vs Unified)
   - 95% confidence intervals
   - Latency percentiles (P50, P95, P99)

3. **Ablation Studies**
   - Effect of α, β, γ weights
   - Early termination impact
   - Temporal decay contribution

#### Deliverables
- Performance report
- Statistical significance tests
- Visualization (latency, NDCG charts)

---

### Week 9-10: Production Hardening

#### Tasks
1. **Stress Testing**
   - Concurrent queries (10, 50, 100 threads)
   - Large datasets (100K, 1M entries)
   - Memory leak detection (valgrind)

2. **Integration with OpenClaw**
   - Replace current RRF code
   - Backward compatibility
   - Configuration options

3. **Documentation**
   - API reference
   - Integration guide
   - Performance tuning tips

#### Deliverables
- Production-ready code
- Integration PR for OpenClaw
- Documentation

---

## Key Milestones

| Week | Milestone | Success Criteria |
|------|-----------|------------------|
| 2 | Baseline established | RRF metrics on 3 datasets |
| 4 | Proof of concept | Virtual table returns correct results |
| 6 | Optimization complete | 40% latency reduction vs RRF |
| 8 | Evaluation done | Statistical significance proven |
| 10 | Production ready | Integrated into OpenClaw |

---

## Datasets Strategy

### Tier 1: Your OpenClaw Memory (Primary)
- **Size**: 30 chunks (perfect for rapid iteration)
- **Queries**: Generate 50-100 test queries
- **Use**: Daily development and testing

### Tier 2: MS MARCO (General IR)
- **Size**: 8.8M passages, 6,980 dev queries
- **Use**: Prove general effectiveness
- **Metrics**: NDCG@10, MRR (compare to published baselines)

### Tier 3: BEIR SciFact (Domain-Specific)
- **Size**: 5K docs, 300 queries
- **Use**: Test on reasoning-heavy queries (like agent memory)
- **Metrics**: NDCG@10, Recall@100

### Tier 4: Synthetic Agent Memory (Optional)
- **Size**: Generate 5K-10K synthetic memories
- **Use**: Test agent-specific patterns (temporal, conversational)
- **Metrics**: Custom (temporal accuracy, partial match recall)

---

## Technical Architecture

### Current (Baseline)
```
┌─────────────────────────────────┐
│  Application (JavaScript)       │
│  ┌─────────┐    ┌─────────┐   │
│  │ FTS5    │    │ Vector  │   │
│  │ Query   │    │ Query   │   │
│  └────┬────┘    └────┬────┘   │
│       │              │         │
│       └──────┬───────┘         │
│              ↓                 │
│         RRF Merge              │
│    (JavaScript code)           │
└─────────────────────────────────┘
         ↓
    SQLite DB
```

### Target (Unified Operator)
```
┌─────────────────────────────────┐
│  Application (JavaScript)       │
│  ┌─────────────────────────┐   │
│  │  Single Query           │   │
│  │  vtab_hybrid            │   │
│  └────────────┬────────────┘   │
└───────────────┼─────────────────┘
                ↓
┌─────────────────────────────────┐
│  SQLite Virtual Table           │
│  ┌──────────────────────────┐  │
│  │  Interleaved Traversal   │  │
│  │  ┌────────┐  ┌────────┐ │  │
│  │  │ FTS5   │  │ Vector │ │  │
│  │  │ Cursor │  │ Cursor │ │  │
│  │  └───┬────┘  └───┬────┘ │  │
│  │      └─────┬──────┘      │  │
│  │            ↓             │  │
│  │    Priority Queue        │  │
│  │    Hybrid Scoring        │  │
│  │    Early Termination     │  │
│  └──────────────────────────┘  │
└─────────────────────────────────┘
```

---

## Metrics to Track

### Relevance Metrics
- **NDCG@10**: Ranking quality (primary metric)
- **MRR**: First relevant result position
- **Recall@k**: Coverage (k=5,10,20)
- **MAP**: Overall precision

### Efficiency Metrics
- **P50 Latency**: Median query time
- **P95 Latency**: Tail latency (target: <50ms)
- **P99 Latency**: Worst-case performance
- **Throughput**: Queries per second

### Agent-Specific Metrics
- **Temporal Accuracy**: Recent memories rank higher?
- **Partial Match Recall**: Vague queries work?
- **Multi-hop Success**: Connect related memories?

---

## Success Criteria

Your research will be successful if:

1. ✅ **Correctness**: Unified operator returns same/better results than RRF
2. ✅ **Performance**: ≥40% latency reduction on 100K entries
3. ✅ **Relevance**: ≥10% NDCG@10 improvement on agent queries
4. ✅ **Scalability**: Handles 1M entries without degradation
5. ✅ **Integration**: Works in production OpenClaw

---

## Resources You Have

### Code & Tools
```
OpenClaw-Hybrid-Retrieval-Research/
├── RESEARCH_PROPOSAL.md          # Your original proposal
├── DATABASE_ANALYSIS.md           # Database findings
├── DATASET_STRATEGY.md            # Dataset recommendations
├── scripts/
│   ├── query_openclaw.py         # Database explorer
│   ├── openclaw_queries.sql      # Example queries
│   └── generate_synthetic_memory.md  # Dataset generation
└── data/
    └── (will contain MS MARCO, BEIR datasets)
```

### Your Database
- **Path**: `~/.openclaw/memory/main.sqlite`
- **Size**: 30 chunks, 10 files
- **Embeddings**: Gemini 3072-dim
- **Ready to use**: Yes!

### Knowledge Base
- OpenClaw source code analyzed
- Current RRF implementation understood
- SQLite virtual table API documented
- Hybrid retrieval literature reviewed

---

## Next Immediate Steps

### 1. Create Benchmark Script (Today)
```bash
cd /Users/jerry/Desktop/OpenClaw-Hybrid-Retrieval-Research
touch scripts/benchmark_baseline.py
```

### 2. Generate Test Queries (Tomorrow)
- Look at your 30 chunks
- Write 50 queries manually
- Label relevance (0=irrelevant, 1=relevant, 2=highly relevant)

### 3. Measure Baseline (This Week)
- Run current RRF on your queries
- Record: NDCG@10, MRR, latency
- This is your target to beat!

---

## Questions to Answer

As you progress, answer these research questions:

1. **How much faster is unified vs RRF?**
   - Hypothesis: 40-50% faster
   - Measure: P95 latency on 100K entries

2. **Does interleaved traversal improve ranking?**
   - Hypothesis: +15% NDCG@10
   - Measure: On agent-specific queries

3. **When does early termination help most?**
   - Hypothesis: High-overlap queries benefit most
   - Measure: Ablation study

4. **What are optimal fusion weights?**
   - Hypothesis: α=0.5, β=0.3, γ=0.2
   - Measure: Grid search on validation set

5. **Does this scale to 1M+ entries?**
   - Hypothesis: Yes, with proper indexing
   - Measure: Stress test on MS MARCO

---

## Summary

You're ready to start! You have:

✅ Clear problem (post-process fusion is slow)  
✅ Real database (30 chunks in OpenClaw)  
✅ Research plan (10-week roadmap)  
✅ Tools (query scripts, analysis tools)  
✅ Datasets (OpenClaw + MS MARCO + BEIR)  
✅ Success criteria (40% faster, 15% better NDCG)  

**Start with Week 1**: Measure baseline RRF performance on your 30 chunks. That's your target to beat!

Good luck! 🚀
