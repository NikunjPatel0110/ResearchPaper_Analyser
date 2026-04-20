# import re
# import math
# import threading
# import numpy as np
# from collections import Counter
# import google.generativeai as genai

# # ── lazy-loaded singletons ──────────────────────────────────────────────────
# _spacy_nlp   = None
# _st_model    = None
# _model_lock  = threading.Lock()

# def _nlp():
#     global _spacy_nlp
#     if _spacy_nlp is None:
#         import spacy
#         with _model_lock:
#             if _spacy_nlp is None:          # double-checked locking
#                 _spacy_nlp = spacy.load("en_core_web_sm")
#     return _spacy_nlp

# def _st():
#     global _st_model
#     if _st_model is None:
#         from sentence_transformers import SentenceTransformer
#         with _model_lock:
#             if _st_model is None:           # double-checked locking
#                 _st_model = SentenceTransformer("all-MiniLM-L6-v2")
#     return _st_model


# def warmup_models():
#     """Eagerly load all heavy models and indexes in the calling thread.
#     Call this once at app startup (main thread) so background threads
#     never trigger model initialisation — which can segfault on Windows.
    
#     CRITICAL: Order matters on Windows. We must load ST before NLTK/spaCy 
#     to avoid native OpenMP/oneDNN initialization conflicts.
#     """
#     print("[warmup] 1/4 Loading SentenceTransformer (ST)...", flush=True)
#     _st()
    
#     print("[warmup] 2/4 Loading spaCy model...", flush=True)
#     _nlp()
    
#     print("[warmup] 3/4 Initialising NLTK...", flush=True)
#     ensure_nltk()
    
#     print("[warmup] 4/4 Pre-loading FAISS index...", flush=True)
#     from backend.services.search_service import warmup_faiss
#     warmup_faiss()
    
#     print("[warmup] ALL SYSTEMS GO. Models ready.", flush=True)


# # ── NLTK downloads (idempotent) ─────────────────────────────────────────────
# _nltk_ready = False

# def ensure_nltk():
#     global _nltk_ready
#     if _nltk_ready:
#         return
        
#     import nltk
#     for pkg in ["punkt_tab", "punkt", "stopwords", "averaged_perceptron_tagger", "wordnet"]:
#         try:
#             if "punkt" in pkg:
#                 nltk.data.find(f"tokenizers/{pkg}")
#             else:
#                 nltk.data.find(f"corpora/{pkg}")
#         except (LookupError, OSError):
#             nltk.download(pkg, quiet=True)
    
#     global STOP_WORDS, sent_tokenize, word_tokenize
#     from nltk.corpus import stopwords
#     from nltk.tokenize import sent_tokenize, word_tokenize
#     STOP_WORDS = set(stopwords.words("english"))
#     _nltk_ready = True

# # We still need these at module level for other functions, but they will be 
# # populated by the first call to ensure_nltk() or warmup_models().
# STOP_WORDS = set()
# sent_tokenize = None
# word_tokenize = None

# def _get_tokenize():
#     """Lazy fetch of NLTK tokenizers."""
#     ensure_nltk()
#     from nltk.tokenize import sent_tokenize, word_tokenize
#     return sent_tokenize, word_tokenize


# # ── Named Entity Recognition ────────────────────────────────────────────────
# def extract_entities(text):
#     """Run spaCy NER on text (capped at 100k chars)."""
#     doc = _nlp()(text[:100_000])
#     KEEP = {"PERSON", "ORG", "GPE", "DATE", "WORK_OF_ART", "LOC", "EVENT"}
#     seen = {}
#     for ent in doc.ents:
#         if ent.label_ in KEEP:
#             key = (ent.text.strip(), ent.label_)
#             seen[key] = seen.get(key, 0) + 1
#     return sorted(
#         [{"text": k[0], "label": k[1], "count": v} for k, v in seen.items()],
#         key=lambda x: x["count"], reverse=True
#     )[:50]


