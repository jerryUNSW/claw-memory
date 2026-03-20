# What Happens When a Query Comes In?

## 🔍 Current OpenClaw Query Flow (RRF Approach)

When you search for "SQLite bug from yesterday", here's what happens:

---

## Step 1: Query Arrives in JavaScript

```javascript
// User query
const query = "SQLite bug from yesterday";

// OpenClaw's search function (manager-CIjpkmRY.js)
async search(query, options) {
    // Step 1: Embed the query
    const queryVec = await this.embedQueryWithTimeout(query);
    
    // Step 2: Run TWO separate SQL queries in parallel
    const keywordResults = await this.searchKeyword(query, 100);
    const vectorResults = await this.searchVector(queryVec, 100);
    
    // Step 3: Merge in JavaScript
    const merged = await this.mergeHybridResults({
        vector: vectorResults,
        keyword: keywordResults,
        vectorWeight: 0.5,
        textWeight: 0.3
    });
    
    return merged.slice(0, 10);
}
```

---

## Step 2: First SQL Query - FTS5 Keyword Search

### SQL Statement Triggered:

```sql
SELECT 
    id,
    path,
    source,
    start_line,
    end_line,
    text,
    bm25(chunks_fts) AS rank
FROM chunks_fts
WHERE chunks_fts MATCH 'SQLite bug yesterday'
ORDER BY rank ASC
LIMIT 100;
```

**⚠️ Important Note:** The `MATCH` operator only works with FTS5 (Full-Text Search) extension. It is NOT a standard SQLite feature. Regular tables must use `LIKE` or `=` for pattern matching.

### What Happens Inside SQLite:

```
1. SQLite Query Planner
   └─> Sees "chunks_fts MATCH" → Use FTS5 index

2. FTS5 Virtual Table Handler
   ├─> Parse query: "SQLite bug yesterday"
   ├─> Tokenize: ["sqlite", "bug", "yesterday"]
   └─> Look up in inverted index

3. chunks_fts_data (Inverted Index)
   ├─> "sqlite" → [doc1, doc5, doc12, ...]
   ├─> "bug" → [doc3, doc5, doc8, ...]
   └─> "yesterday" → [doc2, doc5, doc9, ...]

4. Compute BM25 Scores
   ├─> For each matching document
   ├─> Calculate: TF-IDF with document length normalization
   └─> Use chunks_fts_docsize for document lengths

5. Sort by BM25 Score
   └─> Return top 100 results
```

### Tables Accessed:
- `chunks_fts` (virtual table - entry point)
- `chunks_fts_data` (inverted index - actual search)
- `chunks_fts_docsize` (document lengths - for BM25)
- `chunks_fts_idx` (index metadata)

---

## Step 3: Second SQL Query - Vector Similarity Search

### SQL Statement Triggered:

```sql
SELECT 
    c.id,
    c.path,
    c.start_line,
    c.end_line,
    c.text,
    c.source,
    vec_distance_cosine(v.embedding, ?) AS dist
FROM chunks_vec v
JOIN chunks c ON c.id = v.id
WHERE c.model = 'gemini-embedding-001'
ORDER BY dist ASC
LIMIT 100;
```

### What Happens Inside SQLite:

```
1. SQLite Query Planner
   └─> Sees "vec_distance_cosine" → Use vector index

2. sqlite-vec Extension Handler
   ├─> Get query vector: [0.123, 0.456, ..., 0.789] (3072 dims)
   └─> Scan all vectors (brute force for sqlite-vec)

3. chunks_vec_vector_chunks00 (Vector Storage)
   ├─> Read all 30 embeddings
   ├─> For each: compute cosine_distance(query_vec, stored_vec)
   └─> Keep track of distances

4. Sort by Distance
   └─> Return top 100 closest vectors

5. JOIN with chunks table
   └─> Get full text content for each result
```

### Tables Accessed:
- `chunks_vec` (virtual table - entry point)
- `chunks_vec_vector_chunks00` (actual vector storage)
- `chunks_vec_rowids` (ID mapping)
- `chunks` (join to get full content)

---

## Step 4: Merge in JavaScript (Application Layer)

