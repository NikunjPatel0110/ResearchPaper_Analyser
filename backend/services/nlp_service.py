import re
import math
from collections import Counter

import nltk
import spacy
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sentence_transformers import SentenceTransformer

# ── lazy-loaded singletons ──────────────────────────────────────────────────
_spacy_nlp   = None
_st_model    = None

def _nlp():
    global _spacy_nlp
    if _spacy_nlp is None:
        _spacy_nlp = spacy.load("en_core_web_sm")
    return _spacy_nlp

def _st():
    global _st_model
    if _st_model is None:
        _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _st_model


# ── NLTK downloads (idempotent) ─────────────────────────────────────────────
def ensure_nltk():
    for pkg in ["punkt_tab", "punkt", "stopwords", "averaged_perceptron_tagger", "wordnet"]:
        try:
            if "punkt" in pkg:
                nltk.data.find(f"tokenizers/{pkg}")
            else:
                nltk.data.find(f"corpora/{pkg}")
        except (LookupError, OSError):
            nltk.download(pkg, quiet=True)
            
ensure_nltk()
from nltk.corpus import stopwords
from nltk.tokenize import sent_tokenize, word_tokenize

STOP_WORDS = set(stopwords.words("english"))


# ── Named Entity Recognition ────────────────────────────────────────────────
def extract_entities(text):
    """Run spaCy NER on text (capped at 100k chars)."""
    doc = _nlp()(text[:100_000])
    KEEP = {"PERSON", "ORG", "GPE", "DATE", "WORK_OF_ART", "LOC", "EVENT"}
    seen = {}
    for ent in doc.ents:
        if ent.label_ in KEEP:
            key = (ent.text.strip(), ent.label_)
            seen[key] = seen.get(key, 0) + 1
    return sorted(
        [{"text": k[0], "label": k[1], "count": v} for k, v in seen.items()],
        key=lambda x: x["count"], reverse=True
    )[:50]


# ── Keyword extraction ──────────────────────────────────────────────────────
def extract_keywords(text, top_n=20):
    """TF-based keyword scoring, filtered by POS (nouns preferred)."""
    words = [
        w.lower() for w in word_tokenize(text)
        if w.isalpha() and w.lower() not in STOP_WORDS and len(w) > 3
    ]
    freq  = Counter(words)
    max_f = max(freq.values()) if freq else 1
    scored = [(w, round(f / max_f, 3)) for w, f in freq.most_common(top_n * 3)]

    # Boost multi-word noun phrases via spaCy (best-effort, capped)
    doc = _nlp()(text[:30_000])
    np_counts = Counter()
    for chunk in doc.noun_chunks:
        phrase = chunk.text.lower().strip()
        if 2 < len(phrase) < 40 and not all(w in STOP_WORDS for w in phrase.split()):
            np_counts[phrase] += 1
    np_max = max(np_counts.values()) if np_counts else 1
    for phrase, cnt in np_counts.most_common(top_n):
        scored.append((phrase, round(cnt / np_max * 0.9, 3)))

    # Deduplicate and sort
    seen_kw = {}
    for word, score in scored:
        if word not in seen_kw:
            seen_kw[word] = score
    final = sorted(seen_kw.items(), key=lambda x: x[1], reverse=True)
    return [{"word": w, "score": s} for w, s in final[:top_n]]


# ── Extractive summarisation ────────────────────────────────────────────────
def summarise(text, n_sentences=6):
    """TF-IDF extractive summariser."""
    sentences = sent_tokenize(text)
    if len(sentences) <= n_sentences:
        return " ".join(sentences)

    # Remove very short sentences
    valid = [s for s in sentences if len(s.split()) > 6]
    if len(valid) <= n_sentences:
        return " ".join(valid[:n_sentences])

    try:
        tfidf  = TfidfVectorizer(stop_words="english", max_features=1000)
        matrix = tfidf.fit_transform(valid)
        scores = np.array(matrix.sum(axis=1)).flatten()
        top_idx = sorted(np.argsort(scores)[-n_sentences:])
        return " ".join(valid[i] for i in top_idx)
    except Exception:
        return " ".join(valid[:n_sentences])


# ── Sentence embedding ──────────────────────────────────────────────────────
def embed_text(text):
    """Return 384-dim normalised embedding as a Python list."""
    # all-MiniLM-L6-v2 max 512 tokens ≈ ~2000 chars safe
    snippet = text[:3000]
    vec = _st().encode(snippet, normalize_embeddings=True)
    return vec.tolist()


def embed_chunks(chunks):
    """Embed a list of chunk strings, return list of lists."""
    texts = [c[:2000] for c in chunks]
    vecs  = _st().encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vecs]


# ── Text chunking (for plagiarism) ──────────────────────────────────────────
def chunk_text(text, window_words=200, step_words=150):
    words = text.split()
    chunks = []
    for i in range(0, max(1, len(words) - window_words + 1), step_words):
        chunk_words = words[i:i + window_words]
        if len(chunk_words) >= 30:
            chunks.append({"text": " ".join(chunk_words), "word_offset": i})
    # Always include a trailing chunk if there's enough text
    if words and len(words) >= 30:
        last_start = max(0, len(words) - window_words)
        last_chunk = words[last_start:]
        if last_start not in [c["word_offset"] for c in chunks]:
            chunks.append({"text": " ".join(last_chunk), "word_offset": last_start})
    return chunks


# ── Cosine similarity helper ─────────────────────────────────────────────────
def cosine_similarity(vec1, vec2):
    a = np.array(vec1, dtype="float32")
    b = np.array(vec2, dtype="float32")
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


# ── Run full pipeline ────────────────────────────────────────────────────────
def run_pipeline(text):
    """Run all NLP steps and return dict of results."""
    summary  = summarise(text)
    keywords = extract_keywords(text)
    entities = extract_entities(text)
    embedding= embed_text(text)
    return {
        "summary":   summary,
        "keywords":  keywords,
        "entities":  entities,
        "embedding": embedding
    }


