#!/usr/bin/env python3
"""
OpenClaw Database Query Tool
Properly loads sqlite-vec extension for vector queries
"""

import sqlite3
import os
from pathlib import Path

DB_PATH = Path.home() / ".openclaw" / "memory" / "main.sqlite"

def load_vec_extension(conn):
    """Try to load sqlite-vec extension"""
    # Common paths for sqlite-vec
    possible_paths = [
        "/opt/homebrew/lib/vec0.dylib",
        "/usr/local/lib/vec0.dylib",
        str(Path.home() / ".openclaw" / "extensions" / "vec0.dylib"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            try:
                conn.enable_load_extension(True)
                conn.load_extension(path.replace('.dylib', ''))
                print(f"✅ Loaded sqlite-vec from: {path}")
                return True
            except Exception as e:
                continue
    
    print("⚠️  sqlite-vec extension not found (vector queries will fail)")
    return False

def run_query(conn, title, query):
    """Run a query and display results"""
    print(f"\n{'='*60}")
    print(f"📊 {title}")
    print('='*60)
    
    try:
        cursor = conn.execute(query)
        rows = cursor.fetchall()
        
        if not rows:
            print("(No results)")
            return
        
        # Print column headers
        headers = [desc[0] for desc in cursor.description]
        print(" | ".join(f"{h:20}" for h in headers))
        print("-" * (len(headers) * 23))
        
        # Print rows
        for row in rows[:10]:  # Limit to 10 rows
            print(" | ".join(f"{str(v)[:20]:20}" for v in row))
        
        if len(rows) > 10:
            print(f"\n... ({len(rows) - 10} more rows)")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def main():
    if not DB_PATH.exists():
        print(f"❌ Database not found: {DB_PATH}")
        return
    
    print("="*60)
    print("🔍 OpenClaw Memory Database Explorer")
    print(f"📁 Database: {DB_PATH}")
    print("="*60)
    
    # Connect to database
    conn = sqlite3.connect(str(DB_PATH))
    
    # Try to load vec extension
    vec_loaded = load_vec_extension(conn)
    
    # 1. Overview
    run_query(conn, "Database Overview", """
        SELECT 
            'Total Files' as metric, COUNT(*) as count FROM files
        UNION ALL
        SELECT 'Total Chunks', COUNT(*) FROM chunks
        UNION ALL
        SELECT 'FTS Entries', COUNT(*) FROM chunks_fts
        UNION ALL
        SELECT 'Cached Embeddings', COUNT(*) FROM embedding_cache
    """)
    
    # 2. Memory Files
    run_query(conn, "Memory Files", """
        SELECT 
            path,
            source,
            datetime(mtime, 'unixepoch') as last_modified,
            size as size_bytes
        FROM files
        ORDER BY mtime DESC
        LIMIT 5
    """)
    
    # 3. Recent Chunks
    run_query(conn, "Recent Memory Chunks", """
        SELECT 
            substr(id, 1, 12) as chunk_id,
            substr(path, 1, 30) as path,
            start_line || '-' || end_line as lines,
            substr(text, 1, 60) as preview
        FROM chunks
        ORDER BY updated_at DESC
        LIMIT 5
    """)
    
    # 4. Embedding Info
    run_query(conn, "Embedding Configuration", """
        SELECT 
            provider,
            model,
            COUNT(*) as cached_count,
            dims as dimensions
        FROM embedding_cache
        GROUP BY provider, model, dims
    """)
    
    # 5. FTS5 Search
    run_query(conn, "FTS5 Search: 'memory' (Top 5)", """
        SELECT 
            substr(id, 1, 12) as chunk_id,
            substr(path, 1, 30) as path,
            ROUND(bm25(chunks_fts), 2) as bm25_score,
            substr(text, 1, 60) as snippet
        FROM chunks_fts
        WHERE chunks_fts MATCH 'memory'
        ORDER BY bm25(chunks_fts) ASC
        LIMIT 5
    """)
    
    # 6. Vector table check
    if vec_loaded:
        run_query(conn, "Vector Index Stats", """
            SELECT 
                COUNT(*) as total_vectors,
                (SELECT value FROM chunks_vec_info WHERE key = 'dimensions') as dimensions
            FROM chunks_vec
        """)
        
        run_query(conn, "Hybrid Coverage", """
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
              AND EXISTS (SELECT 1 FROM chunks_fts f WHERE f.id = c.id)
        """)
    
    # 7. Memory Distribution
    run_query(conn, "Memory by Source", """
        SELECT 
            source,
            COUNT(*) as chunks,
            ROUND(SUM(LENGTH(text))/1024.0, 2) as total_kb,
            ROUND(AVG(LENGTH(text)), 0) as avg_chars
        FROM chunks
        GROUP BY source
    """)
    
    # 8. Temporal Distribution
    run_query(conn, "Memory Age Distribution", """
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
        ORDER BY MIN(julianday('now') - julianday(updated_at, 'unixepoch'))
    """)
    
    # 9. Sample memory content
    run_query(conn, "Sample Memory Content", """
        SELECT 
            substr(path, 1, 30) as file,
            substr(text, 1, 100) as content_preview
        FROM chunks
        ORDER BY updated_at DESC
        LIMIT 3
    """)
    
    conn.close()
    
    print("\n" + "="*60)
    print("✅ Exploration complete!")
    print("\n💡 Tips:")
    print(f"  - Interactive: python3 -i {__file__}")
    print(f"  - Direct SQL: sqlite3 {DB_PATH}")
    print(f"  - Full queries: scripts/openclaw_queries.sql")
    print("="*60)

if __name__ == "__main__":
    main()
