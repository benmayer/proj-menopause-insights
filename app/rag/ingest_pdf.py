"""Ingest the coaching-material module PDFs (rag_docs/knowledge/modules/*.pdf) as section 'knowledge'.

ONLY `modules/` is read. The other PDFs in rag_docs/knowledge/ (forms, cheat sheets, diagnosis flowchart,
hormone-therapy tables, symptom table) are deliberately NOT ingested: forms and prescribing/diagnosis material
must never reach retrieval. The symptom table lives in rag_docs/symptom_map.md instead.

Page-aware: text is split into lines/paragraphs tagged with their page, packed into ~400-token chunks
with ~12% overlap. Each chunk keeps doc name + page range in `metadata` so the report can cite it.
The PDFs are gitignored course material (German). Usage: python -m app.rag.ingest_pdf
"""
import re
from pathlib import Path

import pypdf
import tiktoken

from app.rag.clients import embed, supabase_client

PDF_DIR = Path(__file__).resolve().parent.parent.parent / "rag_docs" / "knowledge" / "modules"
CHUNK_TOKENS, OVERLAP_TOKENS, MIN_TOKENS = 400, 50, 60
ENC = tiktoken.get_encoding("cl100k_base")
NOISE = re.compile(r"(©.*MenoCert.*|Nur für registrierte.*|^\s*\d{1,3}\s*$|^\s*MODUL\s*\d\s*$)", re.I)


CITATION = re.compile(r"\(\d{4}\)|doi|https?://|et al\.|\bVol\b|\d+\(\d+\)", re.I)


def is_bibliography(text: str) -> bool:
    """Reference lists are useless as advice and pollute retrieval: drop chunks dense with citation markers."""
    return len(CITATION.findall(text)) >= 4


def doc_name(path: Path) -> str:
    """'3-SLK Modul 3 - Endokrinologie und Wechseljahre SKRIPT-offen' -> 'Modul 3 - Endokrinologie und Wechseljahre'."""
    n = re.sub(r"\s*SKRIPT.*$", "", path.stem)
    return re.sub(r"^\d-", "", n).replace("SLK ", "").replace("Einfu hrung", "Einführung").replace("Einfuhrung", "Einführung").replace("Horxmone", "Hormone")


def page_units(path: Path) -> list[tuple[int, str]]:
    """(page_number, text unit) pairs. A unit is one cleaned line; bullets stay attached to their line."""
    units = []
    reader = pypdf.PdfReader(str(path))
    for i, page in enumerate(reader.pages, start=1):
        for line in (page.extract_text() or "").splitlines():
            line = re.sub(r"\s+", " ", line.replace("●", "-")).strip()
            if line and not NOISE.fullmatch(line) and not NOISE.search(line):
                units.append((i, line))
    return units


def chunk(units: list[tuple[int, str]]) -> list[dict]:
    chunks, cur, n = [], [], 0
    def flush():
        text = "\n".join(t for _, t in cur)
        if len(ENC.encode(text)) >= MIN_TOKENS:
            chunks.append({"text": text, "page": cur[0][0], "page_end": cur[-1][0]})
    for u in units:
        t = len(ENC.encode(u[1])) + 1
        if n + t > CHUNK_TOKENS and cur:
            flush()
            keep, k = [], 0   # overlap: carry the last ~OVERLAP_TOKENS tokens into the next chunk
            for x in reversed(cur):
                k += len(ENC.encode(x[1])) + 1
                if k > OVERLAP_TOKENS:
                    break
                keep.insert(0, x)
            cur, n = keep, sum(len(ENC.encode(x[1])) + 1 for x in keep)
        cur.append(u)
        n += t
    if cur:
        flush()
    return chunks


def main() -> int:
    rows = []
    for pdf in sorted(PDF_DIR.glob("*.pdf")):
        name = doc_name(pdf)
        all_cs = chunk(page_units(pdf))
        cs = [c for c in all_cs if not is_bibliography(c["text"])]
        print(f"  dropped {len(all_cs) - len(cs)} bibliography chunks")
        for i, c in enumerate(cs, start=1):
            pages = f"S. {c['page']}" if c["page"] == c["page_end"] else f"S. {c['page']}-{c['page_end']}"
            rows.append({"section": "knowledge", "title": f"{name}, {pages} (#{i})",
                         "content": c["text"], "source": f"{name} (MenoCert coaching material)",
                         "metadata": {"doc": name, "page": c["page"], "page_end": c["page_end"], "lang": "de"}})
        print(f"{name}: {len(cs)} chunks")
    db = supabase_client()
    db.table("documents").delete().eq("section", "knowledge").execute()  # re-ingest cleanly
    for i in range(0, len(rows), 64):
        batch = rows[i:i + 64]
        vecs = embed([r["content"] for r in batch])
        db.table("documents").insert([{**r, "embedding": v} for r, v in zip(batch, vecs)]).execute()
    print(f"ingested {len(rows)} knowledge chunks")
    return len(rows)


if __name__ == "__main__":
    main()
