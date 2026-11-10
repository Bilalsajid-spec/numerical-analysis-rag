# Purpose: build the local index and retrieve relevant source passages.
# Work: combine persistent Chroma vector retrieval with BM25-style keyword ranking.

import hashlib
import json
import math
import re
import uuid
from collections import Counter
from functools import lru_cache

from .config import CHROMA_DIR, DATA_DIR, INDEX_MANIFEST, NOTES_DIR, MIN_SIMILARITY
from .embeddings import encode, embedding_fingerprint
from .library import list_documents

STOP_WORDS = set("a an the is are was were be of to in on for from and or with what which how why explain tell me about please compare between method methods use using hai kya kia ka ki ke ko aur mujhe batao samjhao frac left right boxed mathrm text quad qquad".split())


def words(text):
    return [word for word in re.findall(r"[a-z0-9]+", text.lower()) if word not in STOP_WORDS]


def pdf_fingerprint():
    digest = hashlib.sha256()
    for path in sorted(NOTES_DIR.glob("*.pdf")):
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def db_client():
    import chromadb
    from chromadb.config import Settings
    return chromadb.PersistentClient(path=str(CHROMA_DIR), settings=Settings(anonymized_telemetry=False))


def load_manifest():
    if not INDEX_MANIFEST.exists():
        raise FileNotFoundError("Search index missing. Run python ingest.py first.")
    manifest = json.loads(INDEX_MANIFEST.read_text(encoding="utf-8"))
    if "pages_file" not in manifest:
        raise ValueError("Index format changed. Run python ingest.py to rebuild.")
    if manifest["pdf_fingerprint"] != pdf_fingerprint():
        raise ValueError("PDFs changed. Rebuild with python ingest.py.")
    if manifest["embedding_fingerprint"] != embedding_fingerprint():
        raise ValueError("Embedding model changed. Rebuild with python ingest.py.")
    return manifest


def save_index(chunks, page_count, signature, pages=None):
    if not chunks:
        raise ValueError("No usable chunks to index.")
    name = f"nm_{uuid.uuid4().hex}"
    client = db_client()
    collection = client.create_collection(name, embedding_function=None, metadata={"hnsw:space": "cosine"})
    try:
        for start in range(0, len(chunks), 32):
            batch = chunks[start:start + 32]
            # Store complete text and report oversized math units whose embeddings may truncate.
            vectors = encode([f"{c['title']}\n{c['text']}" for c in batch])
            collection.add(ids=[c["id"] for c in batch], documents=[c["text"] for c in batch],
                           embeddings=vectors, metadatas=[{k: c[k] for k in ("source", "page", "part", "title", "review_required", "oversize_atomic")} for c in batch])
            print(f"Indexed {min(start+32, len(chunks))}/{len(chunks)} chunks", flush=True)
        records_path = DATA_DIR / "indexes" / f"{name}.json"
        records_path.parent.mkdir(parents=True, exist_ok=True)
        records_path.write_text(json.dumps(chunks, ensure_ascii=False), encoding="utf-8")
        # Locate pages using chunks and provide their complete parent text to the answer model.
        pages_path = records_path.with_name(f"{name}_pages.json")
        pages_path.write_text(json.dumps(pages or [], ensure_ascii=False), encoding="utf-8")
        manifest = {"collection": name, "chunks_file": str(records_path.relative_to(DATA_DIR)),
                    "pages_file": str(pages_path.relative_to(DATA_DIR)),
                    "chunk_count": len(chunks), "page_count": page_count,
                    "pdf_count": len({c['source'] for c in chunks}),
                    "pdf_fingerprint": pdf_fingerprint(), "embedding_fingerprint": embedding_fingerprint(),
                    "build_signature": signature, "oversize_atomic_chunks": sum(c["oversize_atomic"] for c in chunks)}
        temporary = INDEX_MANIFEST.with_suffix(".tmp")
        temporary.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        temporary.replace(INDEX_MANIFEST)
        return manifest
    except Exception:
        # Remove only the failed new collection and preserve the previous successful index.
        client.delete_collection(name)
        raise