# # ── Keyword extraction ──────────────────────────────────────────────────────
# def extract_keywords(text, top_n=20):
#     """TF-based keyword scoring, filtered by POS (nouns preferred)."""
#     ensure_nltk()
#     from nltk.tokenize import word_tokenize
    
#     words = [
#         w.lower() for w in word_tokenize(text)
#         if w.isalpha() and w.lower() in STOP_WORDS and len(w) > 3
#     ]
#     # Wait, the logic was: w.lower() NOT in STOP_WORDS. 
#     # Let me fix that while I'm here.
#     words = [
#         w.lower() for w in word_tokenize(text)
#         if w.isalpha() and w.lower() not in STOP_WORDS and len(w) > 3
#     ]
    
#     freq  = Counter(words)
#     max_f = max(freq.values()) if freq else 1
#     scored = [(w, round(f / max_f, 3)) for w, f in freq.most_common(top_n * 3)]

#     # Boost multi-word noun phrases via spaCy (best-effort, capped)
#     doc = _nlp()(text[:30_000])
#     np_counts = Counter()
#     for chunk in doc.noun_chunks:
#         phrase = chunk.text.lower().strip()
#         if 2 < len(phrase) < 40 and not all(w in STOP_WORDS for w in phrase.split()):
#             np_counts[phrase] += 1
#     np_max = max(np_counts.values()) if np_counts else 1
#     for phrase, cnt in np_counts.most_common(top_n):
#         scored.append((phrase, round(cnt / np_max * 0.9, 3)))

#     # Deduplicate and sort
#     seen_kw = {}
#     for word, score in scored:
#         if word not in seen_kw:
#             seen_kw[word] = score
#     final = sorted(seen_kw.items(), key=lambda x: x[1], reverse=True)
#     return [{"word": w, "score": s} for w, s in final[:top_n]]


# # ── Extractive summarisation ────────────────────────────────────────────────
# def _is_table_or_figure_line(sentence):
#     """Return True if sentence looks like table data, metadata, or non-prose."""
#     sentence = sentence.strip()
#     words = sentence.split()
#     if not words or len(words) < 8:
#         return True

#     # Citations or weird chars
#     if '@' in sentence: return True
#     if re.search(r'\[\d+(?:,\s*\d+)*\]', sentence): return True # [1, 2] citations
#     if re.search(r'\(\w+,\s*\d{4}\)', sentence): return True    # (Smith, 2020) citations

#     # Math/Complex expressions
#     if re.search(r'O\([nkd\s\d\w·\*\+\-\^]+\)', sentence): return True
#     if re.search(r'\d+\s*[·×]\s*\d+', sentence): return True
    
#     # Table-like patterns: high proportion of numbers or short tokens
#     dim_pattern = re.compile(r'^\d+x\d+$|^\d+$|^/\d+$|^\d+\.\d+$|^[%\d\.]+$')
#     dim_count = sum(1 for w in words if dim_pattern.match(w.strip(',.;:()')))
#     if dim_count / max(len(words), 1) > 0.3: return True
    
#     # Comma heavy (lists/tables)
#     if sentence.count(',') / max(len(words), 1) > 0.35: return True
    
#     # Special symbols
#     if sum(1 for c in sentence if c in '·×†‡∗∗•|') > 2: return True
    
#     # Common table/figure headers in text extraction
#     if re.match(r'^Table\s+\d+|^Figure\s+\d+|^Fig\.\s+\d+', sentence, re.I): return True
    
#     # Messy extraction artifacts
#     if len(re.findall(r'\d+\s+\d+x\d+\s+conv', sentence)) >= 1: return True
#     if len(re.findall(r'\b\d+x\d+\b', sentence)) >= 2: return True

#     return False


