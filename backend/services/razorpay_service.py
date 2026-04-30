"""
razorpay_service.py
Creates Razorpay orders and verifies payment signatures.
Install: pip install razorpay
"""
import hmac
import hashlib
import razorpay
from backend.config import Config


def _client():
    return razorpay.Client(
        auth=(Config.RAZORPAY_KEY_ID, Config.RAZORPAY_KEY_SECRET)
    )


def _ok(data): return {"success": True,  "data": data, "error": None}
def _err(msg): return {"success": False, "data": None, "error": msg}


# ─────────────────────────────────────────────────────────────────────────────
# Create order
# ─────────────────────────────────────────────────────────────────────────────

def create_order(user_id, plan):
    """
    Create a Razorpay order for the given plan.
    Returns the order details needed by the frontend checkout widget.
    """
    amount = Config.PLAN_PRICES.get(plan)
    if amount is None:
        return _err(f"Unknown plan: {plan}"), 400

    if not Config.RAZORPAY_KEY_ID or not Config.RAZORPAY_KEY_SECRET:
        return _err("Razorpay credentials not configured"), 500

    try:
        order = _client().order.create({
            "amount":   amount,
            "currency": Config.RAZORPAY_CURRENCY,
            "receipt":  f"paperiq_{user_id}_{plan}",
            "notes": {
                "user_id": str(user_id),
                "plan":    plan,
            }
        })
        return _ok({
            "order_id":    order["id"],
            "amount":      order["amount"],
            "currency":    order["currency"],
            "plan":        plan,
            "key_id":      Config.RAZORPAY_KEY_ID,
            "plan_label":  Config.PLAN_LABELS.get(plan, plan),
        }), 200

    except razorpay.errors.BadRequestError as e:
        return _err(f"Razorpay bad request: {str(e)}"), 400
    except Exception as e:
        return _err(f"Order creation failed: {str(e)}"), 500


# ─────────────────────────────────────────────────────────────────────────────
# Verify payment signature (called after Razorpay checkout success)
# ─────────────────────────────────────────────────────────────────────────────

def verify_payment(razorpay_order_id, razorpay_payment_id, razorpay_signature):
    """
    Verify the payment signature using HMAC-SHA256.
    Razorpay docs: https://razorpay.com/docs/payment-gateway/web-integration/standard/integration-steps/#step-3-handle-successful-payments
    """
    if not Config.RAZORPAY_KEY_SECRET:
        return False

    msg       = f"{razorpay_order_id}|{razorpay_payment_id}".encode()
    secret    = Config.RAZORPAY_KEY_SECRET.encode()
    expected  = hmac.new(secret, msg, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, razorpay_signature)


# ─────────────────────────────────────────────────────────────────────────────
# Verify webhook signature (called from /payments/webhook)
# ─────────────────────────────────────────────────────────────────────────────

def verify_webhook_signature(payload_bytes, signature):
    """
    Verify Razorpay webhook POST body signature.
    Set RAZORPAY_WEBHOOK_SECRET in .env from Razorpay dashboard > Webhooks.
    """
    if not Config.RAZORPAY_WEBHOOK_SECRET:
        return False
    secret   = Config.RAZORPAY_WEBHOOK_SECRET.encode()
    expected = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


# ─────────────────────────────────────────────────────────────────────────────
# Fetch payment details from Razorpay (for server-side capture verification)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_payment(payment_id):
    """Fetch payment details from Razorpay API to double-check status."""
    try:
        payment = _client().payment.fetch(payment_id)
        return payment
    except Exception as e:
        return None