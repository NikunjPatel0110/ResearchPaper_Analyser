from datetime import datetime
from bson import ObjectId
from backend.models.db import papers, comparisons, embeddings
from backend.services.nlp_service import cosine_similarity


def _ok(data): return {"success": True, "data": data, "error": None}
def _err(msg): return {"success": False, "data": None, "error": msg}


def compare_papers(paper_id_1, paper_id_2):
    p1 = papers().find_one({"_id": ObjectId(paper_id_1)})
    p2 = papers().find_one({"_id": ObjectId(paper_id_2)})

    if not p1 or not p2:
        return _err("One or both papers not found"), 404

    if p1.get("status") != "ready" or p2.get("status") != "ready":
        return _err("Papers must be fully processed before comparing"), 400

    # Load embeddings from paper docs
    emb1 = p1.get("embedding", [])
    emb2 = p2.get("embedding", [])
    similarity_score = cosine_similarity(emb1, emb2) if emb1 and emb2 else 0.0

    # Keyword overlap (Jaccard)
    kw1 = set(k["word"] for k in p1.get("keywords", []))
    kw2 = set(k["word"] for k in p2.get("keywords", []))
    shared = kw1 & kw2
    union  = kw1 | kw2
    keyword_overlap = round(len(shared) / len(union), 3) if union else 0.0

    doc = {
        "paper_id_1":       ObjectId(paper_id_1),
        "paper_id_2":       ObjectId(paper_id_2),
        "similarity_score": round(similarity_score, 4),
        "keyword_overlap":  keyword_overlap,
        "shared_keywords":  list(shared),
        "unique_to_p1":     list(kw1 - kw2),
        "unique_to_p2":     list(kw2 - kw1),
        "created_at":       datetime.utcnow()
    }
    res = comparisons().insert_one(doc)

    return _ok({
        "comparison_id":     str(res.inserted_id),
        "paper_1":           {"id": paper_id_1, "title": p1["title"]},
        "paper_2":           {"id": paper_id_2, "title": p2["title"]},
        "similarity_score":  round(similarity_score, 4),
        "keyword_overlap":   keyword_overlap,
        "shared_keywords":   list(shared),
        "unique_to_paper_1": list(kw1 - kw2),
        "unique_to_paper_2": list(kw2 - kw1),
        "summary_1":         p1.get("summary", ""),
        "summary_2":         p2.get("summary", "")
    }), 200