# def _join_lines_to_paragraphs(text):
#     """Join fragmented PDF lines into paragraphs for better sentence detection."""
#     lines = text.split('\n')
#     paragraphs = []
#     current = []
#     for line in lines:
#         line = line.strip()
#         if not line:
#             if current:
#                 paragraphs.append(' '.join(current))
#                 current = []
#         else:
#             current.append(line)
#     if current:
#         paragraphs.append(' '.join(current))
#     return '\n\n'.join(paragraphs)


# def _extract_abstract(text):
#     """Extract abstract using explicit heading or common opener phrases."""
#     for pattern in [
#         r'\bAbstract\b[\s\-\.:—]*\n?\s*([A-Z][^\n]{50,})',
#         r'\bAbstract\b[\-\.:—\s]*([A-Z].+?)(?=\n{2,}|\b(?:1\.?\s+)?Introduction\b|\bKeywords?\b)',
#     ]:
#         match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
#         if match:
#             abstract = re.sub(r'\s+', ' ', match.group(1).strip())
#             if len(abstract.split()) > 40 and abstract[0].isalpha():
#                 for end_marker in ['1 Introduction', '1. Introduction', 'Keywords', 'Index Terms']:
#                     idx = abstract.find(end_marker)
#                     if idx > 100:
#                         abstract = abstract[:idx].strip()
#                 return abstract

#     opener = re.compile(
#         r'((?:We (?:present|propose|introduce|describe|demonstrate)|'
#         r'In this (?:paper|work|article)|'
#         r'This (?:paper|work) (?:presents|proposes|introduces|describes))'  
#         r'[^.]+\..+?)(?=\n{2,}|\b(?:1\.?\s+)?Introduction\b|\bKeywords?\b)',
#         re.DOTALL
#     )
#     match = opener.search(text)
#     if match:
#         abstract = re.sub(r'\s+', ' ', match.group(1).strip())
#         if len(abstract.split()) > 40:
#             return abstract
#     return None


# def summarise(text, n_sentences=6):
#     """Extractive summariser."""
#     ensure_nltk()
#     from nltk.tokenize import sent_tokenize
    
#     para_text = _join_lines_to_paragraphs(text)
#     abstract  = _extract_abstract(para_text)
#     if abstract:
#         return abstract

#     cutoff = max(3000, len(para_text) // 3)
#     sentences = sent_tokenize(para_text[:cutoff])
#     valid = [s for s in sentences if len(s.split()) > 9 and not _is_table_or_figure_line(s)]

#     if len(valid) < n_sentences:
#         sentences = sent_tokenize(para_text)
#         valid = [s for s in sentences if len(s.split()) > 9 and not _is_table_or_figure_line(s)]

#     if not valid:
#         paras = [p for p in para_text.split('\n\n') if len(p.split()) > 8 and not _is_table_or_figure_line(p)]
#         return ' '.join(paras[:3])[:800] if paras else text[:500]

#     if len(valid) <= n_sentences:
#         return ' '.join(valid)

#     try:
#         words = [w.lower() for s in valid for w in s.split() if w.lower() not in STOP_WORDS and w.isalpha()]
#         word_freq = Counter(words)
#         max_f = max(word_freq.values()) if word_freq else 1

#         scores = []
#         for i, s in enumerate(valid):
#             # Frequency score: sum of relative frequencies of words in sentence
#             freq_score = sum(word_freq.get(w.lower(), 0) / max_f for w in s.split() if w.isalpha())
            
#             # Position boost: sentences near the start of the paper (or intro) are usually more descriptive
#             position_boost = 1.0 + max(0, (len(valid) - i) / len(valid)) * 0.4
            
#             # Length penalty/reward: prefer sentences with 15-40 words
#             wlen = len(s.split())
#             length_mod = 1.2 if 15 < wlen < 40 else 0.8 if wlen > 60 else 1.0
            
#             scores.append(freq_score * position_boost * length_mod)

#         # Sort indices of top sentences
#         top_idx = sorted(np.argsort(scores)[-n_sentences:])
#         return ' '.join(valid[i] for i in top_idx)
#     except Exception as e:
#         print(f"[summarise] Error during ranking: {e}")
#         return ' '.join(valid[:n_sentences])


