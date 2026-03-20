# Quick Start Guide: Step-by-Step Commands

## 🚀 Getting Started

### Step 1: Navigate to Project
```bash
cd /Users/jerry/Desktop/OpenClaw-Hybrid-Retrieval-Research
```

### Step 2: Explore Your OpenClaw Database
```bash
# Run the Python explorer (recommended)
python3 scripts/query_openclaw.py
```

**What you'll see:**
- Database overview (30 chunks, 10 files)
- Recent memory chunks
- Embedding configuration (Gemini 3072-dim)
- Sample searches

---

## 📊 Measure Baseline Performance

### Step 3: Run Baseline Benchmark
```bash
python3 scripts/benchmark_baseline.py
```

**What you'll see:**
```
Average Latency:  2.30ms
P50 Latency:      0.19ms
P95 Latency:      17.07ms

Target for Unified Operator:
- Latency: <1.38ms (40% reduction)
```

---

## 🔍 Explore Database Manually

### Step 4: Interactive SQL Mode
```bash
# Open SQLite interactive shell
sqlite3 ~/.openclaw/memory/main.sqlite
```

**Inside SQLite shell:**
```sql
-- Enable column mode for better display
.mode column
.headers on

-- See all tables
.tables

-- Count your chunks
SELECT COUNT(*) as total_chunks FROM chunks;

-- View recent memories
SELECT 
    substr(path, 1, 30) as file,
    substr(text, 1, 60) as preview
FROM chunks
ORDER BY updated_at DESC
LIMIT 5;

-- Search for keyword "memory"
SELECT 
    substr(id, 1, 12) as chunk_id,
    substr(path, 1, 30) as path,
    ROUND(bm25(chunks_fts), 2) as score
FROM chunks_fts
WHERE chunks_fts MATCH 'memory'
ORDER BY score ASC
LIMIT 5;SELECT 
    substr(id, 1, 12) as chunk_id,
    substr(path, 1, 30) as path,
    ROUND(bm25(chunks_fts), 2) as score
FROM chunks_fts
WHERE chunks_fts MATCH 'memory'
ORDER BY score ASC
LIMIT 5;

-- Exit SQLite
.quit
```

---

## 📝 View Your Memory Files

### Step 5: Check Memory Content
```bash
# List all memory files
ls -lh ~/.openclaw/agents/main/agent/memory/

# View a specific memory file
cat ~/.openclaw/agents/main/agent/memory/MEMORY.md

# Or use less for longer files
less ~/.openclaw/agents/main/agent/memory/2026-03-05.md
```

---

## 📖 Read Documentation

### Step 6: Review Research Documents
```bash
# Quick overview
cat README.md

# Database analysis
cat DATABASE_ANALYSIS.md

# 10-week roadmap
cat ROADMAP.md

# Baseline results
cat BASELINE_RESULTS.md

# Dataset strategy
cat DATASET_STRATEGY.md

# Original proposal
cat RESEARCH_PROPOSAL.md
```

---

## 🧪 Test Queries

### Step 7: Try Custom Queries

**Using Python:**
```bash
# Open Python interactive mode
python3 -i scripts/query_openclaw.py

# Then in Python:
>>> conn = connect_db()
>>> results = search_fts5(conn, "workflow", limit=5)
>>> for r in results:
...     print(r['path'], r['bm25_score'])
```

**Using SQLite directly:**
```bash
sqlite3 ~/.openclaw/memory/main.sqlite "
SELECT 
    substr(path, 1, 40) as file,
    substr(text, 1, 80) as preview
FROM chunks_fts
WHERE chunks_fts MATCH 'technical'
LIMIT 3;
"
```

---

## 📊 Generate Test Queries

### Step 8: Create Your Test Dataset

```bash
# Create data directory
mkdir -p data

# Create test queries file
cat > data/test_queries.txt << 'EOF'
memory workflow
technical notes
session February
2026 March
LLM request
xiaohongshu
triangle DDS
regulation annotations
memory from March 2026
technical notes about workflow
session from February 24
EOF

# View your queries
cat data/test_queries.txt
```

---

## 🔬 Advanced Exploration

### Step 9: Run Custom SQL Queries

```bash
# Count chunks by source
sqlite3 ~/.openclaw/memory/main.sqlite "
SELECT source, COUNT(*) as count 
FROM chunks 
GROUP BY source;
"

# Check embedding dimensions
sqlite3 ~/.openclaw/memory/main.sqlite "
SELECT provider, model, dims 
FROM embedding_cache 
GROUP BY provider, model, dims;
"

# Find oldest and newest memories
sqlite3 ~/.openclaw/memory/main.sqlite "
SELECT 
    'Oldest' as type,
    path,
    datetime(updated_at, 'unixepoch') as date
FROM chunks
ORDER BY updated_at ASC
LIMIT 1
UNION ALL
SELECT 
    'Newest',
    path,
    datetime(updated_at, 'unixepoch')
FROM chunks
ORDER BY updated_at DESC
LIMIT 1;
"
```

