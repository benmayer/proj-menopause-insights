"""Chunk rag_docs/*.md by '## ' heading, embed, upsert into Supabase `documents`.

Usage: python -m app.rag.ingest      (idempotent: re-running updates changed chunks)
File header lines: `section: ...` and `source: ...`, then blank line, then '## Title' blocks.
"""
from pathlib import Path

from app.rag.clients import embed, supabase_client

DOCS = Path(__file__).resolve().parent.parent.parent / "rag_docs"


def parse(path: Path) -> list[dict]:
    head, _, body = path.read_text().partition("\n## ")
    meta = dict(line.split(": ", 1) for line in head.strip().splitlines() if ": " in line)
    chunks = []
    for block in ("## " + body).split("\n## "):
        block = block.strip().removeprefix("## ")
        title, _, text = block.partition("\n")
        if text.strip():
            chunks.append({"section": meta["section"], "title": title.strip(),
                           "content": f"{title.strip()}\n{text.strip()}", "source": meta.get("source")})
    return chunks


def main() -> int:
    chunks = [c for f in sorted(DOCS.glob("*.md")) for c in parse(f)]
    vectors = embed([c["content"] for c in chunks])
    rows = [{**c, "embedding": v} for c, v in zip(chunks, vectors)]
    supabase_client().table("documents").upsert(rows, on_conflict="section,title").execute()
    print(f"ingested {len(rows)} chunks from {len(list(DOCS.glob('*.md')))} files")
    return len(rows)


if __name__ == "__main__":
    main()
