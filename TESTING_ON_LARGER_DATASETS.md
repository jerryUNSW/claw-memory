# Testing on Larger Datasets with Ground Truth

## 🎯 Problem Statement

**Current limitation**: Testing on your OpenClaw database (30 chunks, no ground truth)

**Need**: 
- Larger datasets (1,000-100,000+ documents)
- Ground truth relevance labels
- Similar to your setting (text chunks, hybrid search)
- Standardized benchmarks for comparison

---

## 📊 Recommended Datasets

### 1. **BEIR (Benchmarking IR)** ⭐ HIGHLY RECOMMENDED

**What it is**: 
- 18 diverse datasets for information retrieval
- Multiple domains (Wikipedia, scientific papers, Q&A, etc.)
- Ground truth relevance labels (qrels)
- Standard evaluation metrics (NDCG, Recall, MAP)

**Why it's perfect for you**:
- ✅ Text-based (similar to your chunks)
- ✅ Multiple dataset sizes (1K-8M documents)
- ✅ Ground truth labels
- ✅ Standard benchmark (can compare to published results)
- ✅ Easy to use with Python

**Datasets in BEIR**:

| Dataset | Documents | Queries | Domain | Size |
|---------|-----------|---------|--------|------|
| **NFCorpus** | 3.6K | 323 | Medical | Small (good for testing) |
| **SciFact** | 5K | 300 | Scientific claims | Small |
| **FiQA-2018** | 57K | 648 | Financial Q&A | Medium |
| **DBPedia** | 4.6M | 400 | Wikipedia entities | Large |
| **MSMARCO** | 8.8M | 6,980 | Web search | Very large |

**Installation**:
```bash
pip install beir
```

**Usage example**:
```python
from beir import util
from beir.datasets.data_loader import GenericDataLoader

# Download dataset
dataset = "nfcorpus"  # Start with small dataset
url = f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{dataset}.zip"
data_path = util.download_and_unzip(url, "datasets")

# Load data
corpus, queries, qrels = GenericDataLoader(data_folder=data_path).load(split="test")

# corpus: {doc_id: {"title": "...", "text": "..."}}
# queries: {query_id: "query text"}
# qrels: {query_id: {doc_id: relevance_score}}
```

**Relevance labels**:
- 0 = Not relevant
- 1 = Relevant
- 2 = Highly relevant

---

### 2. **MS MARCO Passage Ranking** ⭐ POPULAR BENCHMARK

**What it is**:
- 8.8M passages from web documents
- 500K+ queries with relevance labels
- Real user queries from Bing search

**Why it's good**:
- ✅ Large scale (realistic)
- ✅ Real-world queries
- ✅ Ground truth labels
- ✅ Widely used (can compare to baselines)

**Sizes available**:
- **Dev set**: 8.8M passages, 6,980 queries (good for testing)
- **Full set**: 8.8M passages, 500K+ queries (production scale)

**Installation**:
```bash
pip install ir-datasets
```

**Usage**:
```python
import ir_datasets

# Load MS MARCO passage ranking
dataset = ir_datasets.load("msmarco-passage/dev")

# Iterate through documents
for doc in dataset.docs_iter():
    print(doc.doc_id, doc.text)

# Iterate through queries
for query in dataset.queries_iter():
    print(query.query_id, query.text)

# Get relevance judgments
for qrel in dataset.qrels_iter():
    print(qrel.query_id, qrel.doc_id, qrel.relevance)
```

---

### 3. **Natural Questions (NQ)** - Google's Q&A Dataset

**What it is**:
- Real Google search queries
- Wikipedia passages as documents
- 300K+ training examples

**Why it's good**:
- ✅ Real user queries
- ✅ Natural language questions
- ✅ Wikipedia text (clean, structured)

**Installation**:
```bash
pip install datasets
```

**Usage**:
```python
from datasets import load_dataset

# Load Natural Questions
dataset = load_dataset("natural_questions", split="train[:1000]")

for example in dataset:
    question = example['question']['text']
    document = example['document']['tokens']
    annotations = example['annotations']
```

---

### 4. **TREC-COVID** - Scientific Papers

**What it is**:
- 171K scientific papers about COVID-19
- 50 queries with relevance judgments
- Medical/scientific domain

**Why it's good**:
- ✅ Technical domain (like your research notes)
- ✅ High-quality relevance labels
- ✅ Smaller size (good for testing)

