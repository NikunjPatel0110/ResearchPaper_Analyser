import os
import uuid
import threading
from datetime import datetime
from flask import Blueprint, request, jsonify, current_app, send_file
from flask_jwt_extended import get_jwt_identity
from bson import ObjectId
from werkzeug.utils import secure_filename

from backend.middleware.auth_middleware import jwt_required_custom
from backend.models.db import papers
from backend.services import (
    parse_service,
    nlp_service,
    search_service,
    compare_service,
    plagiarism_service,
    ai_detect_service,
)

papers_bp = Blueprint("papers", __name__)


def _ok(data):  return {"success": True,  "data": data, "error": None}
def _err(msg):  return {"success": False, "data": None, "error": msg}
def _oid(s):
    try:    return ObjectId(s)
    except: return None


def _log_bg(paper_id, msg):
    """Verbose logging for background process diagnostic."""
    ts = datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}][BG-{paper_id[:6]}] {msg}", flush=True)


def _process_paper(app, paper_id, filepath, ext):
    """Background thread: run full NLP pipeline and update MongoDB."""
    with app.app_context():
        try:
            _log_bg(paper_id, f"START processing: {filepath}")
            
            _log_bg(paper_id, "Step 1/5: Parsing file content...")
            raw_text = parse_service.parse_file(filepath, ext)
            raw_text = parse_service.clean_text(raw_text)
            _log_bg(paper_id, f"Parsing complete. Length: {len(raw_text)} chars")

            _log_bg(paper_id, "Step 2/5: Running NLP pipeline (Summary/NER/Embedding)...")
            # This triggers model loading if not already warmed up
            nlp_result = nlp_service.run_pipeline(raw_text)
            _log_bg(paper_id, "NLP pipeline complete.")

            _log_bg(paper_id, "Step 3/5: Adding to FAISS document index...")
            faiss_row = search_service.add_to_faiss(paper_id, nlp_result["embedding"])
            _log_bg(paper_id, f"FAISS update complete (row {faiss_row})")

            _log_bg(paper_id, "Step 4/5: Updating MongoDB record...")
            papers().update_one({"_id": ObjectId(paper_id)}, {"$set": {
                "raw_text":   raw_text,
                "word_count": parse_service.word_count(raw_text),
                "summary":    nlp_result["summary"],
                "keywords":   nlp_result["keywords"],
                "entities":   nlp_result["entities"],
                "embedding":  nlp_result["embedding"],
                "faiss_row":  faiss_row,
                "status":     "ready",
            }})
            _log_bg(paper_id, "Step 5/5: FINISHED successfully.")

        except Exception as e:
            _log_bg(paper_id, f"CRITICAL FAILURE: {str(e)}")
            import traceback
            traceback.print_exc()
            papers().update_one(
                {"_id": ObjectId(paper_id)},
                {"$set": {"status": "error", "error_msg": str(e)}},
            )


# ── Upload ────────────────────────────────────────────────────────────────────
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

    ext        = parse_service.get_extension(file.filename)
    filename   = secure_filename(f"{uuid.uuid4()}.{ext}")
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"], user_id)
    os.makedirs(upload_dir, exist_ok=True)
    filepath   = os.path.join(upload_dir, filename)
    file.save(filepath)

    title = request.form.get("title", "") or file.filename.rsplit(".", 1)[0]
    
    # Check for duplicates by title for THIS user
    existing = papers().find_one({"user_id": ObjectId(user_id), "title": title})
    if existing:
        return jsonify(_err(f"A paper with the title '{title}' already exists in your library.")), 409

    doc = {
        "user_id":    ObjectId(user_id),
        "title":      title,
        "filename":   filename,
        "file_path":  filepath,
        "file_type":  ext,
        "status":     "processing",
        "created_at": datetime.utcnow(),
    }
    result   = papers().insert_one(doc)
    paper_id = str(result.inserted_id)

    # Kick off NLP pipeline in a background thread — avoids HTTP timeout on large PDFs
    thread = threading.Thread(
        target=_process_paper,
        args=(current_app._get_current_object(), paper_id, filepath, ext),
        daemon=True,
    )
    thread.start()

    # Return immediately with 202 Accepted so the client doesn't time out
    return jsonify(_ok({
        "_id":        paper_id,
        "paper_id":   paper_id,
        "title":      title,
        "status":     "processing",
        "word_count": 0,
        "summary":    "Your paper is being analysed. Check the Insights page in a moment.",
        "keywords":   [],
        "file_type":  ext,
    })), 202


