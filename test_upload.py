import os
import sys
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

print("Starting fake upload process...")
sys.stdout.flush()

from backend.services.parse_service import parse_file, get_extension
from backend.services.nlp_service import summarise, extract_keywords, extract_entities
from backend.services.search_service import add_chunks_to_faiss
from backend.services.plagiarism_service import index_paper_chunks, check_plagiarism
from backend.services.ai_detect_service import detect_ai_content

print("All services imported.")
sys.stdout.flush()

sample_text = "This is a dummy paper text. " * 50

print("Running summarisation...")
sys.stdout.flush()
sum_res = summarise(sample_text)

print("Running NLP keywords...")
sys.stdout.flush()
kw = extract_keywords(sample_text)

print("Running NLP entities...")
sys.stdout.flush()
ents = extract_entities(sample_text)

print("Running AI Detect...")
sys.stdout.flush()
try:
    ai_res = detect_ai_content(sample_text)
    print("AI detect done:", ai_res)
except Exception as e:
    print("AI detect failed:", e)

print("Running search index (FAISS + torch)...")
sys.stdout.flush()
chunks = ["This is chunk one.", "This is chunk two."]
meta = [{"paper_id": "dummy", "chk": 1}, {"paper_id": "dummy", "chk": 2}]
try:
    add_chunks_to_faiss(chunks, meta)
    print("Chunks added.")
except Exception as e:
    print("FAISS chunk add:", e)

try:
    print("Plag check...")
    sys.stdout.flush()
    plag = check_plagiarism("dummy", chunks)
except Exception as e:
    print("Plag check error:", e)

print("All done!")
sys.stdout.flush()