# # ── Sentence embedding ──────────────────────────────────────────────────────
# def embed_text(text):
#     """Return 384-dim normalised embedding as a Python list."""
#     snippet = text[:3000]
#     vec = _st().encode(snippet, normalize_embeddings=True)
#     return vec.tolist()


# def embed_chunks(chunks):
#     """Embed a list of chunk strings, return list of lists."""
#     texts = [c[:2000] for c in chunks]
#     vecs  = _st().encode(texts, normalize_embeddings=True, batch_size=32)
#     return [v.tolist() for v in vecs]


# # ── Text chunking ──────────────────────────────────────────────────────────
# def chunk_text(text, window_words=200, step_words=150):
#     words = text.split()
#     chunks = []
#     for i in range(0, max(1, len(words) - window_words + 1), step_words):
#         chunk_words = words[i:i + window_words]
#         if len(chunk_words) >= 30:
#             chunks.append({"text": " ".join(chunk_words), "word_offset": i})
#     if words and len(words) >= 30:
#         last_start = max(0, len(words) - window_words)
#         last_chunk = words[last_start:]
#         if last_start not in [c["word_offset"] for c in chunks]:
#             chunks.append({"text": " ".join(last_chunk), "word_offset": last_start})
#     return chunks


# # ── Cosine similarity ───────────────────────────────────────────────────────
# def cosine_similarity(vec1, vec2):
#     a = np.array(vec1, dtype="float32")
#     b = np.array(vec2, dtype="float32")
#     denom = (np.linalg.norm(a) * np.linalg.norm(b))
#     if denom == 0: return 0.0
#     return float(np.dot(a, b) / denom)


# # ── Run full pipeline ────────────────────────────────────────────────────────
# def run_pipeline(text):
#     """Run all NLP steps and return dict of results."""
#     summary  = summarise(text)
#     keywords = extract_keywords(text)
#     entities = extract_entities(text)
#     embedding= embed_text(text)
#     return {
#         "summary":   summary,
#         "keywords":  keywords,
#         "entities":  entities,
#         "embedding": embedding
#     }

import re
import math
import threading
import numpy as np
from collections import Counter
import os
from google import genai
from google.genai import types

# Configure Gemini API key securely from the environment variable
# genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))

# ── lazy-loaded singletons ──────────────────────────────────────────────────
_spacy_nlp   = None
_st_model    = None
_model_lock  = threading.Lock()

def _nlp():
    global _spacy_nlp
    if _spacy_nlp is None:
        import spacy
        with _model_lock:
            if _spacy_nlp is None:          # double-checked locking
                _spacy_nlp = spacy.load("en_core_web_sm")
    return _spacy_nlp

def _st():
    global _st_model
    if _st_model is None:
        from sentence_transformers import SentenceTransformer
        with _model_lock:
            if _st_model is None:           # double-checked locking
                _st_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _st_model


def warmup_models():
    """Eagerly load all heavy models and indexes in the calling thread.
    Call this once at app startup (main thread) so background threads
    never trigger model initialisation — which can segfault on Windows.
    
    CRITICAL: Order matters on Windows. We must load ST before NLTK/spaCy 
    to avoid native OpenMP/oneDNN initialization conflicts.
    """
    print("[warmup] 1/4 Loading SentenceTransformer (ST)...", flush=True)
    _st()
    
    print("[warmup] 2/4 Loading spaCy model...", flush=True)
    _nlp()
    
    print("[warmup] 3/4 Initialising NLTK...", flush=True)
    ensure_nltk()
    
    print("[warmup] 4/4 Pre-loading FAISS index...", flush=True)
    from backend.services.search_service import warmup_faiss
    warmup_faiss()
    
    print("[warmup] ALL SYSTEMS GO. Models ready.", flush=True)


# ── NLTK downloads (idempotent) ─────────────────────────────────────────────
_nltk_ready = False

