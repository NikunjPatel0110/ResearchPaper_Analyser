from flask import Flask, jsonify
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from backend.config import Config
from backend.routes.auth import auth_bp
from backend.routes.papers import papers_bp
import os


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

    @app.route("/api/v1/health")
    def health():
        return jsonify({"success": True, "data": {"status": "ok"}, "error": None}), 200

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, use_reloader=False, port=5000)


