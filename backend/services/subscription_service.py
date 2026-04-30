"""
subscription_service.py
Handles quota checks, plan management, and all subscription state.
"""
from datetime import datetime, timedelta
from bson import ObjectId
from backend.models.db import users, get_collection
from backend.config import Config


def _payments(): return get_collection("payments")
def _ok(data):   return {"success": True,  "data": data, "error": None}
def _err(msg):   return {"success": False, "data": None, "error": msg}


# ─────────────────────────────────────────────────────────────────────────────
# Quota helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_user_quota(user_id):
    """Return full quota status for a user."""
    user = users().find_one({"_id": ObjectId(user_id)})
    if not user:
        return None

    plan          = user.get("plan", "free")
    upload_count  = user.get("upload_count", 0)
    limit         = Config.PLAN_UPLOAD_LIMITS.get(plan, Config.FREE_UPLOAD_LIMIT)
    remaining     = max(0, limit - upload_count)
    plan_expires  = user.get("plan_expires_at")
    is_expired    = (
        plan not in ("free", "lifetime") and
        plan_expires is not None and
        plan_expires < datetime.utcnow()
    )

    # Auto-downgrade expired subscriptions
    if is_expired:
        users().update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"plan": "free", "plan_expires_at": None}}
        )
        plan      = "free"
        limit     = Config.PLAN_UPLOAD_LIMITS["free"]
        remaining = max(0, limit - upload_count)

    return {
        "user_id":       user_id,
        "plan":          plan,
        "plan_label":    Config.PLAN_LABELS.get(plan, plan),
        "upload_count":  upload_count,
        "upload_limit":  limit,
        "remaining":     remaining,
        "can_upload":    remaining > 0,
        "plan_expires":  plan_expires.isoformat() + "Z" if plan_expires else None,
        "is_lifetime":   plan == "lifetime",
    }


def can_upload(user_id):
    """Quick boolean check — True if user may upload another paper."""
    quota = get_user_quota(user_id)
    return quota["can_upload"] if quota else False


def increment_upload_count(user_id):
    """Call this after a successful upload."""
    users().update_one(
        {"_id": ObjectId(user_id)},
        {"$inc": {"upload_count": 1}}
    )


# ─────────────────────────────────────────────────────────────────────────────
# Plan management (called after successful payment verification)
# ─────────────────────────────────────────────────────────────────────────────

def activate_plan(user_id, plan, payment_id, order_id):
    """Activate or upgrade a user's plan after payment is verified."""
    now = datetime.utcnow()

    if plan == "lifetime":
        expires = None
    else:
        # Monthly plans: 30 days from now (or extend existing expiry)
        user = users().find_one({"_id": ObjectId(user_id)})
        current_expiry = user.get("plan_expires_at") if user else None
        base = current_expiry if (current_expiry and current_expiry > now) else now
        expires = base + timedelta(days=30)

    new_limit = Config.PLAN_UPLOAD_LIMITS.get(plan, 10)

    users().update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {
            "plan":             plan,
            "plan_expires_at":  expires,
            "upload_limit":     new_limit,
            "last_payment_id":  payment_id,
            "last_order_id":    order_id,
            "plan_activated_at":now,
        }}
    )

    # Log the payment
    _payments().insert_one({
        "user_id":    ObjectId(user_id),
        "plan":       plan,
        "amount":     Config.PLAN_PRICES.get(plan, 0),
        "currency":   Config.RAZORPAY_CURRENCY,
        "payment_id": payment_id,
        "order_id":   order_id,
        "status":     "captured",
        "created_at": now,
    })

    return _ok({
        "plan":       plan,
        "expires_at": expires.isoformat() + "Z" if expires else None,
        "new_limit":  new_limit,
    })


def get_payment_history(user_id):
    """Return user's payment history."""
    history = list(_payments().find(
        {"user_id": ObjectId(user_id)},
        {"_id": 0, "user_id": 0}
    ).sort("created_at", -1).limit(20))
    for h in history:
        if isinstance(h.get("created_at"), datetime):
            h["created_at"] = h["created_at"].isoformat() + "Z"
    return _ok(history)


# ─────────────────────────────────────────────────────────────────────────────
# Plans catalogue
# ─────────────────────────────────────────────────────────────────────────────

def get_plans():
    """Return all available plans for display in UI."""
    return _ok([
        {
            "plan":         "basic",
            "label":        "Basic",
            "price_paise":  Config.PLAN_PRICES["basic"],
            "price_inr":    Config.PLAN_PRICES["basic"] // 100,
            "upload_limit": Config.PLAN_UPLOAD_LIMITS["basic"],
            "period":       "monthly",
            "features":     ["50 uploads/month", "All NLP features", "Plagiarism check", "AI detection"],
        },
        {
            "plan":         "pro",
            "label":        "Pro",
            "price_paise":  Config.PLAN_PRICES["pro"],
            "price_inr":    Config.PLAN_PRICES["pro"] // 100,
            "upload_limit": Config.PLAN_UPLOAD_LIMITS["pro"],
            "period":       "monthly",
            "features":     ["500 uploads/month", "All Basic features", "Priority processing", "API access"],
        },
        {
            "plan":         "lifetime",
            "label":        "Lifetime",
            "price_paise":  Config.PLAN_PRICES["lifetime"],
            "price_inr":    Config.PLAN_PRICES["lifetime"] // 100,
            "upload_limit": Config.PLAN_UPLOAD_LIMITS["lifetime"],
            "period":       "one-time",
            "features":     ["Unlimited uploads", "All Pro features", "Future updates included"],
        },
    ])