def ensure_nltk():
    global _nltk_ready
    if _nltk_ready:
        return
        
    import nltk
    for pkg in ["punkt_tab", "punkt", "stopwords", "averaged_perceptron_tagger", "wordnet"]:
        try:
            if "punkt" in pkg:
                nltk.data.find(f"tokenizers/{pkg}")
            else:
                nltk.data.find(f"corpora/{pkg}")
        except (LookupError, OSError):
            nltk.download(pkg, quiet=True)
    
    global STOP_WORDS, sent_tokenize, word_tokenize
    from nltk.corpus import stopwords
    from nltk.tokenize import sent_tokenize, word_tokenize
    STOP_WORDS = set(stopwords.words("english"))
    _nltk_ready = True

# We still need these at module level for other functions, but they will be 
# populated by the first call to ensure_nltk() or warmup_models().
STOP_WORDS = set()
sent_tokenize = None
word_tokenize = None

def _get_tokenize():
    """Lazy fetch of NLTK tokenizers."""
    ensure_nltk()
    from nltk.tokenize import sent_tokenize, word_tokenize
    return sent_tokenize, word_tokenize


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
    ensure_nltk()
    from nltk.tokenize import word_tokenize
    
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


# ── Extractive summarisation helpers (kept for test compatibility) ──────────
def _is_table_or_figure_line(sentence):
    """Return True if sentence looks like table data, metadata, or non-prose."""
    sentence = sentence.strip()
    words = sentence.split()
    if not words or len(words) < 8:
        return True

    # Citations or weird chars
    if '@' in sentence: return True
    if re.search(r'\[\d+(?:,\s*\d+)*\]', sentence): return True # [1, 2] citations
    if re.search(r'\(\w+,\s*\d{4}\)', sentence): return True    # (Smith, 2020) citations

    # Math/Complex expressions
    if re.search(r'O\([nkd\s\d\w·\*\+\-\^]+\)', sentence): return True
    if re.search(r'\d+\s*[·×]\s*\d+', sentence): return True
    
    # Table-like patterns: high proportion of numbers or short tokens
    dim_pattern = re.compile(r'^\d+x\d+$|^\d+$|^/\d+$|^\d+\.\d+$|^[%\d\.]+$')
    dim_count = sum(1 for w in words if dim_pattern.match(w.strip(',.;:()')))
    if dim_count / max(len(words), 1) > 0.3: return True
    
    # Comma heavy (lists/tables)
    if sentence.count(',') / max(len(words), 1) > 0.35: return True
    
    # Special symbols
    if sum(1 for c in sentence if c in '·×†‡∗∗•|') > 2: return True
    
    # Common table/figure headers in text extraction
    if re.match(r'^Table\s+\d+|^Figure\s+\d+|^Fig\.\s+\d+', sentence, re.I): return True
    
    # Messy extraction artifacts
    if len(re.findall(r'\d+\s+\d+x\d+\s+conv', sentence)) >= 1: return True
    if len(re.findall(r'\b\d+x\d+\b', sentence)) >= 2: return True

    return False


def _join_lines_to_paragraphs(text):
    """Join fragmented PDF lines into paragraphs for better sentence detection."""
    lines = text.split('\n')
    paragraphs = []
    current = []
    for line in lines:
        line = line.strip()
        if not line:
            if current:
                paragraphs.append(' '.join(current))
                current = []
        else:
            current.append(line)
    if current:
        paragraphs.append(' '.join(current))
    return '\n\n'.join(paragraphs)


