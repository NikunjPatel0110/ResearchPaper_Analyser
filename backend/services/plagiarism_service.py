# from datetime import datetime
# from bson import ObjectId
# from backend.models.db import papers, plag_reports
# from backend.services.nlp_service import chunk_text, embed_chunks, embed_text
# from backend.services.search_service import search_chunk_index
# from backend.config import Config


# def _ok(data): return {"success": True, "data": data, "error": None}
# def _err(msg): return {"success": False, "data": None, "error": msg}


# def check_plagiarism(paper_id, threshold=None):
#     threshold = threshold or Config.SIMILARITY_THRESHOLD

#     paper = papers().find_one({"_id": ObjectId(paper_id)})
#     if not paper:
#         return _err("Paper not found"), 404
#     if paper.get("status") != "ready":
#         return _err("Paper is not yet processed"), 400

#     text   = paper.get("raw_text", "")
#     chunks = chunk_text(text, window_words=200, step_words=150)

#     if not chunks:
#         return _err("Paper text too short for plagiarism check"), 400

#     chunk_texts = [c["text"] for c in chunks]
#     try:
#         chunk_embeddings = embed_chunks(chunk_texts)
#     except Exception as e:
#         return _err(f"Embedding failed: {str(e)}"), 500

#     matches      = []
#     flagged      = 0
#     seen_sources = set()

#     for chunk, emb in zip(chunks, chunk_embeddings):
#         similar = search_chunk_index(emb, k=3, exclude_paper_id=paper_id)
#         for s in similar:
#             if s["score"] >= threshold:
#                 src_paper = papers().find_one(
#                     {"_id": ObjectId(s["paper_id"])},
#                     {"title": 1}
#                 ) if s["paper_id"] else None

#                 if src_paper and src_paper.get("title") == paper.get("title"):
#                     continue

#                 match_entry = {
#                     "chunk_text":          chunk["text"][:300],
#                     "word_offset":         chunk["word_offset"],
#                     "matched_paper_id":    s["paper_id"],
#                     "matched_paper_title": src_paper["title"] if src_paper else "Unknown",
#                     "similarity":          round(s["score"], 4)
#                 }
#                 matches.append(match_entry)
#                 flagged += 1
#                 break   # one match per chunk

#     total = len(chunks)
#     overall = round(flagged / total, 4) if total else 0.0
#     detected = overall > Config.PLAGIARISM_OVERALL_THRESHOLD

#     report = {
#         "paper_id":           ObjectId(paper_id),
#         "overall_similarity": overall,
#         "plagiarism_detected":detected,
#         "matches":            matches,
#         "total_chunks":       total,
#         "flagged_chunks":     flagged,
#         "threshold_used":     threshold,
#         "created_at":         datetime.utcnow()
#     }
#     res = plag_reports().insert_one(report)

#     return _ok({
#         "report_id":           str(res.inserted_id),
#         "paper_id":            paper_id,
#         "paper_title":         paper["title"],
#         "overall_similarity":  overall,
#         "plagiarism_detected": detected,
#         "flagged_chunks":      flagged,
#         "total_chunks":        total,
#         "matches":             matches,
#         "threshold_used":      threshold
#     }), 200


# def index_paper_chunks(paper_id, text):
#     """Index all chunks of a paper into FAISS chunk index."""
#     from backend.services.search_service import add_chunks_to_faiss
#     chunks = chunk_text(text, window_words=200, step_words=150)
#     if not chunks:
#         return 0
#     chunk_texts = [c["text"] for c in chunks]
#     embeddings  = embed_chunks(chunk_texts)
#     meta = [{
#         "paper_id":   str(paper_id),
#         "chunk_text": c["text"][:200],
#         "word_offset":c["word_offset"]
#     } for c in chunks]
#     add_chunks_to_faiss(embeddings, meta)
#     return len(chunks)

"""
plagiarism_service.py
─────────────────────
Two-layer plagiarism detection:
  Layer 1 — n-gram fingerprint hashing (exact / near-exact)
  Layer 2 — semantic chunk embedding via FAISS (paraphrase detection)

Public API
----------
  index_paper_chunks(paper_id, text)     ← called at upload time
  check_plagiarism(paper_id, threshold)  ← called by the route
  ensure_indexes()                       ← called once at app startup
"""

import re
import hashlib
import numpy as np
from bson import ObjectId

from backend.models.db import get_db, papers

