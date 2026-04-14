from datetime import datetime
from bson import ObjectId
from backend.models.db import papers, plag_reports
from backend.services.nlp_service import chunk_text, embed_chunks, embed_text
from backend.services.search_service import search_chunk_index
from backend.config import Config


def _ok(data): return {"success": True, "data": data, "error": None}
def _err(msg): return {"success": False, "data": None, "error": msg}


def check_plagiarism(paper_id, threshold=None):
    threshold = threshold or Config.SIMILARITY_THRESHOLD

    paper = papers().find_one({"_id": ObjectId(paper_id)})
    if not paper:
        return _err("Paper not found"), 404
    if paper.get("status") != "ready":
        return _err("Paper is not yet processed"), 400

    text   = paper.get("raw_text", "")
    chunks = chunk_text(text, window_words=200, step_words=150)

    if not chunks:
        return _err("Paper text too short for plagiarism check"), 400

    chunk_texts = [c["text"] for c in chunks]
    try:
        chunk_embeddings = embed_chunks(chunk_texts)
    except Exception as e:
        return _err(f"Embedding failed: {str(e)}"), 500

    matches      = []
    flagged      = 0
    seen_sources = set()

    for chunk, emb in zip(chunks, chunk_embeddings):
        similar = search_chunk_index(emb, k=3, exclude_paper_id=paper_id)
        for s in similar:
            if s["score"] >= threshold:
                src_paper = papers().find_one(
                    {"_id": ObjectId(s["paper_id"])},
                    {"title": 1}
                ) if s["paper_id"] else None

                match_entry = {
                    "chunk_text":          chunk["text"][:300],
                    "word_offset":         chunk["word_offset"],
                    "matched_paper_id":    s["paper_id"],
                    "matched_paper_title": src_paper["title"] if src_paper else "Unknown",
                    "similarity":          round(s["score"], 4)
                }
                matches.append(match_entry)
                flagged += 1
                break   # one match per chunk

    total = len(chunks)
    overall = round(flagged / total, 4) if total else 0.0
    detected = overall > Config.PLAGIARISM_OVERALL_THRESHOLD

    report = {
        "paper_id":           ObjectId(paper_id),
        "overall_similarity": overall,
        "plagiarism_detected":detected,
        "matches":            matches,
        "total_chunks":       total,
        "flagged_chunks":     flagged,
        "threshold_used":     threshold,
        "created_at":         datetime.utcnow()
    }
    res = plag_reports().insert_one(report)

    return _ok({
        "report_id":           str(res.inserted_id),
        "paper_id":            paper_id,
        "paper_title":         paper["title"],
        "overall_similarity":  overall,
        "plagiarism_detected": detected,
        "flagged_chunks":      flagged,
        "total_chunks":        total,
        "matches":             matches,
        "threshold_used":      threshold
    }), 200


def index_paper_chunks(paper_id, text):
    """Index all chunks of a paper into FAISS chunk index."""
    from backend.services.search_service import add_chunks_to_faiss
    chunks = chunk_text(text, window_words=200, step_words=150)
    if not chunks:
        return 0
    chunk_texts = [c["text"] for c in chunks]
    embeddings  = embed_chunks(chunk_texts)
    meta = [{
        "paper_id":   str(paper_id),
        "chunk_text": c["text"][:200],
        "word_offset":c["word_offset"]
    } for c in chunks]
    add_chunks_to_faiss(embeddings, meta)
    return len(chunks)