def _extract_abstract(text):
    """Extract abstract using explicit heading or common opener phrases."""
    for pattern in [
        r'\bAbstract\b[\s\-\.:—]*\n?\s*([A-Z][^\n]{50,})',
        r'\bAbstract\b[\-\.:—\s]*([A-Z].+?)(?=\n{2,}|\b(?:1\.?\s+)?Introduction\b|\bKeywords?\b)',
    ]:
        match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
        if match:
            abstract = re.sub(r'\s+', ' ', match.group(1).strip())
            if len(abstract.split()) > 40 and abstract[0].isalpha():
                for end_marker in ['1 Introduction', '1. Introduction', 'Keywords', 'Index Terms']:
                    idx = abstract.find(end_marker)
                    if idx > 100:
                        abstract = abstract[:idx].strip()
                return abstract

    opener = re.compile(
        r'((?:We (?:present|propose|introduce|describe|demonstrate)|'
        r'In this (?:paper|work|article)|'
        r'This (?:paper|work) (?:presents|proposes|introduces|describes))'  
        r'[^.]+\..+?)(?=\n{2,}|\b(?:1\.?\s+)?Introduction\b|\bKeywords?\b)',
        re.DOTALL
    )
    match = opener.search(text)
    if match:
        abstract = re.sub(r'\s+', ' ', match.group(1).strip())
        if len(abstract.split()) > 40:
            return abstract
    return None


# ── AI Summarisation ────────────────────────────────────────────────────────
# ── AI Summarisation ────────────────────────────────────────────────────────
def summarise(text, n_sentences=6):
    """
    Analyzes the full text of a research paper and returns a structured summary,
    strictly ignoring the pre-written abstract.
    """
    # 1. Initialize the new Client (it automatically finds GEMINI_API_KEY in your .env!)
    client = genai.Client()
    
    prompt = f"""
    You are an expert AI research assistant. I am providing you with the full text of a research paper.
    
    CRITICAL INSTRUCTIONS: 
    1. Do NOT simply repeat, paraphrase, or output the paper's Abstract. 
    2. You must analyze the ENTIRE document and synthesize the methodology, architecture, and results from the main body of the text.
    
    Use the exact following formatting:
    
    ### **Overview**
    [1-2 sentences explaining the core proposition]
    
    ### **The Problem with Previous Models**
    [Bullet points detailing what the paper attempts to solve]
    
    ### **The Core Architecture/Methodology**
    [Bullet points detailing how the proposed solution works based on the methodology section]
    
    ### **Key Advantages**
    [Bullet points highlighting efficiency, speed, or novel benefits]
    
    ### **Experimental Results**
    [Bullet points detailing the exact performance metrics and benchmarks achieved from the results section]

    Here is the full paper text to analyze:
    {text}
    """
    
    try:
        # 2. Call the API using the new client and config structure
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2
            )
        )
        return response.text
    except Exception as e:
        print(f"Error during summarization: {e}")
        return "Could not generate summary."


# ── Sentence embedding ──────────────────────────────────────────────────────
def embed_text(text):
    """Return 384-dim normalised embedding as a Python list."""
    snippet = text[:3000]
    vec = _st().encode(snippet, normalize_embeddings=True)
    return vec.tolist()


def embed_chunks(chunks):
    """Embed a list of chunk strings, return list of lists."""
    texts = [c[:2000] for c in chunks]
    vecs  = _st().encode(texts, normalize_embeddings=True, batch_size=32)
    return [v.tolist() for v in vecs]


# ── Text chunking ──────────────────────────────────────────────────────────
def chunk_text(text, window_words=200, step_words=150):
    words = text.split()
    chunks = []
    for i in range(0, max(1, len(words) - window_words + 1), step_words):
        chunk_words = words[i:i + window_words]
        if len(chunk_words) >= 30:
            chunks.append({"text": " ".join(chunk_words), "word_offset": i})
    if words and len(words) >= 30:
        last_start = max(0, len(words) - window_words)
        last_chunk = words[last_start:]
        if last_start not in [c["word_offset"] for c in chunks]:
            chunks.append({"text": " ".join(last_chunk), "word_offset": last_start})
    return chunks


# ── Cosine similarity ───────────────────────────────────────────────────────
def cosine_similarity(vec1, vec2):
    a = np.array(vec1, dtype="float32")
    b = np.array(vec2, dtype="float32")
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0: return 0.0
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