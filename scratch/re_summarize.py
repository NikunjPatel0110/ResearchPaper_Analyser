import os
import sys
from pymongo import MongoClient
from bson import ObjectId

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.config import Config
from backend.services import nlp_service

def re_summarize_all():
    print("Connecting to MongoDB...")
    client = MongoClient(Config.MONGO_URI)
    db = client.get_database()
    papers = db.papers

    print("Fetching papers...")
    all_papers = list(papers.find({"status": "ready"}))
    total = len(all_papers)
    print(f"Found {total} ready papers.")

    for i, p in enumerate(all_papers):
        pid = str(p["_id"])
        title = p.get("title", "Untitled")
        print(f"[{i+1}/{total}] Processing: {title} ({pid})")
        
        text = p.get("raw_text", "")
        if not text:
            print(f"  Skipping: No raw_text found.")
            continue
            
        try:
            new_summary = nlp_service.summarise(text)
            papers.update_one({"_id": p["_id"]}, {"$set": {"summary": new_summary}})
            print(f"  Success.")
        except Exception as e:
            print(f"  Failed: {e}")

    print("Done.")

if __name__ == "__main__":
    re_summarize_all()
