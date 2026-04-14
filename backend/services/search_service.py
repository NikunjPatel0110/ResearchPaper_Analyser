"""
search_service.py
External paper search: OpenAlex (free, no key) → arXiv fallback (free, no key)
FAISS index management for internal similarity search and chunk-level plagiarism.
"""
import os
import json
import numpy as np
import requests
from bson import ObjectId

from backend.config import Config

# ── FAISS index (lazy-loaded) ────────────────────────────────────────────────
_index = None
_meta  = None   # list of paper_id strings, indexed by FAISS row

def _load_index():
    global _index, _meta
    if _index is not None:
        return _index, _meta
    import faiss
    if os.path.exists(Config.FAISS_INDEX_PATH) and os.path.exists(Config.FAISS_META_PATH):
        _index = faiss.read_index(Config.FAISS_INDEX_PATH)
        with open(Config.FAISS_META_PATH) as f:
            _meta = json.load(f)
    else:
        _index = faiss.IndexFlatIP(384)   # inner product on normalised vecs = cosine
        _meta  = []
    return _index, _meta


def _save_index():
    import faiss
    idx, meta = _load_index()
    faiss.write_index(idx, Config.FAISS_INDEX_PATH)
    with open(Config.FAISS_META_PATH, "w") as f:
        json.dump(meta, f)


def add_to_faiss(paper_id, embedding):
    """Add a full-document embedding to FAISS. Returns row number."""
    import faiss
    idx, meta = _load_index()
    vec = np.array([embedding], dtype="float32")
    idx.add(vec)
    meta.append(str(paper_id))
    _save_index()
    return idx.ntotal - 1


def add_chunks_to_faiss(chunk_embeddings, chunk_meta):
    """Add chunk embeddings (list of vecs). chunk_meta: list of dicts."""
    import faiss
    idx, meta = _load_index()
    rows = []
    for vec, cm in zip(chunk_embeddings, chunk_meta):
        arr = np.array([vec], dtype="float32")
        idx.add(arr)
        meta.append(cm)   # store full chunk meta dict
        rows.append(idx.ntotal - 1)
    _save_index()
    return rows


def search_similar_docs(embedding, k=6, exclude_paper_id=None):
    """Search FAISS for similar full-document embeddings."""
    idx, meta = _load_index()
    if idx.ntotal == 0:
        return []
    vec = np.array([embedding], dtype="float32")
    scores, rows = idx.search(vec, min(k + 2, idx.ntotal))
    results = []
    for score, row in zip(scores[0], rows[0]):
        if row < 0:
            continue
        entry = meta[row]
        # Full-doc entries are plain strings (paper_id)
        if not isinstance(entry, str):
            continue
        if exclude_paper_id and entry == str(exclude_paper_id):
            continue
        results.append({"paper_id": entry, "score": float(score)})
    return results[:k]


def search_chunk_index(embedding, k=3, exclude_paper_id=None):
    """Search FAISS for chunk-level matches (plagiarism)."""
    idx, meta = _load_index()
    if idx.ntotal == 0:
        return []
    vec = np.array([embedding], dtype="float32")
    scores, rows = idx.search(vec, min(k + 3, idx.ntotal))
    results = []
    seen_papers = set()
    for score, row in zip(scores[0], rows[0]):
        if row < 0:
            continue
        entry = meta[row]
        if not isinstance(entry, dict):
            continue
        pid = entry.get("paper_id", "")
        if exclude_paper_id and pid == str(exclude_paper_id):
            continue
        results.append({
            "paper_id":   pid,
            "chunk_text": entry.get("chunk_text", ""),
            "score":      float(score)
        })
    return results[:k]


# ── OpenAlex (free, no API key needed) ───────────────────────────────────────
# Docs: https://docs.openalex.org
OPENALEX_URL = "https://api.openalex.org/works"

def search_openalex(keywords, limit=5):
    """
    Search OpenAlex — completely free, no API key required.
    Adding a mailto enters the "polite pool" with higher rate limits.
    """
    if not keywords:
        return []
    query = " ".join(kw["word"] for kw in keywords[:6])
    params = {
        "search":    query,
        "per-page":  limit,
        "select":    "id,title,abstract_inverted_index,doi,publication_year,authorships,cited_by_count,primary_location",
        "mailto":    "paperiq@demo.com",
        "filter":    "type:article"
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
            authors  = []
            for a in (w.get("authorships") or [])[:3]:
                name = (a.get("author") or {}).get("display_name", "")
                if name:
                    authors.append(name)
            doi = w.get("doi") or ""
            loc = w.get("primary_location") or {}
            url = (doi if doi.startswith("http") else
                   f"https://doi.org/{doi}" if doi else
                   (loc.get("landing_page_url") or w.get("id", "")))
            results.append({
                "title":     title,
                "abstract":  abstract[:300] if abstract else "",
                "url":       url,
                "year":      w.get("publication_year"),
                "authors":   authors,
                "citations": w.get("cited_by_count", 0),
                "source":    "openalex"
            })
        return results
    except Exception as e:
        print(f"[OpenAlex] Error: {e}")
        return []


def _decode_abstract(inverted_index):
    """Reconstruct abstract string from OpenAlex inverted index format."""
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
def search_arxiv(keywords, max_results=5):
    """arXiv API — always free, no key needed."""
    import xml.etree.ElementTree as ET
    if not keywords:
        return []
    query  = " ".join(kw["word"] for kw in keywords[:3])
    params = {"search_query": f"all:{query}", "max_results": max_results, "sortBy": "relevance"}
    try:
        r    = requests.get("http://export.arxiv.org/api/query", params=params, timeout=10)
        root = ET.fromstring(r.text)
        ns   = {"atom": "http://www.w3.org/2005/Atom"}
        results = []
        for entry in root.findall("atom:entry", ns):
            title       = entry.find("atom:title", ns)
            link        = entry.find("atom:id", ns)
            summary_el  = entry.find("atom:summary", ns)
            authors_el  = entry.findall("atom:author/atom:name", ns)
            if title is not None:
                results.append({
                    "title":    title.text.strip().replace("\n", " "),
                    "abstract": (summary_el.text or "").strip()[:300],
                    "url":      (link.text or "").strip(),
                    "authors":  [a.text for a in authors_el[:3]],
                    "source":   "arxiv"
                })
        return results
    except Exception as e:
        print(f"[arXiv] Error: {e}")
        return []


def search_external_papers(keywords, limit=5):
    """Main external search — OpenAlex first, arXiv fallback."""
    results = search_openalex(keywords, limit=limit)
    if not results:
        results = search_arxiv(keywords, max_results=limit)
    return results


