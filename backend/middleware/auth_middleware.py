from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt

def jwt_required_custom(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            # Allow token in headers (default) or query string (for direct browser links)
            verify_jwt_in_request(locations=["headers", "query_string"])
        except Exception as e:
            return jsonify({"success": False, "error": "Missing or invalid token", "data": None}), 401
        return fn(*args, **kwargs)
    return wrapper

def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get("role") != "admin":
                return jsonify({"success": False, "error": "Admin access required", "data": None}), 403
        except Exception as e:
            return jsonify({"success": False, "error": "Missing or invalid token", "data": None}), 401
        return fn(*args, **kwargs)
    return wrapper


