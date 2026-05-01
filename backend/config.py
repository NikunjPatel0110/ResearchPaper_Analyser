# import os
# from dotenv import load_dotenv

# load_dotenv()

# class Config:
#     MONGO_URI          = os.getenv("MONGO_URI", "mongodb://localhost:27017/paperiq")
#     JWT_SECRET_KEY     = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me-use-32-chars!!")
#     JWT_EXPIRY_HOURS   = int(os.getenv("JWT_EXPIRY_HOURS", 24))
#     UPLOAD_FOLDER      = os.getenv("UPLOAD_FOLDER", "uploads")
#     MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_MB", 20)) * 1024 * 1024
#     ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}

#     # AI Detection
#     ZEROGPT_API_KEY = os.getenv("ZEROGPT_API_KEY", "")   # ✅ you have this
#     SAPLING_API_KEY = os.getenv("SAPLING_API_KEY", "")   # optional — free without key too

#     # External paper search — OpenAlex & arXiv are both free with no key needed
#     # No config required for either.

#     FAISS_INDEX_PATH             = "faiss.index"
#     FAISS_META_PATH              = "faiss_meta.json"
#     SIMILARITY_THRESHOLD         = 0.85
#     PLAGIARISM_OVERALL_THRESHOLD = 0.15
# #------------------
# # Paste these into your existing Config class
# RAZORPAY_KEY_ID         = os.getenv("RAZORPAY_KEY_ID", "")
# RAZORPAY_KEY_SECRET     = os.getenv("RAZORPAY_KEY_SECRET", "")
# RAZORPAY_CURRENCY       = os.getenv("RAZORPAY_CURRENCY", "INR")
# RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

# FREE_UPLOAD_LIMIT = int(os.getenv("FREE_UPLOAD_LIMIT", 10))

# PLAN_PRICES = {
#     "basic":    int(os.getenv("PLAN_BASIC_PRICE",    49900)),
#     "pro":      int(os.getenv("PLAN_PRO_PRICE",      99900)),
#     "lifetime": int(os.getenv("PLAN_LIFETIME_PRICE", 299900)),
# }
# PLAN_UPLOAD_LIMITS = {
#     "free": 10, "basic": 50, "pro": 500, "lifetime": 999999,
# }
# PLAN_LABELS = {
#     "free": "Free", "basic": "Basic - Rs.499/month",
#     "pro": "Pro - Rs.999/month", "lifetime": "Lifetime - Rs.2999",
# }


# =================================
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGO_URI          = os.getenv("MONGO_URI", "mongodb://localhost:27017/paperiq")
    JWT_SECRET_KEY     = os.getenv("JWT_SECRET_KEY", "dev-secret-change-me-use-32-chars!!")
    JWT_EXPIRY_HOURS   = int(os.getenv("JWT_EXPIRY_HOURS", 24))
    UPLOAD_FOLDER      = os.getenv("UPLOAD_FOLDER", "uploads")
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_CONTENT_MB", 20)) * 1024 * 1024
    ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}

    # AI Detection
    ZEROGPT_API_KEY = os.getenv("ZEROGPT_API_KEY", "")   # ✅ you have this
    SAPLING_API_KEY = os.getenv("SAPLING_API_KEY", "")   # optional — free without key too

    # External paper search — OpenAlex & arXiv are both free with no key needed
    # No config required for either.

    FAISS_INDEX_PATH             = "faiss.index"
    FAISS_META_PATH              = "faiss_meta.json"
    SIMILARITY_THRESHOLD         = 0.85
    PLAGIARISM_OVERALL_THRESHOLD = 0.15

    # ------------------
    # Razorpay & Quota Limits (Properly Indented!)
    # ------------------
    RAZORPAY_KEY_ID         = os.getenv("RAZORPAY_KEY_ID", "")
    RAZORPAY_KEY_SECRET     = os.getenv("RAZORPAY_KEY_SECRET", "")
    RAZORPAY_CURRENCY       = os.getenv("RAZORPAY_CURRENCY", "INR")
    RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    FREE_UPLOAD_LIMIT = int(os.getenv("FREE_UPLOAD_LIMIT", 2))

    PLAN_PRICES = {
        "basic":    int(os.getenv("PLAN_BASIC_PRICE",    49900)),
        "pro":      int(os.getenv("PLAN_PRO_PRICE",      99900)),
        "lifetime": int(os.getenv("PLAN_LIFETIME_PRICE", 299900)),
    }
    PLAN_UPLOAD_LIMITS = {
        "free": 2, "basic": 50, "pro": 500, "lifetime": 999999,
    }
    PLAN_LABELS = {
        "free": "Free", "basic": "Basic - Rs.499/month",
        "pro": "Pro - Rs.999/month", "lifetime": "Lifetime - Rs.2999",
    }