import sys
import os

# Add the project ROOT to path so 'backend' is findable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pymongo import MongoClient
from backend.config import Config
import secrets
from datetime import datetime, timedelta

# Connect directly — no service imports needed
client = MongoClient(Config.MONGO_URI)
db     = client.get_default_database()

# Find admin user
admin = db["users"].find_one({"role": "admin"})
if not admin:
    print("No admin user found. Run create_admin.py first.")
    sys.exit(1)

# Generate invite code
code       = "INV-" + secrets.token_hex(4).upper()
expires_at = datetime.utcnow() + timedelta(hours=720)

db["invite_codes"].insert_one({
    "code":       code,
    "created_by": admin["_id"],
    "used_by":    None,
    "is_used":    False,
    "expires_at": expires_at,
    "note":       "Generated via script",
    "created_at": datetime.utcnow()
})

print("\n✅ New invite code generated:")
print(f"   Code       : {code}")
print(f"   Expires at : {expires_at.strftime('%Y-%m-%d %H:%M')} UTC")
print(f"   Valid for  : 30 days\n")