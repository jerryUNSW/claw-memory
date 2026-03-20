#!/bin/bash
# Script to explore OpenClaw's SQLite database

DB_PATH="$HOME/.openclaw/memory/main.sqlite"

echo "================================================"
echo "OpenClaw Memory Database Explorer"
echo "Database: $DB_PATH"
echo "================================================"
echo ""

# Check if database exists
if [ ! -f "$DB_PATH" ]; then
    echo "❌ Database not found at $DB_PATH"
    exit 1
fi

echo "✅ Database found!"
echo ""

# 1. Show all tables
echo "📊 Tables in database:"
echo "================================================"
sqlite3 "$DB_PATH" ".tables"
echo ""

# 2. Show schema for each table
echo "📋 Database Schema:"
echo "================================================"
sqlite3 "$DB_PATH" ".schema"
echo ""

# 3. Count records in each table
echo "📈 Record Counts:"
echo "================================================"
sqlite3 "$DB_PATH" <<EOF
SELECT 'files' as table_name, COUNT(*) as count FROM files
UNION ALL
SELECT 'chunks', COUNT(*) FROM chunks
UNION ALL
SELECT 'fts_chunks', COUNT(*) FROM fts_chunks
UNION ALL
SELECT 'embedding_cache', COUNT(*) FROM embedding_cache;
EOF
echo ""

# 4. Show sample chunks
echo "📝 Sample Memory Chunks (first 3):"
echo "================================================"
sqlite3 "$DB_PATH" <<EOF
.mode column
.headers on
SELECT 
    substr(id, 1, 20) as id,
    substr(path, 1, 30) as path,
    start_line,
    end_line,
    substr(text, 1, 60) as text_preview,
    source
FROM chunks
LIMIT 3;
EOF
echo ""

# 5. Show embedding cache stats
echo "🔢 Embedding Cache Statistics:"
echo "================================================"
sqlite3 "$DB_PATH" <<EOF
.mode column
.headers on
SELECT 
    provider,
    model,
    COUNT(*) as cached_embeddings,
    AVG(dims) as avg_dimensions
FROM embedding_cache
GROUP BY provider, model;
EOF
echo ""

# 6. Check if vector table exists
echo "🔍 Checking for Vector Index:"
echo "================================================"
sqlite3 "$DB_PATH" "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%vec%';"
echo ""

# 7. Show recent files indexed
echo "📁 Recently Indexed Files (last 5):"
echo "================================================"
sqlite3 "$DB_PATH" <<EOF
.mode column
.headers on
SELECT 
    substr(path, 1, 50) as path,
    source,
    datetime(indexed_at, 'unixepoch') as indexed_time
FROM files
ORDER BY indexed_at DESC
LIMIT 5;
EOF
echo ""

echo "================================================"
echo "✅ Exploration complete!"
echo "================================================"
