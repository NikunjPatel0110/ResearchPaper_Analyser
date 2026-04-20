"""
search_service.py
─────────────────
External paper search : OpenAlex (free, no key) → arXiv fallback (free, no key)
FAISS index management : full-document similarity + chunk-level plagiarism search.

Index layout
------------
Every entry in the FAISS index has a corresponding entry in `_meta` (a Python list
persisted to FAISS_META_PATH as JSON).

  Full-doc entry  →  _meta[row] = "<paper_id_string>"
  Chunk entry     →  _meta[row] = { "paper_id": "...", "chunk_text": "...", "chunk_position": N }

This single shared index lets us run both similarity search and plagiarism chunk
search without maintaining two separate FAISS files.
"""

import os
import json
import numpy as np
import requests
from backend.config import Config

# ── Shared embedding model ────────────────────────────────────────────────────
# Delegates to nlp_service so only ONE SentenceTransformer instance ever exists.
# Loading two copies can OOM or cause an OpenMP segfault on Windows.
def get_embedding_model():
    from backend.services.nlp_service import _st
    return _st()


# ── FAISS index (lazy-loaded, module-level singletons) ───────────────────────
_index = None
_meta  = None   # list – one entry per FAISS row


def _load_index():
    """Load (or create) the FAISS index and its metadata list."""
    global _index, _meta
    if _index is not None:
        return _index, _meta

    import faiss

    if (
        os.path.exists(Config.FAISS_INDEX_PATH)
        and os.path.exists(Config.FAISS_META_PATH)
    ):
        _index = faiss.read_index(Config.FAISS_INDEX_PATH)
        with open(Config.FAISS_META_PATH) as f:
            _meta = json.load(f)
    else:
        # IndexFlatIP on L2-normalised vectors == cosine similarity
        _index = faiss.IndexFlatIP(384)
        _meta  = []

    return _index, _meta


def warmup_faiss():
    """Pre-load FAISS in the main thread to avoid background-thread segfaults."""
    _load_index()


def _save_index():
    """Persist the FAISS index and metadata to disk."""
    import faiss

    idx, meta = _load_index()

    dir_path = os.path.dirname(Config.FAISS_INDEX_PATH)
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)
    faiss.write_index(idx, Config.FAISS_INDEX_PATH)
    with open(Config.FAISS_META_PATH, "w") as f:
        json.dump(meta, f)


# ── Write helpers ─────────────────────────────────────────────────────────────

def add_to_faiss(paper_id: str, embedding: list) -> int:
    """
    Add a single full-document embedding to FAISS.
    Meta entry is a plain string (paper_id).
    Returns the FAISS row number.
    """
    idx, meta = _load_index()
    vec = np.array([embedding], dtype="float32")
    idx.add(vec)
    meta.append(str(paper_id))
    _save_index()
    return idx.ntotal - 1


def add_chunks_to_faiss(
    chunk_embeddings: list,
    chunk_meta: list[dict],
) -> list[int]:
    """
    Add a batch of chunk embeddings to FAISS.
    Meta entries are dicts: { paper_id, chunk_text, chunk_position }.
    Returns a list of FAISS row numbers (one per chunk).
    """
    if not chunk_embeddings:
        return []

    import faiss   # noqa: F401 – ensure faiss is available

    idx, meta = _load_index()

    arr       = np.array(chunk_embeddings, dtype="float32")
    start_row = idx.ntotal
    idx.add(arr)

    rows = []
    for i, cm in enumerate(chunk_meta):
        row = start_row + i
        meta.append({
            "paper_id":       cm["paper_id"],
            "chunk_text":     cm["chunk_text"],
            "chunk_position": cm.get("chunk_position", i),
        })
        rows.append(row)

    _save_index()
    return rows


def remove_paper_vectors(paper_id: str) -> int:
    """
    Physically remove all embeddings (full-doc and chunks) belonging to a paper.
    This reconstructs the index from the remaining metadata rows.
    Returns the number of rows removed.
    """
    import faiss
    idx, meta = _load_index()
    if idx.ntotal == 0:
        return 0

    pid_str = str(paper_id)
    keep_indices = []
    remove_count = 0

    for i, entry in enumerate(meta):
        entry_pid = entry if isinstance(entry, str) else entry.get("paper_id")
        if entry_pid == pid_str:
            remove_count += 1
        else:
            keep_indices.append(i)

    if remove_count == 0:
        return 0

    # Rebuild index from 'keep' vectors
    new_meta = [meta[i] for i in keep_indices]
    
    if keep_indices:
        # Reconstruct vectors for rows we want to keep
        # IndexFlatIP supports reconstruction
        keep_vecs = np.array([idx.reconstruct(i) for i in keep_indices], dtype="float32")
        new_index = faiss.IndexFlatIP(idx.d)
        new_index.add(keep_vecs)
    else:
        new_index = faiss.IndexFlatIP(idx.d)

    global _index, _meta
    _index = new_index
    _meta  = new_meta
    _save_index()
    
    print(f"[remove_paper_vectors] Physically removed {remove_count} rows for paper: {pid_str}")
    return remove_count


