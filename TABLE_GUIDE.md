# OpenClaw Database Tables Explained

## 📊 Table Overview

Your database has **3 main systems** + supporting tables:

```
1. Core Data (chunks, files, meta)
2. FTS5 Full-Text Search (chunks_fts + 5 internal tables)
3. Vector Search (chunks_vec + 4 internal tables)
4. Performance Cache (embedding_cache)
```

---

## 🗂️ Core Tables (You interact with these)

### 1. `chunks` - Main Data Table
**What it stores**: Your actual memory content

```sql
-- View structure
.schema chunks

-- What's inside:
-- - id: Unique chunk identifier
-- - path: File path (e.g., "memory/2026-03-05.md")
-- - text: The actual content
-- - embedding: Vector embedding (serialized)
-- - start_line, end_line: Line numbers in file
-- - source: "memory" or "sessions"
-- - model: Embedding model used
-- - updated_at: Timestamp
```

**Example query:**
```sql
SELECT id, path, substr(text, 1, 50) as preview 
FROM chunks 
LIMIT 3;
```

---

### 2. `files` - File Tracking
**What it stores**: Metadata about indexed files

```sql
-- What's inside:
-- - path: File path
-- - source: "memory" or "sessions"
-- - hash: File content hash (detect changes)
-- - mtime: Last modified time
-- - size: File size in bytes
```

**Example query:**
```sql
SELECT path, size, datetime(mtime, 'unixepoch') as modified 
FROM files;
```

---

### 3. `meta` - Database Metadata
**What it stores**: Configuration and version info

```sql
-- Key-value pairs for database settings
SELECT * FROM meta;
```

---

## 🔍 FTS5 System (Keyword Search)

### 4. `chunks_fts` - FTS5 Virtual Table
**What it does**: Full-text search index (BM25 ranking)

**⚠️ Important:** The `MATCH` operator only works with FTS5 virtual tables, not regular SQLite tables.

**This is the main table you query:**
```sql
-- Search for keyword
SELECT id, path, bm25(chunks_fts) as score
FROM chunks_fts
WHERE chunks_fts MATCH 'SQLite'
ORDER BY score ASC
LIMIT 5;
```

### Supporting FTS5 Tables (Don't touch these!)

#### `chunks_fts_config` - FTS5 Configuration
- Internal FTS5 settings
- Created automatically by SQLite

#### `chunks_fts_content` - Indexed Content
- Stores the actual text being indexed
- Used by FTS5 internally

#### `chunks_fts_data` - Inverted Index
- The actual search index (word → document mapping)
- This is what makes keyword search fast

#### `chunks_fts_docsize` - Document Sizes
- Stores document lengths
- Used for BM25 scoring

#### `chunks_fts_idx` - Index Metadata
- Segment and term information
- FTS5 internal bookkeeping

**You never query these directly** - they're managed by FTS5.

---

## 🎯 Vector System (Semantic Search)

### 5. `chunks_vec` - Vector Virtual Table
**What it does**: Vector similarity search (cosine distance)

**This is the main table you query:**
```sql
-- Vector search (if extension loaded)
SELECT id, vec_distance_cosine(embedding, ?) as distance
FROM chunks_vec
ORDER BY distance ASC
LIMIT 5;
```

### Supporting Vector Tables (Don't touch these!)

#### `chunks_vec_info` - Vector Configuration
- Stores vector dimensions (3072 in your case)
- Metadata about the vector index

```sql
-- Check vector dimensions
SELECT * FROM chunks_vec_info;
```

#### `chunks_vec_chunks` - Vector Storage Chunks
- Stores vectors in compressed chunks
- Optimizes storage and retrieval

#### `chunks_vec_rowids` - Row ID Mapping
- Maps chunk IDs to internal rowids
- Used for fast lookups

#### `chunks_vec_vector_chunks00` - Actual Vector Data
- The raw vector embeddings
- Binary blob storage

**You never query these directly** - they're managed by sqlite-vec.

---

## 💾 Performance Cache

### 6. `embedding_cache` - Embedding Cache
**What it stores**: Previously computed embeddings

```sql
-- What's inside:
-- - provider: "gemini", "openai", etc.
-- - model: "gemini-embedding-001"
-- - hash: Content hash
-- - embedding: Cached vector
-- - dims: Dimensions (3072)
-- - updated_at: Cache timestamp
```

**Why it exists**: Avoid re-computing embeddings for same text

**Example query:**
```sql
SELECT provider, model, COUNT(*) as cached_count, dims
FROM embedding_cache
GROUP BY provider, model, dims;
```

---

## 🎨 Visual Summary

