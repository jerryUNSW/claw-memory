#!/bin/bash
# Interactive OpenClaw Database Query Tool

DB_PATH="$HOME/.openclaw/memory/main.sqlite"

if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database not found at $DB_PATH"
    exit 1
fi

echo "================================================"
echo "🔍 OpenClaw Memory Database Query Tool"
echo "================================================"
echo ""

# Function to run a query section
run_query() {
    local title="$1"
    local query="$2"
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "📊 $title"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    sqlite3 "$DB_PATH" <<EOF
.mode column
.headers on
.width 15 30 10 60 15
$query
EOF
    echo ""
}

# 1. Overview
run_query "Database Overview" "
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
"

# 2. Memory Files
run_query "Memory Files" "
SELECT 
    path,
    source,
    datetime(mtime, 'unixepoch') as last_modified,
    size as size_bytes
FROM files
ORDER BY mtime DESC
LIMIT 10;
"

# 3. Recent Chunks
run_query "Recent Memory Chunks (Last 5)" "
SELECT 
    substr(id, 1, 12) as chunk_id,
    substr(path, 1, 30) as path,
    start_line || '-' || end_line as lines,
    substr(text, 1, 80) as preview
FROM chunks
ORDER BY updated_at DESC
LIMIT 5;
"

# 4. Embedding Info
run_query "Embedding Configuration" "
SELECT 
    provider,
    model,
    COUNT(*) as cached_count,
    dims as dimensions
FROM embedding_cache
GROUP BY provider, model, dims;
"

# 5. FTS5 Search Example
run_query "FTS5 Search: 'SQLite' (Top 3)" "
SELECT 
    substr(id, 1, 12) as chunk_id,
    substr(path, 1, 30) as path,
    substr(text, 1, 80) as snippet,
    ROUND(bm25(chunks_fts), 2) as bm25_score
FROM chunks_fts
WHERE chunks_fts MATCH 'SQLite'
ORDER BY bm25(chunks_fts) ASC
LIMIT 3;
"

# 6. Hybrid Index Coverage
run_query "Hybrid Index Coverage" "
SELECT 
    'Chunks with Vector' as index_type,
    COUNT(*) as count
FROM chunks c
WHERE EXISTS (SELECT 1 FROM chunks_vec v WHERE v.id = c.id)
UNION ALL
SELECT 
    'Chunks with FTS',
    COUNT(*)
FROM chunks c
WHERE EXISTS (SELECT 1 FROM chunks_fts f WHERE f.id = c.id)
UNION ALL
SELECT 
    'Chunks with BOTH',
    COUNT(*)
FROM chunks c
WHERE EXISTS (SELECT 1 FROM chunks_vec v WHERE v.id = c.id)
  AND EXISTS (SELECT 1 FROM chunks_fts f WHERE f.id = c.id);
"

# 7. Memory by Source
run_query "Memory Distribution by Source" "
SELECT 
    source,
    COUNT(*) as chunks,
    ROUND(SUM(LENGTH(text))/1024.0, 2) as total_kb,
    ROUND(AVG(LENGTH(text)), 0) as avg_chars
FROM chunks
GROUP BY source;
"

# 8. Temporal Distribution
run_query "Memory Age Distribution" "
SELECT 
    CASE 
        WHEN julianday('now') - julianday(updated_at, 'unixepoch') < 7 THEN '0-7 days'
        WHEN julianday('now') - julianday(updated_at, 'unixepoch') < 30 THEN '7-30 days'
        WHEN julianday('now') - julianday(updated_at, 'unixepoch') < 90 THEN '30-90 days'
        ELSE '90+ days'
    END as age_bucket,
    COUNT(*) as chunks
FROM chunks
GROUP BY age_bucket
ORDER BY MIN(julianday('now') - julianday(updated_at, 'unixepoch'));
"

echo "================================================"
echo "✅ Query complete!"
echo ""
echo "💡 Tips:"
echo "  - Full query file: scripts/openclaw_queries.sql"
echo "  - Interactive mode: sqlite3 $DB_PATH"
echo "  - Custom query: sqlite3 $DB_PATH 'SELECT * FROM chunks LIMIT 5;'"
echo "================================================"
