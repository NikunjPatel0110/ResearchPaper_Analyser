"""
payments.py — Blueprint for all payment and subscription routes.

Endpoints:
  GET  /api/v1/payments/plans            — list all plans
  GET  /api/v1/payments/quota            — current user's quota
  POST /api/v1/payments/create-order     — create Razorpay order
  POST /api/v1/payments/verify           — verify + activate after checkout
  GET  /api/v1/payments/history          — user's payment history
  POST /api/v1/payments/webhook          — Razorpay server-to-server webhook
"""
import json
from flask import Blueprint, request, jsonify
from flask_jwt_extended import get_jwt_identity

from backend.middleware.auth_middleware import jwt_required_custom
from backend.services import subscription_service, razorpay_service
from backend.config import Config

payments_bp = Blueprint("payments", __name__, url_prefix="/api/v1/payments")


def _ok(data): return {"success": True,  "data": data, "error": None}
def _err(msg): return {"success": False, "data": None, "error": msg}


# ── Plans catalogue ───────────────────────────────────────────────────────────
@payments_bp.route("/plans", methods=["GET"])
def list_plans():
    # plans = subscription_service.get_plans()
    # return jsonify({"success": True, "data": plans}), 200
    response = subscription_service.get_plans()
    return jsonify(response), 200



# ── Current user quota ────────────────────────────────────────────────────────
@payments_bp.route("/quota", methods=["GET"])
@jwt_required_custom
def get_quota():
    user_id = get_jwt_identity()
    quota   = subscription_service.get_user_quota(user_id)
    if not quota:
        return jsonify(_err("User not found")), 404
    return jsonify(_ok(quota)), 200


# ── Create Razorpay order ─────────────────────────────────────────────────────
@payments_bp.route("/create-order", methods=["POST"])
@jwt_required_custom
def create_order():
    """
    Request:  { "plan": "basic" | "pro" | "lifetime" }
    Response: { order_id, amount, currency, key_id, plan, plan_label }
    Frontend uses key_id + order_id to open Razorpay checkout widget.
    """
    user_id = get_jwt_identity()
    data    = request.get_json(force=True, silent=True) or {}
    plan    = data.get("plan", "").strip().lower()

    if plan not in Config.PLAN_PRICES:
        return jsonify(_err(f"Invalid plan. Choose from: {list(Config.PLAN_PRICES)}")), 400

    result, code = razorpay_service.create_order(user_id, plan)
    return jsonify(result), code


# ── Verify payment and activate plan ─────────────────────────────────────────
@payments_bp.route("/verify", methods=["POST"])
@jwt_required_custom
def verify_payment():
    """
    Called by frontend immediately after Razorpay checkout success handler fires.

    Request:
    {
      "razorpay_order_id":   "order_xxx",
      "razorpay_payment_id": "pay_xxx",
      "razorpay_signature":  "hex_string",
      "plan":                "basic" | "pro" | "lifetime"
    }
    """
    user_id = get_jwt_identity()
    data    = request.get_json(force=True, silent=True) or {}

    order_id   = data.get("razorpay_order_id",   "")
    payment_id = data.get("razorpay_payment_id", "")
    signature  = data.get("razorpay_signature",  "")
    plan       = data.get("plan",                "")

    if not all([order_id, payment_id, signature, plan]):
        return jsonify(_err("Missing required fields: order_id, payment_id, signature, plan")), 400

    if plan not in Config.PLAN_PRICES:
        return jsonify(_err("Invalid plan")), 400

    # 1. Verify HMAC signature
    if not razorpay_service.verify_payment(order_id, payment_id, signature):
        return jsonify(_err("Payment signature verification failed. Do not retry — contact support.")), 400

    # 2. (Optional but recommended) Double-check payment status via Razorpay API
    payment_details = razorpay_service.fetch_payment(payment_id)
    if payment_details:
        status = payment_details.get("status", "")
        if status not in ("captured", "authorized"):
            return jsonify(_err(f"Payment not captured. Status: {status}")), 402

    # 3. Activate plan
    response = subscription_service.activate_plan(user_id, plan, payment_id, order_id)
    return jsonify(response), 200


# ── Payment history ───────────────────────────────────────────────────────────
@payments_bp.route("/history", methods=["GET"])
@jwt_required_custom
def payment_history():
    user_id = get_jwt_identity()
    response = subscription_service.get_payment_history(user_id)
    return jsonify(response), 200


# ── Razorpay Webhook (server-to-server, no JWT) ───────────────────────────────
@payments_bp.route("/webhook", methods=["POST"])
def webhook():
    """
    Razorpay will POST to this URL on payment events.
    Register this URL in Razorpay Dashboard > Webhooks.
    Recommended events to subscribe: payment.captured, payment.failed

    This is a safety net — the /verify endpoint above is the primary activation path.
    The webhook handles edge cases where the user closed the browser before /verify ran.
    """
    payload_bytes = request.get_data()
    signature     = request.headers.get("X-Razorpay-Signature", "")

    if not razorpay_service.verify_webhook_signature(payload_bytes, signature):
        return jsonify(_err("Invalid webhook signature")), 400

    try:
        event = json.loads(payload_bytes)
    except Exception:
        return jsonify(_err("Invalid JSON")), 400

    event_type = event.get("event", "")

    if event_type == "payment.captured":
        payment = event.get("payload", {}).get("payment", {}).get("entity", {})
        _handle_captured(payment)

    elif event_type == "payment.failed":
        payment = event.get("payload", {}).get("payment", {}).get("entity", {})
        _handle_failed(payment)

    # Always return 200 so Razorpay doesn't retry
    return jsonify({"status": "ok"}), 200


def _handle_captured(payment):
    """Activate plan from webhook payment.captured event."""
    notes      = payment.get("notes", {})
    user_id    = notes.get("user_id")
    plan       = notes.get("plan")
    payment_id = payment.get("id")
    order_id   = payment.get("order_id")

    if not all([user_id, plan, payment_id, order_id]):
        return

    # Idempotency: check if this payment_id was already processed
    from backend.models.db import get_collection
    existing = get_collection("payments").find_one({"payment_id": payment_id})
    if existing:
        return  # Already processed via /verify — skip

    subscription_service.activate_plan(user_id, plan, payment_id, order_id)


def _handle_failed(payment):
    """Log failed payment for debugging."""
    from datetime import datetime
    from backend.models.db import get_collection
    get_collection("payments").insert_one({
        "payment_id": payment.get("id"),
        "order_id":   payment.get("order_id"),
        "status":     "failed",
        "error":      payment.get("error_description", ""),
        "created_at": datetime.utcnow(),
    })