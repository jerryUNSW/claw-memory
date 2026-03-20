# Dataset Strategy for Unified Retrieval Operator Research

## Executive Summary

To validate the unified interleaved operator for OpenClaw, you need **three-tier dataset strategy**:

1. **Public IR Benchmarks** → Prove general effectiveness
2. **Synthetic Agent Memory** → Validate agent-specific patterns
3. **Real OpenClaw Memory (Optional)** → Production validation

---

## Tier 1: Public IR Datasets (Required)

### Purpose
Establish that your approach is competitive with state-of-the-art hybrid retrieval systems.

### Recommended Datasets

#### A. MS MARCO Passage Ranking
- **Size**: 8.8M passages, 1M queries
- **Download**: `pip install ir-datasets` → `ir_datasets.load("msmarco-passage")`
- **Use Case**: Primary benchmark for hybrid retrieval
- **Metrics**: NDCG@10, MRR, Recall@100

**Why it matters:**
- Industry standard (used by Elasticsearch, Vespa, Weaviate)
- Queries have both keyword and semantic components
- Large enough to test scalability (your 100k+ target)

**Example Query:**
```
Query: "what is the difference between a loan and a credit line"
→ Tests: keyword matching ("loan", "credit") + semantic understanding (difference)
```

#### B. BEIR Benchmark (3 subsets)

**BEIR - SciFact** (Scientific Claim Verification)
- **Size**: 5K documents, 300 queries
- **Why**: Tests reasoning-heavy queries (similar to agent memory retrieval)
- **Example**: "Claim: Vitamin D deficiency is unrelated to cardiovascular disease"
  - Requires semantic understanding + fact verification

**BEIR - NFCorpus** (Medical/Technical)
- **Size**: 3.6K documents, 323 queries  
- **Why**: Domain-specific terminology (like code/technical docs in agent memory)
- **Example**: "What are the effects of IL-6 on inflammation?"

**BEIR - ArguAna** (Argument Retrieval)
- **Size**: 8.7K documents, 1,406 queries
- **Why**: Tests multi-hop reasoning (agent needs to connect multiple memories)

**Download BEIR:**
```bash
pip install beir
from beir import util
url = "https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{}.zip"
util.download_and_unzip(url.format("scifact"), "datasets")
```

#### C. Natural Questions (Conversational Queries)
- **Size**: 307K queries, 2.6M passages
- **Why**: Conversational style matches agent memory queries
- **Example**: "when did the us break away from england"
  - Natural language (not keyword-optimized)

---

## Tier 2: Synthetic Agent Memory (Strongly Recommended)

### Why You Need This

Public IR datasets **don't capture** agent-specific patterns:

| Pattern | Public IR | Agent Memory |
|---------|-----------|--------------|
| **Temporal queries** | ❌ "capital of France" | ✅ "that bug from yesterday" |
| **Session context** | ❌ Single-shot queries | ✅ "continue that discussion" |
| **Code snippets** | ❌ Natural language only | ✅ Mixed text + code |
| **Partial recall** | ❌ Complete questions | ✅ "the thing about SQLite..." |
| **Multi-modal** | ❌ Text only | ✅ Text + metadata + timestamps |

### Generation Strategy

See `scripts/generate_synthetic_memory.md` for full implementation.

**Quick Start:**

1. **Seed Corpus** (1000 entries minimum)
   - Use OpenClaw's own documentation
   - Add synthetic technical discussions
   - Include code snippets from real projects

2. **Query Generation** (3-5 queries per memory)
   ```python
   memory = "Implemented hybrid search with vectorWeight=0.5, textWeight=0.3"
   
   queries = [
       "hybrid search weights",              # Keyword-heavy
       "how did we combine vector and text", # Semantic-heavy  
       "that search thing from last week",   # Temporal + vague
       "the 0.5 and 0.3 parameters",        # Specific detail
       "remind me about ranking fusion"      # Conversational
   ]
   ```

3. **Relevance Labels**
   - **2**: Direct answer (memory fully answers query)
   - **1**: Partial match (related but incomplete)
   - **0**: Irrelevant

4. **Temporal Distribution**
   ```python
   age_distribution = {
       "recent": (0, 7),      # 20% of memories
       "medium": (7, 30),     # 30%
       "old": (30, 90),       # 30%
       "archived": (90, 365)  # 20%
   }
   ```

### Advantages

✅ **Controlled experiments**: Vary temporal decay, query complexity
✅ **No privacy issues**: Fully synthetic
✅ **Reproducible**: Other researchers can regenerate
✅ **Unlimited scale**: Generate 10K, 100K, 1M entries as needed

---

## Tier 3: Real OpenClaw Memory (Optional but Valuable)

### When to Use

- **After** proving concept on synthetic data
- For final production validation
- To discover edge cases not in synthetic data

