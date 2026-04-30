"""
migrate_add_quota.py
Run once to add subscription/quota fields to all existing users.
Usage: python scripts/migrate_add_quota.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from pymongo import MongoClient
from config import Config
from datetime import datetime

client = MongoClient(Config.MONGO_URI)
db     = client.get_default_database()
users  = db["users"]

result = users.update_many(
    {"plan": {"$exists": False}},
    {"$set": {
        "plan":             "free",
        "upload_count":     0,
        "plan_expires_at":  None,
        "upload_limit":     Config.FREE_UPLOAD_LIMIT,
        "last_payment_id":  None,
        "last_order_id":    None,
        "plan_activated_at":None,
    }}
)

print(f"Migrated {result.modified_count} existing users to free plan with upload_count=0")

# Also create indexes for payments collection
db["payments"].create_index("payment_id", unique=True, sparse=True)
db["payments"].create_index("user_id")
db["users"].create_index("plan")
print("Indexes created for payments collection.")