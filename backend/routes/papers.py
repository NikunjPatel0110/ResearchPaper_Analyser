import os
import uuid
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from bson import ObjectId
from werkzeug.utils import secure_filename

from backend.middleware.auth_middleware import jwt_required_custom
from backend.models.db import papers
from backend.services import parse_service, nlp_service, search_service, compare_service, plagiarism_service, ai_detect_service

papers_bp = Blueprint("papers", __name__)


def _ok(data):  return {"success": True, "data": data, "error": None}
def _err(msg):  return {"success": False, "data": None, "error": msg}
def _oid(s):
    try: return ObjectId(s)
    except: return None


# ── Upload ───────────────────────────────────────────────────────────────────
@papers_bp.route("/upload", methods=["POST"])
@jwt_required_custom
def upload():
    user_id = get_jwt_identity()

    if "file" not in request.files:
        return jsonify(_err("No file part in request")), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify(_err("No file selected")), 400

    if not parse_service.allowed_extension(file.filename):
        return jsonify(_err("Only PDF, TXT, DOCX allowed")), 400

    ext      = parse_service.get_extension(file.filename)
    filename = secure_filename(f"{uuid.uuid4()}.{ext}")
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], user_id)
    os.makedirs(upload_dir, exist_ok=True)
    filepath = os.path.join(upload_dir, filename)
    file.save(filepath)

    # Determine title
    title = request.form.get("title", "") or file.filename.rsplit(".", 1)[0]

    # Insert placeholder doc
    doc = {
        "user_id":    ObjectId(user_id),
        "title":      title,
        "filename":   filename,
        "file_path":  filepath,
        "file_type":  ext,
        "status":     "processing",
        "created_at": datetime.utcnow()
    }
    result   = papers().insert_one(doc)
    paper_id = str(result.inserted_id)

    try:
        # Parse file
        raw_text = parse_service.parse_file(filepath, ext)
        raw_text = parse_service.clean_text(raw_text)

        # Run NLP pipeline
        nlp_result = nlp_service.run_pipeline(raw_text)

        # Add full-doc embedding to FAISS
        faiss_row = search_service.add_to_faiss(paper_id, nlp_result["embedding"])

        # Index chunks for plagiarism
        plagiarism_service.index_paper_chunks(paper_id, raw_text)

        # Update MongoDB doc
        papers().update_one({"_id": ObjectId(paper_id)}, {"$set": {
            "raw_text":   raw_text,
            "word_count": parse_service.word_count(raw_text),
            "summary":    nlp_result["summary"],
            "keywords":   nlp_result["keywords"],
            "entities":   nlp_result["entities"],
            "embedding":  nlp_result["embedding"],
            "faiss_row":  faiss_row,
            "status":     "ready"
        }})
    except Exception as e:
        papers().update_one({"_id": ObjectId(paper_id)}, {"$set": {"status": "error", "error_msg": str(e)}})
        return jsonify(_err(f"Processing failed: {str(e)}")), 500

    updated = papers().find_one({"_id": ObjectId(paper_id)})
    return jsonify(_ok({
        "_id":        paper_id,
        "paper_id":   paper_id,
        "title":      updated["title"],
        "status":     updated["status"],
        "word_count": updated.get("word_count", 0),
        "summary":    updated.get("summary", ""),
        "keywords":   updated.get("keywords", []),
        "file_type":  ext
    })), 201


# ── List user's papers ────────────────────────────────────────────────────────
@papers_bp.route("/", methods=["GET"])
@jwt_required_custom
def list_papers():
    user_id = get_jwt_identity()
    all_papers = list(papers().find(
        {"user_id": ObjectId(user_id)},
        {"raw_text": 0, "embedding": 0}
    ).sort("created_at", -1).limit(50))
    result = []
    for p in all_papers:
        result.append({
            "paper_id":   str(p["_id"]),
            "title":      p["title"],
            "status":     p.get("status", "unknown"),
            "word_count": p.get("word_count", 0),
            "file_type":  p.get("file_type", ""),
            "created_at": p["created_at"].isoformat() + "Z"
        })
    return jsonify(_ok(result)), 200


# ── Summary ───────────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/summary", methods=["GET"])
@jwt_required_custom
def get_summary(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"title": 1, "summary": 1, "status": 1})
    if not p: return jsonify(_err("Paper not found")), 404
    if p.get("status") != "ready": return jsonify(_err("Paper not yet processed")), 400
    return jsonify(_ok({
        "paper_id": paper_id,
        "title":    p["title"],
        "summary":  p.get("summary", "")
    })), 200


