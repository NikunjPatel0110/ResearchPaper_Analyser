import os
from pymongo import MongoClient
from bson import ObjectId
from backend.config import Config

client = MongoClient(Config.MONGO_URI)
db = client.paperiq

papers = list(db.papers.find({}, {"title": 1, "raw_text": 1}))

for p in papers:
    print("-----")
    print("ID:", p["_id"])
    print("Title:", p["title"])
    text_len = len(p.get("raw_text", ""))
    print("Text length:", text_len)
    if text_len > 0:
        print("First 100 chars:", p["raw_text"][:100].replace("\n", "\\n"))