@lru_cache(maxsize=2)
def _lexical_index(filename):
    chunks = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
    frequencies = [Counter(words(c["title"] + " " + c["text"])) for c in chunks]
    document_frequency = Counter(word for counts in frequencies for word in counts)
    lengths = [sum(counts.values()) for counts in frequencies]
    return chunks, frequencies, document_frequency, lengths, sum(lengths) / max(1, len(lengths))


@lru_cache(maxsize=2)
def _parent_pages(filename):
    records = json.loads((DATA_DIR / filename).read_text(encoding="utf-8"))
    return {(page["source"], page["page"]): page for page in records}


def retrieve(question, top_k=4, week=None):
    if not question.strip():
        raise ValueError("Question cannot be empty.")
    if not 1 <= top_k <= 10:
        raise ValueError("top-k must be between 1 and 10")
    if week is not None and week < 1:
        raise ValueError("week must be a positive number")
    manifest = load_manifest()
    chunks, frequencies, df, lengths, average = _lexical_index(manifest["chunks_file"])
    # Discover matching week sources from current filenames without a fixed upper limit.
    sources = {doc["source"] for doc in list_documents() if doc["week"] == week} if week else None
    if week is not None and not sources:
        raise ValueError(f"No PDF found for week {week}. Use All notes or add Week_{week}_Numerical_Analysis.pdf and run python ingest.py.")
    eligible = [i for i, chunk in enumerate(chunks) if sources is None or chunk["source"] in sources]
    if not eligible:
        raise ValueError("No indexed passages found for this selection. Run python ingest.py.")
    collection = db_client().get_collection(manifest["collection"], embedding_function=None)
    options = {"where": {"source": {"$in": sorted(sources)}}} if sources else {}
    result = collection.query(query_embeddings=encode([question]), n_results=min(40, len(eligible)),
                              include=["documents", "metadatas", "distances"], **options)
    semantic_ids = result["ids"][0]
    similarities = {key: 1-float(distance) for key, distance in zip(semantic_ids, result["distances"][0])}
    query_words = set(words(question))
    lexical = {}
    for i in eligible:
        score = 0.0
        for word in query_words:
            frequency = frequencies[i].get(word, 0)
            idf = math.log(1 + (len(chunks)-df[word]+0.5)/(df[word]+0.5))
            score += idf * frequency * 2.5 / (frequency + 1.5 * (0.25 + 0.75 * lengths[i] / max(average, 1)))
        if score:
            lexical[chunks[i]["id"]] = score
    lexical_ids = sorted(lexical, key=lexical.get, reverse=True)[:40]
    fused = {}
    for ranking, weight in [(semantic_ids, 1.0), (lexical_ids, 0.8)]:
        for rank, identity in enumerate(ranking, 1):
            fused[identity] = fused.get(identity, 0) + weight / (60 + rank)
    by_id = {c["id"]: c for c in chunks}
    parents = _parent_pages(manifest["pages_file"])
    for identity in fused:
        chunk = by_id[identity]
        page = parents.get((chunk["source"], chunk["page"]), chunk)
        headings = re.findall(r"^#+\s+(.+)$", page["text"], re.M)
        # Prefer main numbered sections over passing mentions of another method.
        primary = [heading for heading in headings if re.match(r"^\d+\s", heading)]
        if not primary and headings:
            primary = headings[:1]
        matches = query_words.intersection(words(" ".join(primary)))
        fused[identity] += 0.01 * sum(math.log(1 + (len(chunks)-df[word]+0.5)/(df[word]+0.5)) for word in matches)
    selected, seen = [], set()
    for identity in sorted(fused, key=fused.get, reverse=True):
        chunk = by_id[identity]
        # Deduplicate overlapping passages from the same PDF page.
        key = (chunk["source"], chunk["page"])
        if key in seen:
            continue
        parent = parents.get(key)
        selected.append(dict(chunk, matched_text=chunk["text"], text=parent["text"] if parent else chunk["text"],
                             similarity=similarities.get(identity, 0.0), lexical_score=lexical.get(identity, 0.0)))
        seen.add(key)
        if len(selected) == top_k:
            break
    strongest = max(similarities.values(), default=0)
    # Reject insufficiently supported questions before requesting language model generation.
    supported = bool(query_words and strongest >= MIN_SIMILARITY and lexical_ids)
    return {"hits": selected, "supported": supported, "best_similarity": strongest}