# ── List user's papers ────────────────────────────────────────────────────────
@papers_bp.route("/", methods=["GET"])
@jwt_required_custom
def list_papers():
    user_id    = get_jwt_identity()
    all_papers = list(
        papers()
        .find({"user_id": ObjectId(user_id)}, {"raw_text": 0, "embedding": 0})
        .sort("created_at", -1)
        .limit(50)
    )
    result = []
    for p in all_papers:
        result.append({
            "paper_id":   str(p["_id"]),
            "_id":        str(p["_id"]),
            "title":      p["title"],
            "status":     p.get("status", "unknown"),
            "word_count": p.get("word_count", 0),
            "file_type":  p.get("file_type", ""),
            "created_at": p["created_at"].isoformat() + "Z",
        })
    return jsonify(_ok(result)), 200


# ── Summary ───────────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/summary", methods=["GET"])
@jwt_required_custom
def get_summary(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"title": 1, "summary": 1, "status": 1})
    if not p:                       return jsonify(_err("Paper not found")), 404
    if p.get("status") != "ready":  return jsonify(_err("Paper not yet processed")), 400
    return jsonify(_ok({
        "paper_id": paper_id,
        "title":    p["title"],
        "summary":  p.get("summary", ""),
    })), 200


# ── Keywords ──────────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/keywords", methods=["GET"])
@jwt_required_custom
def get_keywords(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"title": 1, "keywords": 1, "status": 1})
    if not p:                       return jsonify(_err("Paper not found")), 404
    if p.get("status") != "ready":  return jsonify(_err("Paper not yet processed")), 400
    return jsonify(_ok({
        "paper_id": paper_id,
        "title":    p["title"],
        "keywords": p.get("keywords", []),
    })), 200


# ── Entities ──────────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/entities", methods=["GET"])
@jwt_required_custom
def get_entities(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"title": 1, "entities": 1, "status": 1})
    if not p:                       return jsonify(_err("Paper not found")), 404
    if p.get("status") != "ready":  return jsonify(_err("Paper not yet processed")), 400
    return jsonify(_ok({
        "paper_id": paper_id,
        "title":    p["title"],
        "entities": p.get("entities", []),
    })), 200


# ── Insights ──────────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/insights", methods=["GET"])
@jwt_required_custom
def get_insights(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid})
    if not p:                       return jsonify(_err("Paper not found")), 404
    if p.get("status") != "ready":  return jsonify(_err("Paper not yet processed")), 400

    # Internal similar papers
    internal_raw = search_service.search_similar_docs(
        p["embedding"], k=5, exclude_paper_id=paper_id
    )
    internal = []
    for r in internal_raw:
        rp = papers().find_one({"_id": ObjectId(r["paper_id"])}, {"title": 1, "summary": 1})
        if rp:
            internal.append({
                "paper_id":         r["paper_id"],
                "title":            rp["title"],
                "summary":          rp.get("summary", "")[:200],
                "score":            round(r["score"], 4),
                "source":           "internal",
                "url":              f"/api/v1/papers/{r['paper_id']}/file"
            })

    external = search_service.search_external_papers(
        p.get("keywords", []), limit=5, target_embedding=p.get("embedding")
    )

    return jsonify(_ok({
        "paper_id":      paper_id,
        "title":         p["title"],
        "summary":       p.get("summary", ""),
        "keywords":      p.get("keywords", []),
        "entities":      p.get("entities", []),
        "similar_papers": internal + external,
    })), 200


# ── Similar papers ────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/similar", methods=["GET"])
@jwt_required_custom
def get_similar(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"title": 1, "embedding": 1, "keywords": 1, "status": 1})
    if not p:                       return jsonify(_err("Paper not found")), 404
    if p.get("status") != "ready":  return jsonify(_err("Paper not yet processed")), 400

    internal_raw = search_service.search_similar_docs(
        p["embedding"], k=5, exclude_paper_id=paper_id
    )
    internal = []
    for r in internal_raw:
        rp = papers().find_one({"_id": ObjectId(r["paper_id"])}, {"title": 1, "summary": 1})
        if rp:
            internal.append({
                "paper_id": r["paper_id"],
                "title":    rp["title"],
                "summary":  rp.get("summary", "")[:200],
                "score":    round(r["score"], 4),
            })

    external = search_service.search_external_papers(
        p.get("keywords", []), limit=5, target_embedding=p.get("embedding")
    )

    return jsonify(_ok({
        "paper_id": paper_id,
        "title":    p["title"],
        "internal": internal,
        "external": external,
    })), 200


# ── Compare two papers ────────────────────────────────────────────────────────
@papers_bp.route("/compare", methods=["POST"])
@jwt_required_custom
def compare():
    data = request.get_json(force=True, silent=True) or {}
    pid1 = data.get("paper_id_1") or data.get("paper_id_a")
    pid2 = data.get("paper_id_2") or data.get("paper_id_b")
    if not pid1 or not pid2:
        return jsonify(_err("Both paper IDs are required")), 400
    if pid1 == pid2:
        return jsonify(_err("Cannot compare a paper with itself")), 400
    result, code = compare_service.compare_papers(pid1, pid2)
    return jsonify(result), code


