import bcrypt
import uuid
import secrets
from datetime import datetime, timedelta
from bson import ObjectId
from flask_jwt_extended import create_access_token
from backend.models.db import users, invites
from backend.config import Config


def _ok(data): return {"success": True, "data": data, "error": None}
def _err(msg): return {"success": False, "data": None, "error": msg}


def register_user(name, email, password, invite_code):
    # Validate invite code
    invite = invites().find_one({"code": invite_code, "is_used": False})
    if not invite:
        return _err("Invalid or already used invite code"), 400

    if invite.get("expires_at") and invite["expires_at"] < datetime.utcnow():
        return _err("Invite code has expired"), 400

    # Check duplicate email
    if users().find_one({"email": email.lower()}):
        return _err("Email already registered"), 409

    # Hash password
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

    user_doc = {
        "name":         name,
        "email":        email.lower(),
        "password_hash": pw_hash,
        "role":         "user",
        "invite_used":  invite["_id"],
        "created_at":   datetime.utcnow()
    }
    result = users().insert_one(user_doc)
    user_id = str(result.inserted_id)

    # Mark invite used
    invites().update_one(
        {"_id": invite["_id"]},
        {"$set": {"is_used": True, "used_by": result.inserted_id, "used_at": datetime.utcnow()}}
    )

    return _ok({"user_id": user_id, "email": email.lower(), "role": "user"}), 201


def login_user(email, password):
    user = users().find_one({"email": email.lower()})
    if not user:
        return _err("Invalid email or password"), 401

    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return _err("Invalid email or password"), 401

    token = create_access_token(
        identity=str(user["_id"]),
        additional_claims={"role": user["role"], "name": user["name"]},
        expires_delta=timedelta(hours=Config.JWT_EXPIRY_HOURS)
    )
    return _ok({
        "access_token": token,
        "token_type":   "Bearer",
        "expires_in":   Config.JWT_EXPIRY_HOURS * 3600,
        "role":         user["role"],
        "name":         user["name"]
    }), 200


def create_invite(admin_user_id, expires_in_hours=48, note=""):
    code = "INV-" + secrets.token_hex(4).upper()
    expires_at = datetime.utcnow() + timedelta(hours=expires_in_hours)

    doc = {
        "code":       code,
        "created_by": ObjectId(admin_user_id),
        "used_by":    None,
        "is_used":    False,
        "expires_at": expires_at,
        "note":       note,
        "created_at": datetime.utcnow()
    }
    invites().insert_one(doc)
    return _ok({
        "invite_code": code,
        "expires_at":  expires_at.isoformat() + "Z",
        "note":        note
    }), 201


def list_invites():
    all_inv = list(invites().find({}).sort("created_at", -1).limit(100))
    result = []
    for inv in all_inv:
        result.append({
            "code":       inv["code"],
            "is_used":    inv["is_used"],
            "note":       inv.get("note", ""),
            "expires_at": inv["expires_at"].isoformat() + "Z" if inv.get("expires_at") else None,
            "created_at": inv["created_at"].isoformat() + "Z"
        })
    return _ok(result), 200


def list_users():
    all_users = list(users().find({}, {"password_hash": 0}).sort("created_at", -1).limit(200))
    result = []
    for u in all_users:
        result.append({
            "user_id":    str(u["_id"]),
            "name":       u["name"],
            "email":      u["email"],
            "role":       u["role"],
            "created_at": u["created_at"].isoformat() + "Z"
        })
    return _ok(result), 200


def create_admin_user(name, email, password):
    """Used only by bootstrap script — no invite needed."""
    if users().find_one({"email": email.lower()}):
        return False, "Email already registered"
    pw_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    users().insert_one({
        "name":          name,
        "email":         email.lower(),
        "password_hash": pw_hash,
        "role":          "admin",
        "invite_used":   None,
        "created_at":    datetime.utcnow()
    })
    return True, "Admin created"