```
┌─────────────────────────────────────────────────┐
│  YOUR DATA (Query these)                        │
├─────────────────────────────────────────────────┤
│  chunks              → Main content             │
│  files               → File metadata            │
│  meta                → Database config          │
│  embedding_cache     → Performance cache        │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  FTS5 SEARCH (Query chunks_fts)                 │
├─────────────────────────────────────────────────┤
│  chunks_fts          → Main FTS5 table          │
│  ├─ chunks_fts_config                           │
│  ├─ chunks_fts_content                          │
│  ├─ chunks_fts_data     (inverted index)        │
│  ├─ chunks_fts_docsize                          │
│  └─ chunks_fts_idx                              │
└─────────────────────────────────────────────────┘
                    ↓
┌─────────────────────────────────────────────────┐
│  VECTOR SEARCH (Query chunks_vec)               │
├─────────────────────────────────────────────────┤
│  chunks_vec          → Main vector table        │
│  ├─ chunks_vec_info                             │
│  ├─ chunks_vec_chunks                           │
│  ├─ chunks_vec_rowids                           │
│  └─ chunks_vec_vector_chunks00                  │
└─────────────────────────────────────────────────┘
```

---

## 🔧 Practical Usage

### What You Should Query

**1. View your memories:**
```sql
SELECT path, substr(text, 1, 100) FROM chunks;
```

**2. Keyword search:**
```sql
SELECT id, path, bm25(chunks_fts) as score
FROM chunks_fts
WHERE chunks_fts MATCH 'your search term'
ORDER BY score ASC;
```

**3. Check cache:**
```sql
SELECT provider, model, COUNT(*) FROM embedding_cache GROUP BY provider, model;
```

**4. File list:**
```sql
SELECT path, size FROM files;
```

### What You Should NOT Query

❌ `chunks_fts_data` - Internal FTS5 index  
❌ `chunks_fts_idx` - Internal FTS5 metadata  
❌ `chunks_vec_chunks` - Internal vector storage  
❌ `chunks_vec_vector_chunks00` - Raw vector data  

**These are managed automatically by SQLite extensions.**

---

## 🧪 Test Queries

### Count everything:
```sql
SELECT 'chunks' as table_name, COUNT(*) FROM chunks
UNION ALL
SELECT 'files', COUNT(*) FROM files
UNION ALL
SELECT 'fts_entries', COUNT(*) FROM chunks_fts
UNION ALL
SELECT 'cached_embeddings', COUNT(*) FROM embedding_cache;
```

### Search example:
```sql
-- Keyword search
SELECT 
    c.path,
    substr(c.text, 1, 80) as preview,
    f.bm25_score
FROM chunks c
JOIN (
    SELECT id, bm25(chunks_fts) as bm25_score
    FROM chunks_fts
    WHERE chunks_fts MATCH 'memory'
) f ON f.id = c.id
ORDER BY f.bm25_score ASC
LIMIT 5;
```

### Check vector dimensions:
```sql
SELECT key, value FROM chunks_vec_info WHERE key = 'dimensions';
```

---

## 📚 Table Relationships

```
files (1) ──────┬───── (many) chunks
                │
                └───── (many) chunks_fts (virtual)
                │
                └───── (many) chunks_vec (virtual)

embedding_cache (independent cache)
```

**Key insight**: 
- `chunks` is the source of truth
- `chunks_fts` and `chunks_vec` are **indexes** pointing to `chunks`
- All three share the same `id` field

---

## 🎯 For Your Research

### Tables You'll Use:

1. **`chunks`** - Get actual content
2. **`chunks_fts`** - Keyword search (BM25 scores)
3. **`chunks_vec`** - Vector search (cosine similarity)
4. **`embedding_cache`** - Check what's cached

### Tables You'll Ignore:

- All `chunks_fts_*` internal tables
- All `chunks_vec_*` internal tables (except `chunks_vec` itself)

### Your Unified Operator Will:

```sql
-- Instead of two queries:
-- 1. SELECT FROM chunks_fts WHERE MATCH ...
-- 2. SELECT FROM chunks_vec ORDER BY distance ...
-- 3. Merge in JavaScript

-- You'll do one query:
SELECT * FROM vtab_hybrid 
WHERE fts_match(?, text) 
  AND vector_distance(?, embedding) < 0.8
ORDER BY hybrid_score DESC;
```

---

## 💡 Quick Reference

| Table | Type | Purpose | Query It? |
|-------|------|---------|-----------|
| `chunks` | Real | Main data | ✅ Yes |
| `files` | Real | File tracking | ✅ Yes |
| `meta` | Real | Config | ✅ Yes |
| `embedding_cache` | Real | Performance | ✅ Yes |
| `chunks_fts` | Virtual | Keyword search | ✅ Yes |
| `chunks_fts_*` | Internal | FTS5 internals | ❌ No |
| `chunks_vec` | Virtual | Vector search | ✅ Yes |
| `chunks_vec_*` | Internal | Vector internals | ❌ No |

---

**Summary**: You have 4 tables to query (`chunks`, `files`, `chunks_fts`, `chunks_vec`) and 10 internal tables you can ignore!