# Re-use the already-initialised model and FAISS index from search_service.
# Never create a second SentenceTransformer instance — it's expensive.
from backend.services.search_service import (
    search_chunk_index,
    add_chunks_to_faiss,
    get_embedding_model
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _sliding_window_chunks(text: str, size: int = 150, stride: int = 75) -> list[str]:
    """Split text into overlapping word-window chunks."""
    words  = text.split()
    chunks = []
    for i in range(0, max(1, len(words) - size + 1), stride):
        chunk = " ".join(words[i : i + size])
        if len(chunk.split()) >= 30:   # discard tiny trailing fragments
            chunks.append(chunk)
    return chunks


def _ngram_hashes(text: str, n: int = 5) -> list[str]:
    """Return MD5 hashes of every word n-gram in text."""
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    words   = cleaned.split()
    ngrams  = [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
    return [hashlib.md5(ng.encode()).hexdigest() for ng in ngrams]


def _deduplicate_chunks(flagged: list[dict]) -> list[dict]:
    """Remove duplicate flagged chunks (same leading 60 chars)."""
    seen, result = set(), []
    for c in flagged:
        key = c["chunk_text"][:60]
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result


# ── Index at upload time ──────────────────────────────────────────────────────

def index_paper_chunks(paper_id: str, text: str) -> None:
    """
    Index all chunks of a paper for plagiarism detection.
    Called lazily on first plagiarism check (NOT at upload time).
    Safe to call multiple times — skips if already indexed.
    Stores:
      • n-gram hashes  →  MongoDB  `fingerprints` collection
      • chunk vectors  →  FAISS index  +  MongoDB `chunk_index` collection
    """
    db = get_db()

    # Skip if already indexed
    if db.chunk_index.find_one({"paper_id": paper_id}):
        return

    chunks = _sliding_window_chunks(text)
    if not chunks:
        return

    # ── 1. Fingerprint hashes → MongoDB (bulk insert) ─────────────────────
    hash_docs = []
    for chunk in chunks:
        for h in _ngram_hashes(chunk, n=5):
            hash_docs.append({
                "hash":       h,
                "paper_id":   paper_id,
                "chunk_text": chunk,
            })
    if hash_docs:
        try:
            db.fingerprints.insert_many(hash_docs, ordered=False)
        except Exception:
            pass   # ignore duplicate-key errors on re-index

    # ── 2. Chunk embeddings → FAISS + chunk_index collection (bulk) ───────
    vecs = get_embedding_model().encode(chunks, normalize_embeddings=True, batch_size=32)

    chunk_meta = [
        {
            "paper_id":       paper_id,
            "chunk_text":     chunk,
            "chunk_position": i,
        }
        for i, chunk in enumerate(chunks)
    ]

    faiss_ids = add_chunks_to_faiss(
        chunk_embeddings=list(vecs),
        chunk_meta=chunk_meta,
    )

    # Bulk insert into MongoDB (one round-trip instead of N)
    if faiss_ids:
        db.chunk_index.insert_many([
            {
                "faiss_id":       faiss_id,
                "paper_id":       meta["paper_id"],
                "chunk_text":     meta["chunk_text"],
                "chunk_position": meta["chunk_position"],
            }
            for faiss_id, meta in zip(faiss_ids, chunk_meta)
        ])


# ── Check plagiarism ──────────────────────────────────────────────────────────

def check_plagiarism(paper_id: str, threshold: float = None) -> tuple[dict, int]:
    """
    Run the two-layer plagiarism check on a paper.

    Returns
    -------
    (response_dict, http_status_code)

    response_dict follows the app envelope:
      { "success": bool, "data": { overall_score, flagged_chunks }, "error": str|None }
    """
    semantic_threshold = float(threshold) if threshold is not None else 0.85

    db    = get_db()
    paper = papers().find_one({"_id": ObjectId(paper_id)})
    if not paper:
        return {"success": False, "data": None, "error": "Paper not found"}, 404

    raw_text = paper.get("raw_text", "")
    if not raw_text:
        return {"success": False, "data": None, "error": "Paper has no text content"}, 400

    # Lazily build chunk index on first plagiarism check for this paper
    index_paper_chunks(paper_id, raw_text)

    chunks  = _sliding_window_chunks(raw_text)
    flagged = []

    for chunk in chunks:

        # ── Layer 1 : exact / near-exact fingerprint ──────────────────────
        from collections import Counter
        hashes  = _ngram_hashes(chunk, n=5)
        total_hashes = len(hashes)
        
        matches = list(db.fingerprints.find({
            "hash":     {"$in": hashes},
            "paper_id": {"$ne": str(paper_id)},
        }))

        counts = Counter(m["paper_id"] for m in matches)
        seen_in_layer1 = set()
        
        for src_pid, count in counts.items():
            if total_hashes > 0 and (count / total_hashes) < 0.15:
                continue

            seen_in_layer1.add(src_pid)

            src = papers().find_one({"_id": ObjectId(src_pid)}, {"title": 1})
            if src:
                # Exclude if it has the same title (case-insensitive) to skip duplicates/clones
                if src.get("title", "").lower().strip() == paper.get("title", "").lower().strip():
                    continue
            else:
                continue

            flagged.append({
                "chunk_text": chunk,
                "matched_paper_title": src["title"] if src else "Unknown paper",
                "similarity": 1.0,
                "method": "exact",
            })

        # ── Layer 2 : semantic / paraphrase match ─────────────────────────
        # search_chunk_index already filters out full-doc entries (dicts only)
        vec = get_embedding_model().encode([chunk], normalize_embeddings=True)
        sem_matches  = search_chunk_index(
            embedding=vec[0],
            k=5,
            exclude_paper_id=paper_id,
        )

        for match in sem_matches:
            if match["score"] < semantic_threshold:
                continue
            # Avoid double-flagging a source already caught by fingerprinting
            if match["paper_id"] in seen_in_layer1:
                continue

            src = papers().find_one({"_id": ObjectId(match["paper_id"])}, {"title": 1})
            if src:
                if src.get("title", "").lower().strip() == paper.get("title", "").lower().strip():
                    continue
            else:
                continue

            flagged.append({
                "chunk_text": chunk,
                "matched_paper_title": src["title"] if src else "Unknown paper",
                "similarity": round(match["score"], 3),
                "method": "semantic",
            })

    # ── Combine, deduplicate, compute overall score ───────────────────────
    flagged       = _deduplicate_chunks(flagged)
    flagged       = sorted(flagged, key=lambda x: -x["similarity"])

    total_words   = len(raw_text.split())
    flagged_words = sum(len(c["chunk_text"].split()) for c in flagged)
    overall_score = round(min(flagged_words / total_words, 1.0), 3) if total_words else 0.0

    return {
        "success": True,
        "data": {
            "paper_id":      paper_id,
            "overall_similarity": overall_score,
            "matches": flagged,
            "total_chunks":  len(chunks),
            "flagged_count": len(flagged),
        },
        "error": None,
    }, 200


def delete_paper_data(paper_id: str) -> None:
    """
    Remove all associated fingerprints, chunks, and reports for a given paper.
    Ensures no 'ghost data' is left in the system after deletion.
    """
    db = get_db()
    pid_str = str(paper_id)
    
    # 1. Remove fingerprints
    db.fingerprints.delete_many({"paper_id": pid_str})
    
    # 2. Remove from chunk index
    db.chunk_index.delete_many({"paper_id": pid_str})
    
    # 3. Remove analysis reports
    db.plag_reports.delete_many({"paper_id": ObjectId(paper_id)})
    db.ai_reports.delete_many({"paper_id": ObjectId(paper_id)})
    db.comparisons.delete_many({
        "$or": [
            {"paper_id_1": ObjectId(paper_id)},
            {"paper_id_2": ObjectId(paper_id)},
            {"paper_id_a": ObjectId(paper_id)},  # handle both naming conventions
            {"paper_id_b": ObjectId(paper_id)}
        ]
    })
    
    # 4. Remove from physical FAISS index (Scrub vectors)
    from backend.services import search_service
    search_service.remove_paper_vectors(paper_id)
    
    print(f"[delete_paper_data] Scrubbed all data for paper: {pid_str}")


# ── One-time index setup ──────────────────────────────────────────────────────

def ensure_indexes() -> None:
    """
    Create MongoDB indexes for the fingerprints and chunk_index collections.
    Safe to call multiple times — MongoDB ignores already-existing indexes.
    Call this once from create_app() inside app.py.
    """
    db = get_db()
    db.fingerprints.create_index("hash")
    db.fingerprints.create_index("paper_id")
    db.chunk_index.create_index("faiss_id")
    db.chunk_index.create_index("paper_id")