# ── Plagiarism check ──────────────────────────────────────────────────────────
@papers_bp.route("/plagiarism-check", methods=["POST"])
@jwt_required_custom
def plagiarism_check():
    data      = request.get_json(force=True, silent=True) or {}
    pid       = data.get("paper_id")
    if not pid:
        return jsonify(_err("paper_id is required")), 400
    threshold = data.get("threshold", None)
    result, code = plagiarism_service.check_plagiarism(pid, threshold)
    return jsonify(result), code


@papers_bp.route("/<paper_id>/plagiarism", methods=["POST"])
@jwt_required_custom
def plagiarism_check_rest(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    user_id = get_jwt_identity()
    p = papers().find_one({"_id": oid, "user_id": ObjectId(user_id)})
    if not p:   return jsonify(_err("Paper not found or not yours")), 404
    if p.get("status") != "ready": return jsonify(_err("Paper not yet processed")), 400
    threshold = (request.get_json(force=True, silent=True) or {}).get("threshold", None)
    result, code = plagiarism_service.check_plagiarism(paper_id, threshold)
    return jsonify(result), code


# ── AI detection ──────────────────────────────────────────────────────────────
@papers_bp.route("/ai-detection", methods=["POST"])
@jwt_required_custom
def ai_detection():
    data = request.get_json(force=True, silent=True) or {}
    pid  = data.get("paper_id")
    if not pid: return jsonify(_err("paper_id is required")), 400
    result, code = ai_detect_service.detect_ai_content(pid)
    return jsonify(result), code


@papers_bp.route("/<paper_id>/ai-detection", methods=["POST"])
@jwt_required_custom
def ai_detection_rest(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    user_id = get_jwt_identity()
    p = papers().find_one({"_id": oid, "user_id": ObjectId(user_id)})
    if not p:   return jsonify(_err("Paper not found or not yours")), 404
    if p.get("status") != "ready": return jsonify(_err("Paper not yet processed")), 400
    result, code = ai_detect_service.detect_ai_content(paper_id)
    return jsonify(result), code


# ── Get single paper meta ─────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>", methods=["GET"])
@jwt_required_custom
def get_paper(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid}, {"raw_text": 0, "embedding": 0})
    if not p:   return jsonify(_err("Paper not found")), 404
    return jsonify(_ok({
        "paper_id":   str(p["_id"]),
        "title":      p["title"],
        "status":     p.get("status"),
        "word_count": p.get("word_count", 0),
        "file_type":  p.get("file_type", ""),
        "summary":    p.get("summary", ""),
        "keywords":   p.get("keywords", []),
        "entities":   p.get("entities", []),
        "created_at": p["created_at"].isoformat() + "Z",
    })), 200


# ── Delete paper ──────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>", methods=["DELETE"])
@jwt_required_custom
def delete_paper(paper_id):
    user_id = get_jwt_identity()
    oid     = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid, "user_id": ObjectId(user_id)})
    if not p:   return jsonify(_err("Paper not found or not yours")), 404
    fp = p.get("file_path")
    if fp and os.path.exists(fp):
        os.remove(fp)
    plagiarism_service.delete_paper_data(paper_id)
    papers().delete_one({"_id": oid})
    return jsonify(_ok({"deleted": paper_id})), 200


# ── Serve file ──────────────────────────────────────────────────────────────
@papers_bp.route("/<paper_id>/file", methods=["GET"])
@jwt_required_custom
def get_paper_file(paper_id):
    oid = _oid(paper_id)
    if not oid: return jsonify(_err("Invalid paper ID")), 400
    p = papers().find_one({"_id": oid})
    if not p:   return jsonify(_err("Paper not found")), 404
    
    filepath = p.get("file_path")
    if not filepath or not os.path.exists(filepath):
        return jsonify(_err("File not found on disk")), 404
        
    return send_file(filepath)


# ── Maintenance (Admin Only) ──────────────────────────────────────────────────
@papers_bp.route("/maintenance/optimize", methods=["POST"])
@jwt_required_custom
def optimize_index():
    from backend.middleware.auth_middleware import admin_required
    from flask import current_app
    
    # We use a nested check because we want to reuse the error handling of admin_required
    # but the decorator needs to be applied correctly. 
    # Actually, let's just use the shared logic.
    user_id = get_jwt_identity()
    from backend.models.db import users
    u = users().find_one({"_id": ObjectId(user_id)})
    if not u or u.get("role") != "admin":
        return jsonify(_err("🛡️ Access denied. Admin only.")), 403

    stats = search_service.sync_index_with_db()
    return jsonify(_ok(stats)), 200