# ── Keywords ──────────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/keywords", methods=["GET"])
@jwt_required_custom
def get_keywords(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"title": 1, "keywords": 1, "status": 1})
    if not p: return jsonify(_err("Paper not found")), 404
    if p.get("status") != "ready": return jsonify(_err("Paper not yet processed")), 400
    return jsonify(_ok({"paper_id": paper_id, "title": p["title"], "keywords": p.get("keywords", [])})), 200


# ── Entities ──────────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/entities", methods=["GET"])
@jwt_required_custom
def get_entities(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"title": 1, "entities": 1, "status": 1})
    if not p: return jsonify(_err("Paper not found")), 404
    if p.get("status") != "ready": return jsonify(_err("Paper not yet processed")), 400
    return jsonify(_ok({"paper_id": paper_id, "title": p["title"], "entities": p.get("entities", [])})), 200


# ── Similar papers ────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/similar", methods=["GET"])
@jwt_required_custom
def get_similar(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"title": 1, "embedding": 1, "keywords": 1, "status": 1})
    if not p: return jsonify(_err("Paper not found")), 404
    if p.get("status") != "ready": return jsonify(_err("Paper not yet processed")), 400

    # Internal FAISS search
    internal_raw = search_service.search_similar_docs(p["embedding"], k=5, exclude_paper_id=paper_id)
    internal = []
    for r in internal_raw:
        rp = papers().find_one({"_id": ObjectId(r["paper_id"])}, {"title": 1, "summary": 1})
        if rp:
            internal.append({
                "paper_id": r["paper_id"],
                "title":    rp["title"],
                "summary":  rp.get("summary", "")[:200],
                "score":    round(r["score"], 4)
            })

    # External — OpenAlex first (free, no key), arXiv fallback (free, no key)
    external = search_service.search_external_papers(p.get("keywords", []), limit=5)

    return jsonify(_ok({
        "paper_id":  paper_id,
        "title":     p["title"],
        "internal":  internal,
        "external":  external
    })), 200


# ── Compare two papers ────────────────────────────────────────────────────────
@papers_bp.route("/compare", methods=["POST"])
@jwt_required_custom
def compare():
    data = request.get_json(force=True, silent=True) or {}
    pid1 = data.get("paper_id_1")
    pid2 = data.get("paper_id_2")
    if not pid1 or not pid2:
        return jsonify(_err("Both paper_id_1 and paper_id_2 are required")), 400
    if pid1 == pid2:
        return jsonify(_err("Cannot compare a paper with itself")), 400
    result, code = compare_service.compare_papers(pid1, pid2)
    return jsonify(result), code


# ── Plagiarism check ──────────────────────────────────────────────────────────
@papers_bp.route("/plagiarism-check", methods=["POST"])
@jwt_required_custom
def plagiarism_check():
    data = request.get_json(force=True, silent=True) or {}
    pid  = data.get("paper_id")
    if not pid:
        return jsonify(_err("paper_id is required")), 400
    threshold = data.get("threshold", None)
    result, code = plagiarism_service.check_plagiarism(pid, threshold)
    return jsonify(result), code


# ── AI detection ──────────────────────────────────────────────────────────────
@papers_bp.route("/ai-detection", methods=["POST"])
@jwt_required_custom
def ai_detection():
    data = request.get_json(force=True, silent=True) or {}
    pid  = data.get("paper_id")
    if not pid:
        return jsonify(_err("paper_id is required")), 400
    result, code = ai_detect_service.detect_ai_content(pid)
    return jsonify(result), code


# ── Get single paper meta ─────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>", methods=["GET"])
@jwt_required_custom
def get_paper(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"raw_text": 0, "embedding": 0})
    if not p: return jsonify(_err("Paper not found")), 404
    return jsonify(_ok({
        "paper_id":   str(p["_id"]),
        "title":      p["title"],
        "status":     p.get("status"),
        "word_count": p.get("word_count", 0),
        "file_type":  p.get("file_type", ""),
        "summary":    p.get("summary", ""),
        "keywords":   p.get("keywords", []),
        "entities":   p.get("entities", []),
        "created_at": p["created_at"].isoformat() + "Z"
    })), 200


# ── Delete paper ──────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>", methods=["DELETE"])
@jwt_required_custom
def delete_paper(paper_id):
    user_id = get_jwt_identity()
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid, "user_id": ObjectId(user_id)})
    if not p: return jsonify(_err("Paper not found or not yours")), 404
    # Delete file
    fp = p.get("file_path")
    if fp and os.path.exists(fp):
        os.remove(fp)
    papers().delete_one({"_id": oid})
    return jsonify(_ok({"deleted": paper_id})), 200


