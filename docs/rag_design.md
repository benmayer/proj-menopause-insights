# RAG design

## Current settings (Phase 4, built)
| | |
|---|---|
| Store | Supabase Postgres + pgvector, table `documents` (`sql/001_documents.sql`) |
| Embedding model | OpenAI `text-embedding-3-small`, 1536 dims (`app/rag/clients.py`) |
| Chunking | By `## ` heading, one chunk per section. No size limit, **no overlap** |
| Chunk text | Heading + body (the heading helps matching) |
| Corpus | 8 files in `rag_docs/` → 13 chunks: reference ranges (NHS, STRAW+10) and report-section instructions |
| Search | Cosine similarity, top 3, optional filter by `section` (`match_documents`) |
| Access | RLS on, no policies; only the server-side secret key can read |
| Ingest | `python -m app.rag.ingest` (idempotent upsert on `section,title`) |
| Test | `tests/test_rag.py` (live): 4 queries return the expected chunk first |

Why heading-based, no overlap: the documents are short, hand-written, and each section is one idea. Overlap only helps when a split can cut an idea in half.

## Planned: large PDFs (symptoms and advice)
Same store and embedding model; **different ingestion pipeline**.

| Step | Approach |
|---|---|
| Extract | PyMuPDF or pypdf, page by page, keeping page numbers. Scanned PDFs need OCR first |
| Clean | Drop repeated headers/footers, page numbers, reference lists; fix hyphenation |
| Chunk | Size-based, about 400 tokens, 10-15% overlap (about 50 tokens), splitting at paragraph/heading boundaries first |
| Metadata | Document title, page, section heading, chunk id (add a `metadata jsonb` column) |
| Section tag | `knowledge`, separate from the instruction/reference sections, so report instructions are never crowded out by PDF text |
| Embed | Same model, batches of about 100 chunks. Cost is pennies even for thousands of pages |
| Dedupe | Hash each chunk; skip unchanged chunks on re-ingest |
| Retrieve | Top 5 from `knowledge`, with a minimum similarity cut-off; return title and page for citation |

The embedding model does not need to change; chunking and metadata do.

## Decided
- **Advice.** The PDFs are teaching material for professional menopause coaches. Advice from them may be passed on, close to the source wording and attributed (document + page), in a "Things that may help" report section (`rag_docs/instr_advice.md`). Guardrails: only from retrieved chunks; nuanced ("can help", "some people find"); no doses; never tell the reader to start, stop or change medication; hormone therapy/medication = "an option to discuss with a GP"; no diagnosis; disclaimer on every report.

## Open decisions for the PDFs
- **Check node.** It verifies numbers against stats. Quoted facts from PDFs need a second check: every claim must be traceable to a retrieved chunk (citation required).
- **Licensing / reuse.** Professional teaching material is usually copyrighted. Confirm you may use it and quote it near-verbatim in generated reports, especially in the public demo. If not, keep the PDF-grounded advice to local runs (like the Clue data) and use open sources in the demo. Check each PDF's licence. Keep the PDFs out of git (add `rag_pdfs/` to `.gitignore`). Chunks stored in Supabase are still derived copies, so only use sources you may reuse; prefer open guidance (NHS, NICE, WHO, society guidelines).
- **Quality over volume.** Many huge documents dilute retrieval. Start with 2-3 authoritative sources; evaluate with a small set of test questions, as in `tests/test_rag.py`.
