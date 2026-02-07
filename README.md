# Document-Grounded Archives (DGA)

MVP pipeline:
1) ingest (registry-driven download + hashing + manifest)
2) process (page extract + OCR)
3) safety (PII redaction + risk skip)
4) index (chunk + embeddings + FAISS)
5) search (keyword + semantic)
6) answer (retrieval-gated + citations + uncertainty)