### Collection Methods

#### Option A: Your Own OpenClaw Usage
```bash
# Export your own memory
openclaw memory export --agent default --output my_memory.jsonl

# Anonymize sensitive content
python scripts/anonymize_memory.py my_memory.jsonl
```

#### Option B: Opt-in User Study
- Recruit 10-20 OpenClaw users
- Ask them to donate anonymized memory
- Provide clear privacy policy
- Manual review to remove PII

#### Option C: Synthetic from Real Patterns
- Analyze real query patterns (without content)
- Generate synthetic memories matching those patterns
- Best of both worlds: realistic patterns + no privacy issues

### Privacy Considerations

⚠️ **Critical**: Real agent memory may contain:
- API keys, passwords
- Personal information
- Proprietary code
- Confidential discussions

**Mitigation:**
```python
def anonymize_memory(entry):
    # Remove PII
    entry = redact_emails(entry)
    entry = redact_api_keys(entry)
    entry = redact_file_paths(entry)
    
    # Generalize specifics
    entry = replace_names_with_placeholders(entry)
    entry = replace_dates_with_relative_times(entry)
    
    return entry
```

---

## Recommended Research Timeline

### Phase 1: Baseline (Weeks 1-2)
- Download MS MARCO + BEIR
- Implement current RRF baseline
- Establish performance metrics

**Deliverable**: Baseline performance report
```
MS MARCO: NDCG@10 = 0.42, MRR = 0.38
BEIR-SciFact: NDCG@10 = 0.65, MRR = 0.71
```

### Phase 2: Synthetic Dataset (Weeks 3-4)
- Generate 5K synthetic memories
- Create 15K query-memory pairs
- Validate query diversity

**Deliverable**: Synthetic dataset + statistics
```
Query Types:
- Keyword-heavy: 30%
- Semantic-heavy: 30%
- Temporal: 20%
- Conversational: 20%
```

### Phase 3: Unified Operator (Weeks 5-8)
- Implement vtab_hybrid
- Test on MS MARCO (general)
- Test on synthetic (agent-specific)

**Deliverable**: Performance comparison
```
                MS MARCO    Synthetic
RRF Baseline    0.42        0.38
Unified Op      0.46 (+9%)  0.51 (+34%)
```

### Phase 4: Real Data Validation (Weeks 9-10)
- Collect anonymized real memory (if possible)
- Run final evaluation
- Identify edge cases

**Deliverable**: Production readiness report

---

## Dataset Sizes for Different Goals

| Goal | MS MARCO | BEIR | Synthetic | Real |
|------|----------|------|-----------|------|
| **Proof of Concept** | Dev set (6K) | SciFact (300) | 1K memories | None |
| **Research Paper** | Full (1M) | 3 subsets | 10K memories | Optional |
| **Production** | Full (1M) | All BEIR | 50K memories | 5K+ queries |

---

## Key Metrics to Track

### Relevance Metrics
- **NDCG@10**: Ranking quality with graded relevance
- **MRR**: Position of first relevant result
- **Recall@k**: Coverage of relevant results

### Efficiency Metrics
- **P50/P95/P99 Latency**: Query response time
- **Throughput**: Queries per second
- **Memory Usage**: Peak RAM during queries

### Agent-Specific Metrics
- **Temporal Accuracy**: Do recent memories rank higher?
- **Partial Match Recall**: Can it find memories from vague queries?
- **Multi-hop Success**: Can it connect related memories?

---

## Answer to Your Question

**Do you need real agent memory?**

**Short answer**: No, but it helps.

**Recommended approach**:
1. **Start with MS MARCO + BEIR** → Prove general effectiveness (2 weeks)
2. **Generate synthetic agent memory** → Validate agent patterns (2 weeks)
3. **Optionally collect real data** → Final validation (1 week)

**Why this works:**
- Public datasets give you credibility
- Synthetic data lets you test agent-specific features
- Real data is nice-to-have, not required

**Your research will be stronger with synthetic data** because:
- You can control variables (temporal decay, query complexity)
- No privacy concerns
- Reproducible by reviewers
- Can generate edge cases on demand

---

## Next Steps

1. **Download MS MARCO dev set** (6,980 queries)
   ```bash
   pip install ir-datasets
   python scripts/download_msmarco.py
   ```

2. **Download BEIR SciFact**
   ```bash
   pip install beir
   python scripts/download_beir.py --dataset scifact
   ```

3. **Generate synthetic memory** (1K entries)
   ```bash
   python scripts/generate_synthetic_memory.py --size 1000
   ```

4. **Run baseline evaluation**
   ```bash
   python scripts/eval_baseline.py --dataset msmarco --method rrf
   ```

This gives you a solid foundation to prove your unified operator works on both general IR tasks and agent-specific memory retrieval.
