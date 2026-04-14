import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    MONGO_URI          = os.getenv("MONGO_URI", "mongodb://localhost:27017/paperiq")
    JWT_SECRET_KEY     = os.getenv("JWT_SECRET", "dev-secret-change-me")
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


