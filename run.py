"""
run.py - Use this to start the backend server.

Sets critical environment variables FIRST, then pre-loads all ML models
on the main thread BEFORE Flask starts accepting requests.

This prevents the Windows DLL collision between PyTorch and FAISS OpenMP
libraries that causes a silent crash (exit code 1) when models are
loaded lazily inside Flask worker threads.
"""
import os
import sys
#added below 2 lines
from dotenv import load_dotenv
load_dotenv()
# ─── MUST be before ANY other import ──────────────────────────────────────────
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"] = "0"   # quieten TF noise
# ──────────────────────────────────────────────────────────────────────────────

print("[*] Loading ML models (first run may take a moment)...", flush=True)

# Pre-load SentenceTransformer on main thread
from sentence_transformers import SentenceTransformer
_embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
print("[OK] Embedding model loaded.", flush=True)

# Pre-load FAISS so its OpenMP DLL is registered before torch arrives
import faiss  # noqa: F401
print("[OK] FAISS loaded.", flush=True)

# Pre-load Torch + HuggingFace pipeline on main thread
import torch
from transformers import pipeline as hf_pipeline
_detector = hf_pipeline(
    "text-classification",
    model="roberta-base-openai-detector",
    framework="pt",
    device=-1  # CPU
)
print("[OK] AI detection model loaded.", flush=True)

# ── Inject pre-loaded singletons into the services so they skip re-loading ───
import backend.services.search_service as _ss
_ss._embedding_model = _embedding_model

import backend.services.ai_detect_service as _ai
_ai._detector_pipeline = _detector

print("[OK] All models ready. Starting Flask...\n", flush=True)

# ── Now safe to start Flask ──────────────────────────────────────────────────
from backend.app import create_app

app = create_app()
app.run(debug=False, use_reloader=False, port=5000)
