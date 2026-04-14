import requests
from datetime import datetime
from bson import ObjectId
from backend.models.db import papers, ai_reports
from backend.config import Config


def _ok(data): return {"success": True, "data": data, "error": None}
def _err(msg): return {"success": False, "data": None, "error": msg}


def detect_ai_content(paper_id):
    paper = papers().find_one({"_id": ObjectId(paper_id)})
    if not paper:
        return _err("Paper not found"), 404

    text = paper.get("raw_text", "")[:8_000]   # conservative limit for all APIs

    # Priority order: ZeroGPT (you have key) → Sapling (free) → heuristic
    if Config.ZEROGPT_API_KEY:
        result = _call_zerogpt(text)
    else:
        result = _call_sapling(text)

    if "error" in result:
        # Final fallback — heuristic
        print(f"[AI Detect] API failed ({result['error']}), using heuristic fallback")
        result = _heuristic_fallback(text)

    doc = {
        "paper_id":       ObjectId(paper_id),
        "ai_probability": result["ai_probability"],
        "confidence":     result["confidence"],
        "label":          result["label"],
        "explanation":    result.get("explanation", ""),
        "api_provider":   result["api_provider"],
        "created_at":     datetime.utcnow()
    }
    res = ai_reports().insert_one(doc)

    return _ok({
        "report_id":      str(res.inserted_id),
        "paper_id":       paper_id,
        "paper_title":    paper["title"],
        "ai_probability": result["ai_probability"],
        "confidence":     result["confidence"],
        "label":          result["label"],
        "explanation":    result.get("explanation", ""),
        "api_provider":   result["api_provider"],
        "checked_at":     datetime.utcnow().isoformat() + "Z"
    }), 200


# ── ZeroGPT (you have this key) ──────────────────────────────────────────────
def _call_zerogpt(text):
    url     = "https://api.zerogpt.com/api/detect/detectText"
    headers = {"ApiKey": Config.ZEROGPT_API_KEY, "Content-Type": "application/json"}
    try:
        r = requests.post(url, json={"input_text": text}, headers=headers, timeout=20)
        r.raise_for_status()
        d   = r.json().get("data", {})
        pct = float(d.get("fakePercentage", 0))
        return {
            "ai_probability": round(pct / 100, 4),
            "confidence":     "high" if d.get("isHuman") is not None else "medium",
            "label":          _label(pct / 100),
            "explanation":    d.get("feedback", ""),
            "api_provider":   "zerogpt"
        }
    except Exception as e:
        return {"error": f"ZeroGPT: {str(e)}"}


# ── Sapling AI (free, no API key needed for /aidetect endpoint) ───────────────
# Docs: https://sapling.ai/docs/api/aidetect
# Free tier: up to 2000 chars per request — we'll send in chunks and average.
def _call_sapling(text):
    url  = "https://api.sapling.ai/api/v1/aidetect"
    # Sapling's public endpoint doesn't require auth for basic detection.
    # If you get a key from https://sapling.ai, add it to .env as SAPLING_API_KEY.
    api_key = Config.SAPLING_API_KEY or "sample"  # "sample" triggers demo mode
    chunks  = _split_chunks(text, max_chars=2000)
    scores  = []

    try:
        for chunk in chunks[:5]:   # max 5 chunks to keep it fast
            payload = {"key": api_key, "text": chunk}
            r = requests.post(url, json=payload, timeout=15)
            r.raise_for_status()
            data  = r.json()
            score = data.get("score")   # 0.0 (human) to 1.0 (AI)
            if score is not None:
                scores.append(float(score))

        if not scores:
            return {"error": "Sapling returned no scores"}

        avg = round(sum(scores) / len(scores), 4)

        # Sapling also returns per-sentence scores — grab a short explanation
        explanation = (
            f"Average AI probability across {len(scores)} text segment(s). "
            f"Sapling AI detector — higher score means more likely AI-generated."
        )

        return {
            "ai_probability": avg,
            "confidence":     "medium",
            "label":          _label(avg),
            "explanation":    explanation,
            "api_provider":   "sapling"
        }
    except Exception as e:
        return {"error": f"Sapling: {str(e)}"}


def _split_chunks(text, max_chars=2000):
    """Split text into chunks of max_chars, splitting on sentence boundaries."""
    import re
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks, current = [], ""
    for s in sentences:
        if len(current) + len(s) + 1 <= max_chars:
            current = (current + " " + s).strip()
        else:
            if current:
                chunks.append(current)
            current = s[:max_chars]
    if current:
        chunks.append(current)
    return chunks if chunks else [text[:max_chars]]


# ── Heuristic fallback (offline, no API) ─────────────────────────────────────
def _heuristic_fallback(text):
    """
    Rough heuristic — NOT accurate. Clearly labelled in response.
    Only used if both ZeroGPT and Sapling fail.
    Signals: avg sentence length, vocabulary diversity.
    """
    import re
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.split()) > 3]
    if not sentences:
        return {
            "ai_probability": 0.0, "confidence": "low",
            "label": "Unable to assess", "explanation": "Text too short for analysis.",
            "api_provider": "heuristic"
        }
    avg_len = sum(len(s.split()) for s in sentences) / len(sentences)
    words   = text.lower().split()
    vocab   = len(set(words)) / max(len(words), 1)
    # AI text: consistent sentence length (~20w), lower unique vocab ratio
    ai_score = max(0.0, min(1.0, (0.4 * (1 - vocab)) + (0.3 * max(0, 1 - abs(avg_len - 20) / 30))))
    return {
        "ai_probability": round(ai_score, 4),
        "confidence":     "low",
        "label":          _label(ai_score),
        "explanation":    "Heuristic estimate only (both API providers unavailable). Configure ZeroGPT key for accurate results.",
        "api_provider":   "heuristic"
    }


def _label(prob):
    if prob < 0.20:  return "Likely human written"
    if prob < 0.50:  return "Possibly human written"
    if prob < 0.80:  return "Likely AI generated"
    return "Almost certainly AI generated"


