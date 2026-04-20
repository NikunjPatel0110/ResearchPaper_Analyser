import requests
from datetime import datetime
from bson import ObjectId
from backend.models.db import papers, ai_reports
from backend.config import Config

# --- LOCAL MODEL INITIALIZATION ---
_detector_pipeline = None

def get_pipeline():
    """Lazily loads the RoBERTa model only when needed."""
    global _detector_pipeline
    if _detector_pipeline is None:
        try:
            import torch
            from transformers import pipeline
            device = 0 if torch.cuda.is_available() else -1
            _detector_pipeline = pipeline(
                "text-classification", 
                model="roberta-base-openai-detector", 
                framework="pt",
                device=device
            )
        except Exception as e:
            print(f"[AI Detect] Local model load failed: {e}")
    return _detector_pipeline

def _ok(data): return {"success": True, "data": data, "error": None}
def _err(msg): return {"success": False, "data": None, "error": msg}

def detect_ai_content(paper_id):
    """
    Analyzes paper text for AI generation probability.
    Priority: ZeroGPT (Paid/Accurate) -> Sapling (Free/Accurate) -> Local Model (Offline).
    """
    paper = papers().find_one({"_id": ObjectId(paper_id)})
    if not paper:
        return _err("Paper not found"), 404

    raw_text = paper.get("raw_text", "")
    if not raw_text or len(raw_text.strip()) < 100:
        return _err("Text too short for reliable AI detection"), 400

    # 1. Try ZeroGPT (If key provided)
    if Config.ZEROGPT_API_KEY:
        print("[AI Detect] Using ZeroGPT API...")
        result = _call_zerogpt(raw_text[:15000]) # ZeroGPT limit around 15k chars
        if "error" not in result:
            return _save_and_return(paper_id, paper["title"], result)
        print(f"[AI Detect] ZeroGPT failed: {result['error']}")

    # 2. Try Sapling (Free tier)
    print("[AI Detect] Using Sapling AI API...")
    result = _call_sapling(raw_text[:8000])
    if "error" not in result:
        return _save_and_return(paper_id, paper["title"], result)
    print(f"[AI Detect] Sapling failed: {result['error']}")

    # 3. Final Fallback: Local Neural Model (Chunked)
    print("[AI Detect] Using Local Model (Chunked Fallback)...")
    result = _local_detection_chunked(raw_text)
    return _save_and_return(paper_id, paper["title"], result)

def _save_and_return(paper_id, title, result):
    """Saves the report to DB and returns the response."""
    result["ai_probability"] = round(result["ai_probability"] * 100, 1) # Convert to percentage
    doc = {
        "paper_id": ObjectId(paper_id),
        "created_at": datetime.utcnow(),
        **result
    }
    res = ai_reports().insert_one(doc)
    
    return _ok({
        "report_id": str(res.inserted_id),
        "paper_id": str(paper_id),
        "paper_title": title,
        "checked_at": datetime.utcnow().isoformat() + "Z",
        **result
    }), 200

# --- PROVIDER: ZeroGPT ---
def _call_zerogpt(text):
    url = "https://api.zerogpt.com/api/detect/detectText"
    headers = {"ApiKey": Config.ZEROGPT_API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(url, json={"input_text": text}, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json().get("data", {})
        pct = float(data.get("fakePercentage", 0))
        return {
            "ai_probability": pct / 100,
            "confidence": "HIGH" if data.get("isHuman") is not None else "MEDIUM",
            "label": _get_label(pct / 100),
            "explanation": data.get("feedback", "ZeroGPT analysis."),
            "api_provider": "zerogpt"
        }
    except Exception as e:
        return {"error": str(e)}

# --- PROVIDER: Sapling ---
def _call_sapling(text):
    url = "https://api.sapling.ai/api/v1/aidetect"
    api_key = Config.SAPLING_API_KEY or "sample"
    try:
        # Take a sample from the middle of the text
        chunk = text[:2000]
        payload = {"key": api_key, "text": chunk}
        r = requests.post(url, json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        score = data.get("score", 0)
        return {
            "ai_probability": float(score),
            "confidence": "MEDIUM",
            "label": _get_label(float(score)),
            "explanation": "Sapling AI detector estimate.",
            "api_provider": "sapling"
        }
    except Exception as e:
        return {"error": str(e)}

# --- PROVIDER: Local Model (Chunked) ---
def _local_detection_chunked(text):
    """
    To prevent false positives, we check 3 chunks (Start, Middle, End) 
    and return the average probability.
    """
    pipeline_fn = get_pipeline()
    if not pipeline_fn:
        return {
            "ai_probability": 0.0, "confidence": "LOW",
            "label": "Analysis Error", "explanation": "Local model failed to load.",
            "api_provider": "local_error"
        }

    # Extract 3 chunks of ~1200 chars (~200 words)
    length = len(text)
    chunks = [
        text[:1200],                           # Start
        text[max(0, length//2 - 600):length//2 + 600], # Middle
        text[max(0, length - 1200):]           # End
    ]
    
    probs = []
    try:
        for c in chunks:
            if len(c.strip()) < 50: continue
            res = pipeline_fn(c, truncation=True, max_length=512)[0]
            # 'Fake' = AI, 'Real' = Human
            p = res['score'] if res['label'] == 'Fake' else (1 - res['score'])
            probs.append(p)
        
        if not probs: return {"ai_probability": 0.0, "confidence": "LOW", "label": "Unknown", "explanation": "Text too short.", "api_provider": "local"}
        
        avg_prob = sum(probs) / len(probs)
        return {
            "ai_probability": avg_prob,
            "confidence": "MEDIUM", # Local is never 100% "HIGH" to avoid arrogance
            "label": _get_label(avg_prob),
            "explanation": f"Average of {len(probs)} neural scans performed locally (Fallback).",
            "api_provider": "huggingface_local"
        }
    except Exception as e:
        print(f"[AI Detect] Local inference error: {e}")
        return {"ai_probability": 0.0, "confidence": "LOW", "label": "Error", "explanation": "Inference error.", "api_provider": "local"}

def _get_label(prob):
    if prob < 0.20: return "Human Written"
    if prob < 0.50: return "Possibly Human"
    if prob < 0.80: return "Possibly AI-Assisted"
    return "AI Generated"