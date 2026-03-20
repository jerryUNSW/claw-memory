-- OpenClaw Memory Database Queries
-- Database: ~/.openclaw/memory/main.sqlite

-- ============================================
-- 1. OVERVIEW: What's in the database?
-- ============================================

-- Count all records
SELECT 
    'Total Files' as metric, COUNT(*) as count FROM files
UNION ALL
SELECT 'Total Chunks', COUNT(*) FROM chunks
UNION ALL
SELECT 'FTS Entries', COUNT(*) FROM chunks_fts
UNION ALL
SELECT 'Vector Entries', COUNT(*) FROM chunks_vec
UNION ALL
SELECT 'Cached Embeddings', COUNT(*) FROM embedding_cache;

-- ============================================
-- 2. MEMORY CONTENT: What memories exist?
-- ============================================

-- Show all memory files
SELECT 
    path,
    source,
    datetime(mtime, 'unixepoch') as last_modified,
    size as size_bytes
FROM files
ORDER BY mtime DESC;

-- Show recent memory chunks with preview
SELECT 
    substr(id, 1, 12) as chunk_id,
    path,
    start_line || '-' || end_line as lines,
    substr(text, 1, 100) as preview,
    source,
    datetime(updated_at, 'unixepoch') as updated
FROM chunks
ORDER BY updated_at DESC
LIMIT 10;

-- ============================================
-- 3. EMBEDDING ANALYSIS
-- ============================================

-- Embedding provider info
SELECT 
    provider,
    model,
    COUNT(*) as cached_count,
    dims as dimensions,
    datetime(MAX(updated_at), 'unixepoch') as last_updated
FROM embedding_cache
GROUP BY provider, model, dims;

-- Check vector dimensions
SELECT value as vector_dimensions
FROM chunks_vec_info
WHERE key = 'dimensions';

-- ============================================
-- 4. SEARCH EXAMPLES
-- ============================================

-- FTS5 Keyword Search Example
-- Search for "SQLite" in memory
SELECT 
    id,
    substr(path, 1, 40) as path,
    start_line,
    substr(text, 1, 150) as snippet,
    bm25(chunks_fts) as relevance_score
FROM chunks_fts
WHERE chunks_fts MATCH 'SQLite'
ORDER BY bm25(chunks_fts) ASC
LIMIT 5;

-- FTS5 Search for "bug" or "error"
SELECT 
    id,
    substr(path, 1, 40) as path,
    substr(text, 1, 150) as snippet,
    bm25(chunks_fts) as relevance_score
FROM chunks_fts
WHERE chunks_fts MATCH 'bug OR error'
ORDER BY bm25(chunks_fts) ASC
LIMIT 5;

-- ============================================
-- 5. HYBRID RETRIEVAL SIMULATION
-- ============================================

-- Show chunks that would be retrieved by both FTS and vector search
-- (This simulates what OpenClaw does)
SELECT 
    c.id,
    c.path,
    c.start_line,
    substr(c.text, 1, 100) as text_preview,
    CASE 
        WHEN v.id IS NOT NULL THEN '✅ Has Vector'
        ELSE '❌ No Vector'
    END as vector_status,
    CASE 
        WHEN f.id IS NOT NULL THEN '✅ In FTS'
        ELSE '❌ Not in FTS'
    END as fts_status
FROM chunks c
LEFT JOIN chunks_vec v ON v.id = c.id
LEFT JOIN chunks_fts f ON f.id = c.id
LIMIT 10;

-- ============================================
-- 6. MEMORY STATISTICS
-- ============================================

-- Memory by source
SELECT 
    source,
    COUNT(*) as chunk_count,
    SUM(LENGTH(text)) as total_chars,
    AVG(LENGTH(text)) as avg_chunk_size
FROM chunks
GROUP BY source;

-- Memory by file
SELECT 
    path,
    COUNT(*) as chunks,
    SUM(LENGTH(text)) as total_chars,
    MIN(start_line) as first_line,
    MAX(end_line) as last_line
FROM chunks
GROUP BY path
ORDER BY chunks DESC;

-- ============================================
-- 7. TEMPORAL ANALYSIS
-- ============================================

-- Memory creation timeline
SELECT 
    DATE(updated_at, 'unixepoch') as date,
    COUNT(*) as chunks_created
FROM chunks
GROUP BY DATE(updated_at, 'unixepoch')
ORDER BY date DESC
LIMIT 30;

-- Age distribution (for temporal decay research)
SELECT 
    CASE 
        WHEN julianday('now') - julianday(updated_at, 'unixepoch') < 7 THEN '0-7 days (recent)'
        WHEN julianday('now') - julianday(updated_at, 'unixepoch') < 30 THEN '7-30 days (medium)'
        WHEN julianday('now') - julianday(updated_at, 'unixepoch') < 90 THEN '30-90 days (old)'
        ELSE '90+ days (archived)'
    END as age_bucket,
    COUNT(*) as chunk_count
FROM chunks
GROUP BY age_bucket;

-- ============================================
-- 8. RESEARCH-SPECIFIC QUERIES
-- ============================================

-- Find chunks suitable for hybrid retrieval testing
-- (Has both keyword matches and vector embeddings)
SELECT 
    c.id,
    c.path,
    LENGTH(c.text) as text_length,
    c.text LIKE '%SQLite%' as has_sqlite_keyword,
    c.text LIKE '%vector%' as has_vector_keyword,
    c.text LIKE '%search%' as has_search_keyword,
    julianday('now') - julianday(c.updated_at, 'unixepoch') as age_days
FROM chunks c
WHERE c.id IN (SELECT id FROM chunks_vec)
  AND c.id IN (SELECT id FROM chunks_fts)
LIMIT 20;

-- Estimate RRF candidate set size
-- (How many results would FTS5 and vector search return?)
SELECT 
    'FTS5 candidates' as search_type,
    COUNT(*) as result_count
FROM chunks_fts
WHERE chunks_fts MATCH 'SQLite'
UNION ALL
SELECT 
    'Vector candidates',
    COUNT(*)
FROM chunks_vec;
