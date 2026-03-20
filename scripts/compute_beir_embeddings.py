#!/usr/bin/env python3
"""
Compute and store real vector embeddings for BEIR dataset

This script:
1. Downloads BEIR dataset (e.g., nfcorpus)
2. Computes embeddings using sentence-transformers
3. Stores embeddings in SQLite database with sqlite-vec
4. Creates proper vector index for cosine similarity search

Usage:
    python3 scripts/compute_beir_embeddings.py --dataset nfcorpus
"""

import argparse
import sqlite3
import struct
from pathlib import Path
from tqdm import tqdm
from sentence_transformers import SentenceTransformer
from beir import util
from beir.datasets.data_loader import GenericDataLoader
import sqlite_vec

def serialize_f32(vector):
    """Serialize float32 vector for sqlite-vec"""
    return struct.pack(f'{len(vector)}f', *vector)

def create_database(db_path: Path, corpus: dict, queries: dict, qrels: dict):
    """Create SQLite database with BEIR data"""
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    
    # Create tables
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            id TEXT PRIMARY KEY,
            path TEXT,
            text TEXT,
            title TEXT,
            updated_at INTEGER DEFAULT 0
        )
    """)
    
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
            id UNINDEXED,
            path UNINDEXED,
            text,
            content=chunks,
            content_rowid=rowid
        )
    """)
    
    # Insert corpus
    print("Inserting corpus into database...")
    for doc_id, doc in tqdm(corpus.items(), desc="Corpus"):
        title = doc.get('title', '')
        text = doc.get('text', '')
        full_text = f"{title} {text}".strip()
        
        conn.execute("""
            INSERT INTO chunks (id, path, text, title)
            VALUES (?, ?, ?, ?)
        """, (doc_id, f"doc_{doc_id}", full_text, title))
        
        # Insert into FTS5
        conn.execute("""
            INSERT INTO chunks_fts (id, path, text)
            VALUES (?, ?, ?)
        """, (doc_id, f"doc_{doc_id}", full_text))
    
    # Store queries
    conn.execute("""
        CREATE TABLE IF NOT EXISTS queries (
            id TEXT PRIMARY KEY,
            text TEXT
        )
    """)
    
    for query_id, query_text in queries.items():
        conn.execute("""
            INSERT INTO queries (id, text)
            VALUES (?, ?)
        """, (query_id, query_text))
    
    # Store qrels (ground truth)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS qrels (
            query_id TEXT,
            doc_id TEXT,
            relevance INTEGER,
            PRIMARY KEY (query_id, doc_id)
        )
    """)
    
    for query_id, doc_rels in qrels.items():
        for doc_id, relevance in doc_rels.items():
            conn.execute("""
                INSERT INTO qrels (query_id, doc_id, relevance)
                VALUES (?, ?, ?)
            """, (query_id, doc_id, relevance))
    
    conn.commit()
    return conn

def compute_embeddings(conn, corpus: dict, model_name: str = 'all-MiniLM-L6-v2'):
    """Compute and store embeddings for all documents"""
    print(f"\nLoading embedding model: {model_name}")
    model = SentenceTransformer(model_name)
    embedding_dim = model.get_sentence_embedding_dimension()
    
    print(f"Embedding dimension: {embedding_dim}")
    
    # Create vector table
    print("Creating vector table...")
    conn.execute(f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS chunks_vec USING vec0(
            id TEXT PRIMARY KEY,
            embedding FLOAT[{embedding_dim}]
        )
    """)
    
    # Compute embeddings
    print("\nComputing embeddings...")
    batch_size = 32
    doc_ids = list(corpus.keys())
    
    for i in tqdm(range(0, len(doc_ids), batch_size), desc="Batches"):
        batch_ids = doc_ids[i:i+batch_size]
        batch_texts = []
        
        for doc_id in batch_ids:
            doc = corpus[doc_id]
            title = doc.get('title', '')
            text = doc.get('text', '')
            full_text = f"{title} {text}".strip()
            batch_texts.append(full_text)
        
        # Compute embeddings for batch
        embeddings = model.encode(batch_texts, show_progress_bar=False)
        
        # Store in database
        for doc_id, embedding in zip(batch_ids, embeddings):
            conn.execute("""
                INSERT INTO chunks_vec (id, embedding)
                VALUES (?, ?)
            """, (doc_id, serialize_f32(embedding)))
    
    conn.commit()
    print(f"✅ Stored {len(doc_ids)} embeddings")
    
    return model

def verify_embeddings(conn, model):
    """Verify embeddings are stored correctly"""
    print("\nVerifying embeddings...")
    
    # Count embeddings
    cursor = conn.execute("SELECT COUNT(*) FROM chunks_vec")
    count = cursor.fetchone()[0]
    print(f"Total embeddings: {count}")
    
    # Test vector search
    test_query = "What is cancer?"
    query_embedding = model.encode(test_query)
    
    cursor = conn.execute("""
        SELECT 
            chunks.id,
            chunks.title,
            vec_distance_cosine(chunks_vec.embedding, ?) as distance
        FROM chunks_vec
        JOIN chunks ON chunks.id = chunks_vec.id
        ORDER BY distance ASC
        LIMIT 5
    """, (serialize_f32(query_embedding),))
    
    print(f"\nTest query: '{test_query}'")
    print("Top 5 results:")
    for row in cursor:
        print(f"  {row[0]}: {row[1][:60]}... (distance: {row[2]:.4f})")
    
    print("\n✅ Vector search working!")

def main():
    parser = argparse.ArgumentParser(description='Compute BEIR embeddings')
    parser.add_argument('--dataset', type=str, default='nfcorpus',
                       help='BEIR dataset name (default: nfcorpus)')
    parser.add_argument('--model', type=str, default='all-MiniLM-L6-v2',
                       help='Sentence-transformers model (default: all-MiniLM-L6-v2)')
    args = parser.parse_args()
    
    print("=" * 80)
    print(f"🔬 Computing BEIR Embeddings: {args.dataset}")
    print("=" * 80)
    
    # Download dataset
    print(f"\nDownloading {args.dataset}...")
    url = f"https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/{args.dataset}.zip"
    data_path = util.download_and_unzip(url, "datasets")
    
    # Load dataset
    print("Loading dataset...")
    corpus, queries, qrels = GenericDataLoader(data_folder=data_path).load(split="test")
    
    print(f"\nDataset statistics:")
    print(f"  Corpus size: {len(corpus)}")
    print(f"  Queries: {len(queries)}")
    print(f"  Qrels: {sum(len(v) for v in qrels.values())}")
    
    # Create database
    db_path = Path(f"beir_{args.dataset}.db")
    if db_path.exists():
        print(f"\n⚠️  Database {db_path} already exists. Deleting...")
        db_path.unlink()
    
    print(f"\nCreating database: {db_path}")
    conn = create_database(db_path, corpus, queries, qrels)
    
    # Compute embeddings
    model = compute_embeddings(conn, corpus, args.model)
    
    # Verify
    verify_embeddings(conn, model)
    
    conn.close()
    
    print("\n" + "=" * 80)
    print(f"✅ Complete! Database saved to: {db_path}")
    print("=" * 80)
    print("\nNext steps:")
    print(f"  1. Update compare_rrf_vs_interleaved.py to use real embeddings")
    print(f"  2. Update benchmark_beir.py to use {db_path}")
    print(f"  3. Re-run benchmarks with real vector search")

if __name__ == "__main__":
    main()
