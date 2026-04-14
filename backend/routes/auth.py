from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity
from backend.middleware.auth_middleware import admin_required, jwt_required_custom
from backend.services import auth_service

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(force=True, silent=True) or {}
    required = ["name", "email", "password", "invite_code"]
    missing  = [f for f in required if not data.get(f)]
    if missing:
        return jsonify({"success": False, "data": None, "error": f"Missing fields: {missing}"}), 400

    result, code = auth_service.register_user(
        data["name"], data["email"], data["password"], data["invite_code"]
    )
    return jsonify(result), code


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(force=True, silent=True) or {}
    if not data.get("email") or not data.get("password"):
        return jsonify({"success": False, "data": None, "error": "Email and password required"}), 400
    result, code = auth_service.login_user(data["email"], data["password"])
    return jsonify(result), code


@auth_bp.route("/create-invite", methods=["POST"])
@admin_required
def create_invite():
    admin_id = get_jwt_identity()
    data = request.get_json(force=True, silent=True) or {}
    result, code = auth_service.create_invite(
        admin_id,
        expires_in_hours=data.get("expires_in_hours", 48),
        note=data.get("note", "")
    )
    return jsonify(result), code


@auth_bp.route("/invites", methods=["GET"])
@admin_required
def list_invites():
    result, code = auth_service.list_invites()
    return jsonify(result), code


@auth_bp.route("/users", methods=["GET"])
@admin_required
def list_users():
    result, code = auth_service.list_users()
    return jsonify(result), code


@auth_bp.route("/me", methods=["GET"])
@jwt_required_custom
def me():
    from flask_jwt_extended import get_jwt
    claims = get_jwt()
    return jsonify({"success": True, "data": {
        "user_id": get_jwt_identity(),
        "name":    claims.get("name"),
        "role":    claims.get("role")
    }, "error": None}), 200


