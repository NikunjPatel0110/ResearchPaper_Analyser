import os
import sys

# --- CRITICAL: Must be set BEFORE any other imports ---
# PyTorch + FAISS both load OpenMP (libiomp5md / libomp) and collide on Windows.
# This env var tells the Intel OpenMP runtime to allow multiple instances.
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"]       = "1"  # Prevent multi-threaded OpenMP fighting
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"  # Disable TensorFlow oneDNN (collides with FAISS OpenMP)

from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from backend.config import Config
from backend.routes.auth import auth_bp
from backend.routes.papers import papers_bp
from backend.services.plagiarism_service import ensure_indexes
from backend.services.nlp_service import warmup_models


def create_app(config_class=Config):
    app = Flask(__name__, template_folder="templates")
    app.config.from_object(config_class)

    # Extensions
    JWTManager(app)
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # Upload folder
    os.makedirs(app.config.get("UPLOAD_FOLDER", "uploads"), exist_ok=True)

    # Blueprints
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(papers_bp, url_prefix="/api/v1/papers")

    # Database index initialization
    with app.app_context():
        try:
            ensure_indexes()
        except Exception as e:
            app.logger.error(f"Failed to create indexes: {e}")

    # Pre-load all heavy ML models in the main thread.
    # This prevents segfaults when background threads (spawned during upload)
    # try to initialise SentenceTransformer / spaCy for the first time.
    try:
        warmup_models()
    except Exception as e:
        app.logger.warning(f"Model warmup failed (non-fatal): {e}")

    @app.route("/api/v1/health")
    def health():
        return jsonify({"success": True, "data": {"status": "ok"}, "error": None}), 200

    return app


if __name__ == "__main__":
    app = create_app()
    # use_reloader=False prevents Flask from forking a child process which
    # would double-load the OpenMP runtimes and cause a crash on Windows.
    app.run(debug=True, use_reloader=False, port=5000)