def sync_index_with_db() -> dict:
    """
    Cross-reference FAISS metadata with MongoDB and remove any orphaned vectors.
    Useful for cleaning up after manual DB deletions.
    """
    from backend.models.db import papers
    from bson import ObjectId

    idx, meta = _load_index()
    if not meta:
        return {"total_before": 0, "removed": 0, "total_after": 0}

    total_before = len(meta)
    
    # Get all unique paper IDs in the index
    indexed_pids = set()
    for entry in meta:
        indexed_pids.add(entry if isinstance(entry, str) else entry.get("paper_id"))

    # Check which ones still exist in MongoDB
    # Convert to valid ObjectIds only
    valid_oids = []
    for pid in indexed_pids:
        try:
            valid_oids.append(ObjectId(pid))
        except:
            pass
            
    existing_docs = papers().find({"_id": {"$in": valid_oids}}, {"_id": 1})
    existing_pids = {str(d["_id"]) for d in existing_docs}

    # Find orphans
    orphans = indexed_pids - existing_pids
    
    removed_total = 0
    if orphans:
        for pid in orphans:
            removed_total += remove_paper_vectors(pid)

    return {
        "total_before": total_before,
        "removed":      removed_total,
        "total_after":  len(_meta) if _meta is not None else 0
    }


# ── Read helpers ──────────────────────────────────────────────────────────────

def search_similar_docs(
    embedding: list,
    k: int = 6,
    exclude_paper_id: str = None,
) -> list[dict]:
    """
    Search FAISS for similar full-document embeddings.
    Only returns entries where meta is a plain string (= full-doc entries).
    """
    idx, meta = _load_index()
    if idx.ntotal == 0:
        return []

    vec = np.array([embedding], dtype="float32")
    scores, rows = idx.search(vec, min(k + 5, idx.ntotal))

    results = []
    for score, row in zip(scores[0], rows[0]):
        if row < 0:
            continue
        entry = meta[row]
        # Full-doc entries are plain strings
        if not isinstance(entry, str):
            continue
        if exclude_paper_id and entry == str(exclude_paper_id):
            continue
        results.append({"paper_id": entry, "score": float(score)})
        if len(results) >= k:
            break

    return results


def search_chunk_index(
    embedding,
    k: int = 5,
    exclude_paper_id: str = None,
) -> list[dict]:
    """
    Search FAISS for chunk-level matches (used by plagiarism_service).
    Only returns entries where meta is a dict (= chunk entries).

    Parameters
    ----------
    embedding : 1-D array-like of shape (384,)
    k         : number of results to return
    exclude_paper_id : skip chunks belonging to this paper

    Returns
    -------
    list of { paper_id, chunk_text, score }
    """
    idx, meta = _load_index()
    if idx.ntotal == 0:
        return []

    vec = np.array([embedding], dtype="float32").reshape(1, -1)
    # Fetch more than k so we still have k after filtering
    scores, rows = idx.search(vec, min(k + 10, idx.ntotal))

    results     = []
    seen_papers = set()

    for score, row in zip(scores[0], rows[0]):
        if row < 0:
            continue
        entry = meta[row]
        # Chunk entries are dicts
        if not isinstance(entry, dict):
            continue
        pid = entry.get("paper_id", "")
        if exclude_paper_id and pid == str(exclude_paper_id):
            continue
        # Return at most one result per source paper to avoid flooding
        if pid in seen_papers:
            continue
        seen_papers.add(pid)

        results.append({
            "paper_id":   pid,
            "chunk_text": entry.get("chunk_text", ""),
            "score":      float(score),
        })

        if len(results) >= k:
            break

    return results


# ── OpenAlex (free, no API key needed) ───────────────────────────────────────
OPENALEX_URL = "https://api.openalex.org/works"


