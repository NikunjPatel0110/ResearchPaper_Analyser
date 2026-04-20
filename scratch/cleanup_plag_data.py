import os
import sys
from pymongo import MongoClient
from bson import ObjectId

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.config import Config

def cleanup_orphaned_data():
    print("Connecting to MongoDB...")
    client = MongoClient(Config.MONGO_URI)
    db = client.get_database()
    
    # 1. Get all valid paper IDs
    print("Fetching valid paper IDs...")
    valid_pids = set(str(p["_id"]) for p in db.papers.find({}, {"_id": 1}))
    print(f"Found {len(valid_pids)} valid papers.")

    # 2. Cleanup fingerprints
    print("Cleaning up fingerprints...")
    # Find fingerprints where paper_id is NOT in valid_pids
    # Since valid_pids is a set, we might need to do this in chunks or using $nin
    # But for a local DB, we can just iterate or use a simple query.
    
    # Let's find all unique paper_ids in fingerprints
    fingerprint_pids = set(db.fingerprints.distinct("paper_id"))
    orphaned_fp = fingerprint_pids - valid_pids
    
    if orphaned_fp:
        print(f"Found {len(orphaned_fp)} orphaned paper IDs in fingerprints.")
        res = db.fingerprints.delete_many({"paper_id": {"$in": list(orphaned_fp)}})
        print(f"  Deleted {res.deleted_count} orphaned fingerprint entries.")
    else:
        print("  No orphaned fingerprints found.")

    # 3. Cleanup chunk_index
    print("Cleaning up chunk_index...")
    chunk_pids = set(db.chunk_index.distinct("paper_id"))
    orphaned_chunks = chunk_pids - valid_pids
    
    if orphaned_chunks:
        print(f"Found {len(orphaned_chunks)} orphaned paper IDs in chunk_index.")
        res = db.chunk_index.delete_many({"paper_id": {"$in": list(orphaned_chunks)}})
        print(f"  Deleted {res.deleted_count} orphaned chunk entries.")
    else:
        print("  No orphaned chunk entries found.")

    print("Done cleanup.")

if __name__ == "__main__":
    cleanup_orphaned_data()
