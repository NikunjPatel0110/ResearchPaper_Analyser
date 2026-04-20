import os
import sys
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

from backend.app import create_app
from backend.models.db import get_db, papers
from backend.services.plagiarism_service import delete_paper_data
from bson import ObjectId

app = create_app()

def dedupe():
    with app.app_context():
        db = get_db()
        all_papers = list(papers().find().sort("created_at", -1))
        
        seen_titles = {} # title -> keep_id
        to_delete = []
        
        for p in all_papers:
            title = p.get("title", "").strip().lower()
            if title in seen_titles:
                to_delete.append(p)
            else:
                seen_titles[title] = p["_id"]
        
        print(f"Found {len(to_delete)} duplicate papers to remove.")
        
        for p in to_delete:
            pid = p["_id"]
            title = p["title"]
            print(f"Removing duplicate: {title} ({pid})")
            
            # 1. Delete physical file
            fp = p.get("file_path")
            if fp and os.path.exists(fp):
                try:
                    os.remove(fp)
                    print(f"  - Deleted file: {fp}")
                except Exception as e:
                    print(f"  - Failed to delete file: {e}")
            
            # 2. Scrub metadata (fingerprints, chunks, reports)
            delete_paper_data(str(pid))
            
            # 3. Delete paper doc
            papers().delete_one({"_id": pid})
            print(f"  - Deleted paper document.")

        print("Deduplication complete.")

if __name__ == "__main__":
    dedupe()
