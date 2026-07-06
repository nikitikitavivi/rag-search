The minimal pipeline

docs → chunk → embed → vector index → retrieve → rerank → prompt+LLM → answer(+citations)

1. Ingestion & chunking (highest-leverage step)
Chunk to ~256–512 tokens with ~10–20% overlap. Start here; it beats most fancy schemes.

Split on structure first (Markdown headers, code blocks, sentences) — not blind fixed windows. Use LangChain/LlamaIndex RecursiveCharacterTextSplitter.

Parent-child (small-to-big): embed small chunks for precision, return the larger parent for context. Biggest quality win for the least effort.

Attach metadata (title, section, source URL, date) — you need it for filtering and citations.

2. Embeddings
Open-source default: BAAI/bge-large-en-v1.5 or gte-large (or multilingual bge-m3). Hosted: OpenAI text-embedding-3-large, Cohere, Voyage.

Match query vs document mode if the model is asymmetric (BGE wants a query instruction prefix).

Normalize vectors and use cosine similarity.

Cache embeddings by content hash; batch your calls.

3. Vector store
Local/prototype: FAISS or Chroma. Production: Qdrant, Weaviate, Milvus, or pgvector (Postgres) if you want SQL + metadata filters in one place.

Managed: Pinecone.

Index type: flat for <100k vectors; HNSW or IVF for millions.

4. Retrieval (this is where quality is won or lost)
Go hybrid: dense (vectors) + sparse (BM25) fused with RRF. Reliably beats either alone, especially for exact terms/codes/names. (BM25 via Elasticsearch/OpenSearch or rank_bm25.)

Retrieve wide, then rerank narrow: pull top ~50–100 candidates, then a cross-encoder reranker (bge-reranker-v2-m3, or Cohere Rerank API) cuts to top 3–5.

Threshold on relevance, not raw top-k — drop weak matches so you don't feed the LLM noise.

5. Prompt / generation
"Open-book exam" prompt: "Answer only from the context below. If it's not there, say you don't know. Cite sources." This is the single biggest hallucination reducer.

Pass 3–5 high-quality chunks, not 20 — more context often hurts.

Return citations (chunk → source) so answers are verifiable.

6. Evaluation (don't skip — build it early)
Frozen golden set of 25–100 real questions with known-correct answers.

Retrieval metrics: Recall@k, nDCG@k, MRR. Answer metrics: groundedness/faithfulness, correctness.

Tools: Ragas, TruLens, or DeepEval. Use LLM-as-judge but calibrate it against a few human labels — judges silently inflate scores.

Change one variable at a time so you know what moved the needle.

Top pitfalls
Garbage in = garbage out, amplified. Clean/dedup your source data first.

Stale index — rebuild when docs change.

Query/doc embedding mismatch (wrong model or mode) silently kills recall.

Optimizing retrieval recall while ignoring end-to-end answer quality.

RAG is for dynamic factual grounding — use fine-tuning for style/behavior, long-context for a small fixed working set.

Fastest path to a working v1
LlamaIndex or LangChain + Chroma/FAISS + BGE embeddings + BGE reranker + any LLM API + Ragas for eval. Get that end-to-end, then upgrade to hybrid retrieval and parent-child chunking once your eval set tells you where it’s weak.

Order of tuning effort → payoff: chunking → hybrid retrieval → reranking → prompt grounding → embedding model. Tackle in that order.