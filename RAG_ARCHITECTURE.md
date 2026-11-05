# Retrieval and RAG Architecture

## Implemented retrieval baseline

Ingestion stores title/content/source/provenance/hash. Search tokenizes Unicode text (including Bengali), computes lexical TF-IDF-style ranking over the owner's documents, returns ranked snippets and source attribution, and identifies itself as `lexical_tfidf_v1_not_vector`.

This provides real source-backed retrieval without pretending an embedding model or vector index exists. There is no generative RAG answer unless a caller separately supplies retrieved context to a configured model; automatic context assembly/reranking is not yet exposed.

## Target production pipeline

`Document ingestion → extraction → cleaning → chunking → evaluated embedding → pgvector indexing → PostgreSQL full-text + vector hybrid retrieval → optional reranker → source-bound context assembly → cited model answer`.

pgvector research verifies exact, HNSW and IVFFlat options and hybrid use with PostgreSQL full-text search. Index choice and embedding dimensions must be benchmarked on multilingual/Bengali data. Tenant filters must apply inside retrieval, not after exposing documents.

## Quality gates

Measure recall@k, citation correctness, Bengali tokenization/embedding quality, duplicate handling, deletion propagation and prompt-injection resistance. Vector storage does not establish truth; verification status and source URLs remain attached to every chunk.