**Available in BEIR**:
```python
from beir import util
from beir.datasets.data_loader import GenericDataLoader

dataset = "trec-covid"
url = f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{dataset}.zip"
data_path = util.download_and_unzip(url, "datasets")
corpus, queries, qrels = GenericDataLoader(data_folder=data_path).load(split="test")
```

---

## 🔧 Adapting Your Benchmark to BEIR

### Step 1: Convert BEIR to OpenClaw Format

```python
import sqlite3
from beir import util
from beir.datasets.data_loader import GenericDataLoader

# Download BEIR dataset
dataset = "nfcorpus"
url = f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{dataset}.zip"
data_path = util.download_and_unzip(url, "datasets")

# Load data
corpus, queries, qrels = GenericDataLoader(data_folder=data_path).load(split="test")

# Create SQLite database (OpenClaw format)
conn = sqlite3.connect("beir_nfcorpus.sqlite")

# Create tables
conn.execute("""
    CREATE TABLE chunks (
        id TEXT PRIMARY KEY,
        path TEXT,
        text TEXT,
        start_line INTEGER,
        end_line INTEGER,
        source TEXT,
        updated_at INTEGER
    )
""")

conn.execute("""
    CREATE VIRTUAL TABLE chunks_fts USING fts5(
        id, path, text,
        content='chunks',
        content_rowid='rowid'
    )
""")

# Insert documents
import time
for doc_id, doc in corpus.items():
    text = doc.get('title', '') + '\n\n' + doc.get('text', '')
    conn.execute("""
        INSERT INTO chunks (id, path, text, start_line, end_line, source, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (doc_id, f"beir/{dataset}/{doc_id}", text, 0, 0, "beir", int(time.time())))

# Build FTS5 index
conn.execute("INSERT INTO chunks_fts SELECT id, path, text FROM chunks")

conn.commit()
conn.close()

print(f"Created database with {len(corpus)} documents")
```

### Step 2: Extract Test Queries

```python
# Save queries to file
with open("beir_queries.txt", "w") as f:
    for query_id, query_text in queries.items():
        f.write(f"{query_id}\t{query_text}\n")

print(f"Saved {len(queries)} queries")
```

### Step 3: Run Your Benchmark

```python
# Modify your benchmark script to use BEIR queries
from scripts.compare_rrf_vs_interleaved import benchmark_rrf, benchmark_interleaved

conn = sqlite3.connect("beir_nfcorpus.sqlite")

results = []
for query_id, query_text in queries.items():
    # Run both methods
    rrf_results, rrf_metrics = benchmark_rrf(conn, query_text, top_k=10)
    int_results, int_metrics = benchmark_interleaved(conn, query_text, top_k=10)
    
    results.append({
        'query_id': query_id,
        'query': query_text,
        'rrf': rrf_results,
        'interleaved': int_results,
        'rrf_metrics': rrf_metrics,
        'int_metrics': int_metrics
    })

conn.close()
```

### Step 4: Evaluate with Ground Truth

```python
def evaluate_with_qrels(results, qrels):
    """Evaluate retrieval quality using ground truth labels"""
    from collections import defaultdict
    
    metrics = defaultdict(list)
    
    for result in results:
        query_id = result['query_id']
        rrf_ids = [r.id for r in result['rrf']]
        int_ids = [r.id for r in result['interleaved']]
        
        # Get ground truth for this query
        relevant_docs = qrels.get(query_id, {})
        
        # Calculate metrics for RRF
        rrf_ndcg = calculate_ndcg(rrf_ids, relevant_docs)
        rrf_recall = calculate_recall(rrf_ids, relevant_docs)
        
        # Calculate metrics for Interleaved
        int_ndcg = calculate_ndcg(int_ids, relevant_docs)
        int_recall = calculate_recall(int_ids, relevant_docs)
        
        metrics['rrf_ndcg'].append(rrf_ndcg)
        metrics['rrf_recall'].append(rrf_recall)
        metrics['int_ndcg'].append(int_ndcg)
        metrics['int_recall'].append(int_recall)
    
    # Average metrics
    return {
        'rrf_ndcg': sum(metrics['rrf_ndcg']) / len(metrics['rrf_ndcg']),
        'rrf_recall': sum(metrics['rrf_recall']) / len(metrics['rrf_recall']),
        'int_ndcg': sum(metrics['int_ndcg']) / len(metrics['int_ndcg']),
        'int_recall': sum(metrics['int_recall']) / len(metrics['int_recall']),
    }

def calculate_ndcg(retrieved_ids, relevant_docs, k=10):
    """Calculate NDCG@k"""
    dcg = 0.0
    for i, doc_id in enumerate(retrieved_ids[:k]):
        relevance = relevant_docs.get(doc_id, 0)
        dcg += (2**relevance - 1) / np.log2(i + 2)
    
    # Ideal DCG
    ideal_relevances = sorted(relevant_docs.values(), reverse=True)[:k]
    idcg = sum((2**rel - 1) / np.log2(i + 2) for i, rel in enumerate(ideal_relevances))
    
    return dcg / idcg if idcg > 0 else 0.0

def calculate_recall(retrieved_ids, relevant_docs, k=10):
    """Calculate Recall@k"""
    retrieved_set = set(retrieved_ids[:k])
    relevant_set = set(doc_id for doc_id, rel in relevant_docs.items() if rel > 0)
    
    if len(relevant_set) == 0:
        return 0.0
    
    return len(retrieved_set & relevant_set) / len(relevant_set)
```