```javascript
// This happens OUTSIDE SQLite, in Node.js

function mergeHybridResults(keywordResults, vectorResults) {
    const byId = new Map();
    
    // Add keyword results
    for (const result of keywordResults) {
        byId.set(result.id, {
            id: result.id,
            path: result.path,
            text: result.text,
            textScore: normalizeScore(result.bm25_score),
            vectorScore: 0
        });
    }
    
    // Add vector results
    for (const result of vectorResults) {
        if (byId.has(result.id)) {
            byId.get(result.id).vectorScore = 1 - result.distance;
        } else {
            byId.set(result.id, {
                id: result.id,
                path: result.path,
                text: result.text,
                textScore: 0,
                vectorScore: 1 - result.distance
            });
        }
    }
    
    // Compute hybrid scores
    const results = Array.from(byId.values()).map(doc => {
        doc.hybridScore = 0.5 * doc.vectorScore + 0.3 * doc.textScore;
        return doc;
    });
    
    // Sort by hybrid score
    return results.sort((a, b) => b.hybridScore - a.hybridScore);
}
```

---

## 📊 Table Types Explained

### Relational Tables (Standard SQL)

These are **real tables** stored on disk:

```sql
-- 1. chunks (Relational)
CREATE TABLE chunks (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding TEXT NOT NULL,  -- Serialized vector
    ...
);
-- Stored as: B-tree on disk
-- Access: Standard SQL SELECT

-- 2. files (Relational)
CREATE TABLE files (
    path TEXT PRIMARY KEY,
    hash TEXT NOT NULL,
    ...
);
-- Stored as: B-tree on disk

-- 3. embedding_cache (Relational)
CREATE TABLE embedding_cache (
    provider TEXT,
    model TEXT,
    hash TEXT,
    embedding TEXT,
    ...
    PRIMARY KEY (provider, model, provider_key, hash)
);
-- Stored as: B-tree on disk

-- 4. meta (Relational)
CREATE TABLE meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
-- Stored as: B-tree on disk
```

### Virtual Tables (NOT Relational)

These are **interfaces** to specialized indexes:

```sql
-- 1. chunks_fts (Virtual Table - FTS5)
CREATE VIRTUAL TABLE chunks_fts USING fts5(
    text,
    id UNINDEXED,
    ...
);
-- NOT stored as B-tree
-- Stored as: Inverted index (custom FTS5 format)
-- Access: Through FTS5 extension code
-- Backend tables: chunks_fts_data, chunks_fts_idx, etc.

-- 2. chunks_vec (Virtual Table - sqlite-vec)
CREATE VIRTUAL TABLE chunks_vec USING vec0(
    id TEXT PRIMARY KEY,
    embedding FLOAT[3072]
);
-- NOT stored as B-tree
-- Stored as: Compressed vector chunks (custom format)
-- Access: Through sqlite-vec extension code
-- Backend tables: chunks_vec_vector_chunks00, etc.
```

---

## 🔄 Comparison: Relational vs Virtual Tables

| Aspect | Relational Table | Virtual Table |
|--------|------------------|---------------|
| **Storage** | B-tree on disk | Custom format |
| **Access** | Standard SQL | Extension code |
| **Indexing** | B-tree indexes | Specialized (inverted index, vector index) |
| **Example** | `chunks`, `files` | `chunks_fts`, `chunks_vec` |
| **Query** | `SELECT * FROM chunks` | `SELECT * FROM chunks_fts WHERE MATCH ...` |
| **Backend** | Single table file | Multiple internal tables |

---

## 🎯 Visual Flow Diagram

```
User Query: "SQLite bug from yesterday"
           ↓
┌──────────────────────────────────────────────┐
│  JavaScript (Node.js)                        │
│  ┌────────────────────────────────────────┐ │
│  │ 1. Embed query → [0.1, 0.2, ..., 0.9] │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
           ↓
┌──────────────────────────────────────────────┐
│  SQLite Database                             │
│  ┌────────────────┐    ┌─────────────────┐ │
│  │ Query 1: FTS5  │    │ Query 2: Vector │ │
│  └────────┬───────┘    └────────┬────────┘ │
│           ↓                     ↓          │
│  ┌────────────────┐    ┌─────────────────┐ │
│  │ chunks_fts     │    │ chunks_vec      │ │
│  │ (Virtual)      │    │ (Virtual)       │ │
│  └────────┬───────┘    └────────┬────────┘ │
│           ↓                     ↓          │
│  ┌────────────────┐    ┌─────────────────┐ │
│  │ chunks_fts_data│    │ chunks_vec_     │ │
│  │ (Inverted idx) │    │ vector_chunks00 │ │
│  │ [Relational]   │    │ [Relational]    │ │
│  └────────┬───────┘    └────────┬────────┘ │
│           ↓                     ↓          │
│  100 keyword results    100 vector results │
└──────────────────────────────────────────────┘
           ↓                     ↓
┌──────────────────────────────────────────────┐
│  JavaScript (Node.js)                        │
│  ┌────────────────────────────────────────┐ │
│  │ Merge 200 results → RRF fusion        │ │
│  │ Sort by hybrid score                  │ │
│  │ Return top 10                         │ │
│  └────────────────────────────────────────┘ │
└──────────────────────────────────────────────┘
```