---

## 📈 Benchmark with Custom Queries

### Step 10: Test Your Own Queries

**Edit the benchmark script:**
```bash
# Open in your editor
code scripts/benchmark_baseline.py
# or
nano scripts/benchmark_baseline.py

# Add your queries to TEST_QUERIES list (around line 15)
```

**Then run:**
```bash
python3 scripts/benchmark_baseline.py
```

---

## 🔧 Useful One-Liners

### Quick Database Stats
```bash
# Total chunks
sqlite3 ~/.openclaw/memory/main.sqlite "SELECT COUNT(*) FROM chunks;"

# Total files
sqlite3 ~/.openclaw/memory/main.sqlite "SELECT COUNT(*) FROM files;"

# Database size
ls -lh ~/.openclaw/memory/main.sqlite

# All memory files
sqlite3 ~/.openclaw/memory/main.sqlite "SELECT path FROM files;"
```

### Search Examples
```bash
# Search for "SQLite"
sqlite3 ~/.openclaw/memory/main.sqlite "
SELECT path, substr(text, 1, 100) 
FROM chunks_fts 
WHERE chunks_fts MATCH 'SQLite' 
LIMIT 3;
"

# Search for "workflow"
sqlite3 ~/.openclaw/memory/main.sqlite "
SELECT path, substr(text, 1, 100) 
FROM chunks_fts 
WHERE chunks_fts MATCH 'workflow' 
LIMIT 3;
"
```

---

## 📚 Next Steps

### Week 1 Tasks

**1. Generate more test queries (50-100 total):**
```bash
# Edit your test queries
nano data/test_queries.txt

# Add queries based on your actual memory content
# Look at: python3 scripts/query_openclaw.py
```

**2. Add relevance labels:**
```bash
# Create relevance labels file
cat > data/relevance_labels.csv << 'EOF'
query,chunk_id,relevance
"memory workflow",7e06eab8f604,2
"technical notes",c0d79f2ad4f6,2
EOF

# Edit and expand
nano data/relevance_labels.csv
```

**3. Download MS MARCO (optional for now):**
```bash
# Install dependencies
pip3 install ir-datasets

# Create download script
cat > scripts/download_msmarco.py << 'EOF'
import ir_datasets
dataset = ir_datasets.load("msmarco-passage/dev")
print(f"Loaded {dataset.docs_count()} documents")
EOF

# Run it
python3 scripts/download_msmarco.py
```

---

## 🆘 Troubleshooting

### Database not found?
```bash
# Check if database exists
ls -la ~/.openclaw/memory/main.sqlite

# If not found, check OpenClaw installation
which openclaw
openclaw --version
```

### Python script errors?
```bash
# Check Python version (need 3.7+)
python3 --version

# Install missing packages if needed
pip3 install sqlite3
```

### Permission denied?
```bash
# Make scripts executable
chmod +x scripts/*.py
chmod +x scripts/*.sh
```

---

## 📋 Command Cheat Sheet

```bash
# Navigate to project
cd /Users/jerry/Desktop/OpenClaw-Hybrid-Retrieval-Research

# Explore database
python3 scripts/query_openclaw.py

# Run benchmark
python3 scripts/benchmark_baseline.py

# Interactive SQL
sqlite3 ~/.openclaw/memory/main.sqlite

# View memory files
ls ~/.openclaw/agents/main/agent/memory/

# Read documentation
cat README.md
cat ROADMAP.md
cat DATABASE_ANALYSIS.md

# Custom query
sqlite3 ~/.openclaw/memory/main.sqlite "SELECT * FROM chunks LIMIT 5;"

# Check database size
ls -lh ~/.openclaw/memory/main.sqlite

# Count chunks
sqlite3 ~/.openclaw/memory/main.sqlite "SELECT COUNT(*) FROM chunks;"
```

---

## 🎯 Your Current Status

✅ **Database located**: `~/.openclaw/memory/main.sqlite`  
✅ **Baseline measured**: 2.30ms average latency  
✅ **Tools ready**: query_openclaw.py, benchmark_baseline.py  
✅ **Documentation complete**: 6 markdown files  
✅ **Test queries**: 8 queries (expand to 50-100)  

**Next**: Generate more test queries and start implementing the unified operator!

---

## 💡 Pro Tips

1. **Start small**: Test with your 30 chunks first
2. **Iterate quickly**: Use Python scripts for rapid testing
3. **Document everything**: Keep notes on what works
4. **Compare always**: Measure before and after changes
5. **Use version control**: `git init` and commit your progress

---

**Ready to start? Run this:**
```bash
cd /Users/jerry/Desktop/OpenClaw-Hybrid-Retrieval-Research
python3 scripts/query_openclaw.py
```

Good luck! 🚀