def search_openalex(keywords: list, limit: int = 5) -> list[dict]:
    """
    Search OpenAlex — completely free, no API key required.
    Passing a mailto address enters the 'polite pool' (higher rate limits).
    """
    if not keywords:
        return []

    # keywords may be list[str] or list[dict] with a "word" key
    kw_words = [
        kw["word"] if isinstance(kw, dict) else kw
        for kw in keywords[:6]
    ]
    query  = " ".join(kw_words)
    params = {
        "search":   query,
        "per-page": limit,
        "select":   (
            "id,title,abstract_inverted_index,doi,"
            "publication_year,authorships,cited_by_count,primary_location"
        ),
        "mailto":   "paperiq@demo.com",
        "filter":   "type:article",
    }

    try:
        r = requests.get(OPENALEX_URL, params=params, timeout=10)
        r.raise_for_status()
        works   = r.json().get("results", [])
        results = []

        for w in works:
            title = w.get("title") or ""
            if not title:
                continue
            abstract = _decode_abstract(w.get("abstract_inverted_index"))
            authors  = [
                (a.get("author") or {}).get("display_name", "")
                for a in (w.get("authorships") or [])[:3]
                if (a.get("author") or {}).get("display_name")
            ]
            doi = w.get("doi") or ""
            loc = w.get("primary_location") or {}
            url = (
                doi if doi.startswith("http") else
                f"https://doi.org/{doi}" if doi else
                loc.get("landing_page_url") or w.get("id", "")
            )
            results.append({
                "title":            title,
                "abstract":         abstract[:300] if abstract else "",
                "url":              url,
                "year":             str(w.get("publication_year", "")),
                "authors":          authors,
                "citations":        w.get("cited_by_count", 0),
                "source":           "external",
                "similarity_score": 0.0,
            })

        return results

    except Exception as e:
        print(f"[OpenAlex] Error: {e}")
        return []


def _decode_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract string from OpenAlex inverted-index format."""
    if not inverted_index:
        return ""
    try:
        positions = {}
        for word, pos_list in inverted_index.items():
            for pos in pos_list:
                positions[pos] = word
        return " ".join(positions[i] for i in sorted(positions))
    except Exception:
        return ""


# ── arXiv (free fallback, no key) ────────────────────────────────────────────

def search_arxiv(keywords: list, max_results: int = 5) -> list[dict]:
    """arXiv Atom API — always free, no key needed."""
    import xml.etree.ElementTree as ET

    if not keywords:
        return []

    kw_words = [
        kw["word"] if isinstance(kw, dict) else kw
        for kw in keywords[:3]
    ]
    query  = " ".join(kw_words)
    params = {
        "search_query": f"all:{query}",
        "max_results":  max_results,
        "sortBy":       "relevance",
    }

    try:
        r    = requests.get("http://export.arxiv.org/api/query", params=params, timeout=10)
        root = ET.fromstring(r.text)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}

        results = []
        for entry in root.findall("atom:entry", ns):
            title_el   = entry.find("atom:title",   ns)
            link_el    = entry.find("atom:id",      ns)
            summary_el = entry.find("atom:summary", ns)
            authors_el = entry.findall("atom:author/atom:name", ns)

            if title_el is None:
                continue

            results.append({
                "title":            title_el.text.strip().replace("\n", " "),
                "abstract":         (summary_el.text or "").strip()[:300],
                "url":              (link_el.text or "").strip(),
                "authors":          [a.text for a in authors_el[:3]],
                "year":             "",
                "source":           "external",
                "similarity_score": 0.0,
            })

        return results

    except Exception as e:
        print(f"[arXiv] Error: {e}")
        return []


def search_external_papers(keywords: list, limit: int = 5, target_embedding: list = None) -> list[dict]:
    """Primary external search — OpenAlex first, arXiv as fallback."""
    results = search_openalex(keywords, limit=limit)
    if not results:
        results = search_arxiv(keywords, max_results=limit)

    if results and target_embedding:
        try:
            from backend.services.nlp_service import embed_chunks, cosine_similarity
            # Using abstracts for embedding comparison; fall back to title if abstract is missing
            texts = [
                (r.get("abstract") or "")[:500] if r.get("abstract") else r.get("title", "")
                for r in results
            ]
            res_embeddings = embed_chunks(texts)
            
            for i, emb in enumerate(res_embeddings):
                score = cosine_similarity(target_embedding, emb)
                results[i]["score"] = round(score, 4)
            
            # Re-sort by actual semantic similarity
            results.sort(key=lambda x: x["score"], reverse=True)
        except Exception as e:
            print(f"[search_external_papers] Similarity calculation failed: {e}")

    return results