---

## 🔍 Detailed: What Each Table Type Does

### Relational Tables (B-tree Storage)

**How they work:**
```
1. Data stored in B-tree pages on disk
2. Primary key creates clustered index
3. Additional indexes create secondary B-trees
4. SQLite query planner chooses best index
5. Standard SQL operations (SELECT, JOIN, WHERE)
```

**Example: chunks table**
```
Disk Layout:
Page 1: [id="abc", path="memory/file.md", text="...", ...]
Page 2: [id="def", path="memory/file2.md", text="...", ...]
...

Index on id (primary key):
"abc" → Page 1, offset 0
"def" → Page 2, offset 0
...
```

### Virtual Tables (Custom Storage)

**How they work:**
```
1. SQLite calls extension code (not standard B-tree)
2. Extension manages its own storage format
3. Extension implements xFilter, xNext, xBestIndex
4. Can use multiple backend tables
5. Optimized for specific operations (search, similarity)
```

**Example: chunks_fts (FTS5)**
```
Storage Format (Inverted Index):
"sqlite" → [doc1:pos3, doc5:pos1, doc12:pos7, ...]
"bug" → [doc3:pos5, doc5:pos8, doc8:pos2, ...]
"yesterday" → [doc2:pos1, doc5:pos12, ...]

When you query "sqlite bug":
1. Look up "sqlite" → get doc list
2. Look up "bug" → get doc list
3. Intersect lists → docs with both terms
4. Compute BM25 scores
5. Return sorted results
```

**Example: chunks_vec (sqlite-vec)**
```
Storage Format (Compressed Vectors):
Chunk 0: [vec1, vec2, vec3, ...] (compressed)
Chunk 1: [vec11, vec12, vec13, ...] (compressed)
...

When you query with vector [0.1, 0.2, ...]:
1. Decompress all chunks
2. For each vector: compute cosine_distance(query, stored)
3. Keep top-k closest
4. Return sorted by distance
```

---

## 🎯 Your Research: Unified Operator

### Current (2 queries):
```sql
-- Query 1
SELECT * FROM chunks_fts WHERE MATCH 'SQLite' LIMIT 100;

-- Query 2  
SELECT * FROM chunks_vec ORDER BY distance LIMIT 100;

-- Merge in JavaScript (200 results → 10 results)
```

### Target (1 query):
```sql
-- Single unified query
SELECT * FROM vtab_hybrid 
WHERE fts_match(?, text) 
  AND vector_distance(?, embedding) < 0.8
ORDER BY hybrid_score DESC 
LIMIT 10;
```

### What vtab_hybrid will do internally:
```
1. Initialize TWO cursors:
   ├─ FTS5 cursor (chunks_fts)
   └─ Vector cursor (chunks_vec)

2. Interleaved traversal:
   ├─ Pull next from FTS5 → compute text_score
   ├─ Pull next from Vector → compute vector_score
   ├─ Compute hybrid_score = 0.5*vec + 0.3*text
   └─ Insert into priority queue

3. Early termination:
   └─ Stop when top-10 is stable (no need to scan all 200)

4. Return top 10 directly
   └─ No JavaScript merge needed!
```

---

## 📋 Summary

### Table Types:
- **4 Relational tables**: `chunks`, `files`, `embedding_cache`, `meta`
- **2 Virtual tables**: `chunks_fts`, `chunks_vec`
- **10 Backend tables**: Internal storage for virtual tables

### Query Flow:
1. JavaScript embeds query
2. SQL Query 1: FTS5 search (100 results)
3. SQL Query 2: Vector search (100 results)
4. JavaScript merges (200 → 10 results)

### Your Goal:
Replace steps 2-4 with a single unified query that does everything in SQLite!
