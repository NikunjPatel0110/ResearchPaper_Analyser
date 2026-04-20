import hashlib
from pymongo import MongoClient
from backend.config import Config
from backend.services.plagiarism_service import _ngram_hashes, _sliding_window_chunks
from bson import ObjectId

client = MongoClient(Config.MONGO_URI)
db = client.paperiq

pid_cvpr = "69de80765eaea0b6d2dcf706"
cvpr_paper = db.papers.find_one({"_id": ObjectId(pid_cvpr)})

text = cvpr_paper["raw_text"]
chunks = _sliding_window_chunks(text)
chunk = chunks[0]
hashes = _ngram_hashes(chunk, n=5)

h = hashes[0]
print(f"Hash: {h} from CVPR paper")

matches = list(db.fingerprints.find({"hash": h}))
print(f"Found {len(matches)} matches in DB.")
for m in matches:
    print(f"Matched paper_id in fingerprint: {m['paper_id']}")
    doc = db.papers.find_one({"_id": ObjectId(m["paper_id"])})
    if doc:
        print(f"  -> Title in db: {doc['title']}")
    else:
        print("  -> Ghost paper")
