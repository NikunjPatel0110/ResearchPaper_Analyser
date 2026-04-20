import re
import hashlib

def sliding_window_chunks(text: str, size: int = 150, stride: int = 75) -> list[str]:
    words = text.split()
    chunks = []
    for i in range(0, len(words) - size + 1, stride):
        chunk = " ".join(words[i : i + size])
        if len(chunk.split()) >= 30:  # ignore tiny trailing chunks
            chunks.append(chunk)
    return chunks

def ngram_hashes(text: str, n: int = 5) -> list[str]:
    cleaned = re.sub(r"[^\w\s]", "", text.lower())
    words   = cleaned.split()
    ngrams  = [" ".join(words[i : i + n]) for i in range(len(words) - n + 1)]
    return [hashlib.md5(ng.encode()).hexdigest() for ng in ngrams]

def deduplicate_chunks(flagged: list[dict]) -> list[dict]:
    seen, result = set(), []
    for c in flagged:
        key = c["text"][:60]
        if key not in seen:
            seen.add(key)
            result.append(c)
    return result