---

## 📋 Recommended Testing Strategy

### Phase 1: Small Dataset (Quick Validation)
**Dataset**: BEIR NFCorpus (3.6K docs, 323 queries)
**Time**: 1-2 hours
**Goal**: Validate that your approach works on external data

```bash
# Download and setup
python3 scripts/setup_beir_nfcorpus.py

# Run benchmark
python3 scripts/benchmark_beir.py --dataset nfcorpus

# Expected results:
# - Overlap: 85-95% (not 100% like your small DB)
# - Speedup: 10-20x
# - NDCG: RRF ~0.35, Interleaved ~0.33 (slight drop)
```

### Phase 2: Medium Dataset (Realistic Scale)
**Dataset**: BEIR FiQA (57K docs, 648 queries)
**Time**: 4-6 hours
**Goal**: Test scalability and effectiveness trade-off

```bash
python3 scripts/benchmark_beir.py --dataset fiqa

# Expected results:
# - Overlap: 80-90%
# - Speedup: 15-30x
# - NDCG: RRF ~0.32, Interleaved ~0.29 (5-10% drop)
```

### Phase 3: Large Dataset (Production Scale)
**Dataset**: MS MARCO (8.8M docs, 6,980 queries)
**Time**: 1-2 days
**Goal**: Validate production readiness

```bash
python3 scripts/benchmark_msmarco.py

# Expected results:
# - Overlap: 75-85%
# - Speedup: 20-50x
# - NDCG: RRF ~0.28, Interleaved ~0.25 (10-15% drop)
```

---

## 🎯 Evaluation Metrics with Ground Truth

### 1. **NDCG@k (Normalized Discounted Cumulative Gain)**
- Measures ranking quality with graded relevance
- Range: 0.0 (worst) to 1.0 (perfect)
- **Most important metric** for ranking evaluation

### 2. **Recall@k**
- % of relevant documents retrieved in top-k
- Range: 0.0 to 1.0
- Measures completeness

### 3. **MAP (Mean Average Precision)**
- Average precision across all queries
- Range: 0.0 to 1.0
- Measures overall quality

### 4. **MRR (Mean Reciprocal Rank)**
- Average of 1/rank of first relevant document
- Range: 0.0 to 1.0
- Measures top-1 quality

---

## 🔧 Complete Implementation Script

I'll create a complete script for you:

```python
# scripts/benchmark_beir.py
```

Would you like me to create the complete implementation script that:
1. Downloads BEIR datasets
2. Converts to OpenClaw format
3. Runs your RRF vs Interleaved benchmark
4. Evaluates with ground truth (NDCG, Recall, MAP)
5. Generates comparison report

---

## 📊 Expected Results Summary

| Dataset | Size | RRF NDCG | Interleaved NDCG | Speedup | Overlap |
|---------|------|----------|------------------|---------|---------|
| Your DB | 30 | N/A | N/A | 13.91x | 100% |
| NFCorpus | 3.6K | 0.35 | 0.33 (-6%) | 15x | 90% |
| FiQA | 57K | 0.32 | 0.29 (-9%) | 25x | 85% |
| MS MARCO | 8.8M | 0.28 | 0.25 (-11%) | 40x | 80% |

**Key insight**: As dataset size increases, effectiveness gap widens but speedup also increases.

---

## 🚀 Next Steps

1. **Start with NFCorpus** (small, fast to test)
2. **Implement evaluation metrics** (NDCG, Recall)
3. **Measure actual effectiveness degradation**
4. **Compare to published baselines**
5. **Scale to larger datasets**

Would you like me to create the complete implementation scripts for BEIR benchmarking?
